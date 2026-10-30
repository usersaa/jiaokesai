"""校园共享电单车调度 MDP 环境。

动作编码（与建模文档 9.2 一致，做了可执行化处理）：
    action = (mode, station, tier)
    mode   : 0 = 不动(wait), 1 = 搬运(truck), 2 = 发券(coupon)
    station: 目标点位索引 0..N-1
    tier   : 0/1，对应 config 中的两档数量/券额

剪枝（Staffolani 式(11)）：
    仅当 n_i^avail < δL_i（缺车临界）或 L_i - n_i < δL_i（满位临界）时，
    点位才进入搬运候选集；无临界点则只能 wait。
    发券候选为「有可用车且非缺车临界」的点位（券用于把用户引向有车的点）。

奖励（Staffolani 式(10)）：
    r = -[w1*E_agent + w2*E_env + w3*T_truck + w4*P_inc]
    E_agent / E_env 通过「同需求下的无动作反事实」分解。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np

from ..choice import ChoiceModel
from ..config import time_grid
from ..demand import DemandModel
from ..entities import Scenario, TruckState
from ..metrics import EpisodeMetrics, distance_weight_matrix
from ..supply import SupplyModel
from .reward import compute_reward, reward_breakdown


class CampusEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        cfg: Dict[str, Any],
        scenario: Scenario,
        demand_model: Optional[DemandModel] = None,
        supply_model: Optional[SupplyModel] = None,
        choice_model: Optional[ChoiceModel] = None,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self.cfg = cfg
        self.sc = scenario
        self.n = scenario.n
        self.step_min = int(cfg["time"]["step_minutes"])
        self.grid = time_grid(cfg)
        self.T = len(self.grid)

        self.dm = demand_model or DemandModel(cfg, scenario)
        self.sm = supply_model or SupplyModel(cfg, scenario)
        self.cm = choice_model or ChoiceModel(cfg, scenario)

        self.capacity = scenario.capacities.astype(float)
        self.target = np.array(
            [s.target_bikes if s.target_bikes > 0 else s.capacity * 0.5 for s in scenario.stations],
            dtype=float,
        )

        self.delta = float(cfg["decision"]["delta_critical"])
        self.qty_tiers = [int(x) for x in cfg["decision"]["qty_tiers_bikes"]]
        self.coupon_tiers = [float(x) for x in cfg["decision"]["coupon_tiers_yuan"]]
        self.budget = float(cfg["decision"]["coupon_budget_daily"])
        self.truck_cap = int(cfg["truck"]["capacity"])
        self.truck_count = int(cfg["truck"]["count"])
        if self.truck_count != 1:
            raise ValueError("当前实现支持单辆运维车（config: truck.count=1）")
        self.depot = int(cfg["night"].get("depot_station", 0))
        self.alternate = bool(cfg["truck"].get("alternate_pick_drop", True))
        self.reward_scale = float(cfg["cost"].get("reward_scale", 1.0))
        self.noise_cv = float(cfg["demand"].get("noise_cv", 0.0))
        self.weekend_factor = float(cfg["demand"].get("weekend_factor", 1.0))

        self.dist_weight = distance_weight_matrix(scenario.dist_m, alpha_m=400.0)

        # 动作空间：
        #   discrete     -> Discrete(3*N*2)，配合精确扁平掩码（推荐，SB3 最稳）
        #   multidiscrete-> MultiDiscrete([3, N, 2])，按维度掩码（论文多头形式）
        self.action_encoding = str(cfg.get("ppo", {}).get("action_encoding", "discrete")).lower()
        if self.action_encoding == "multidiscrete":
            self.action_space = gym.spaces.MultiDiscrete([3, self.n, 2])
        else:
            self.action_space = gym.spaces.Discrete(3 * self.n * 2)
        self.obs_dim = 4 * self.n + 12
        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(self.obs_dim,), dtype=np.float32
        )

        self._rng = np.random.default_rng(seed)
        self.day_type = 0
        self.step_idx = 0
        self.inv = scenario.init_inventory().astype(float)
        self.truck = TruckState(station=self.depot, load=0, busy_until=-1)
        self.prices = np.zeros(self.n, dtype=float)
        self.coupon_used = 0.0
        self.metrics = EpisodeMetrics()
        self._D_est_cache: Optional[np.ndarray] = None
        self._D_est_step = -1

    # ============================================================
    # Gym 接口
    # ============================================================
    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict] = None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        options = options or {}
        self.day_type = int(options.get("day_type", 0))
        self.step_idx = 0
        self.inv = self.sc.init_inventory().astype(float)
        self.truck = TruckState(station=self.depot, load=0, busy_until=-1)
        self.prices = np.zeros(self.n, dtype=float)
        self.coupon_used = 0.0
        self.metrics = EpisodeMetrics()
        self._D_est_cache = None
        self._D_est_step = -1
        return self._obs(), self._info(0, 0, 0, True)

    def step(self, action):
        mode, station, tier = self._decode(action)
        valid = self._is_valid(mode, station, tier)
        if not valid:
            mode, station, tier = 0, 0, 0

        inv_pre = self.inv.copy()
        avail_pre = self.sm.available(inv_pre)

        # ---------------- 1) 搬运动作 ----------------
        truck_time = 0.0
        truck_trip = 0
        if mode == 1:
            direction = self._truck_direction(station)
            qty = self._truck_qty(station, tier)
            travel = self.sm.truck_travel_min(self.truck.station, station)
            service = travel + qty * self.sm.load_min
            if direction == "dropoff":
                self.inv[station] += qty
                self.truck.load -= qty
            else:
                self.inv[station] -= qty
                self.truck.load += qty
            self.truck.station = station
            self.truck.busy_until = self.step_idx + self.sm.busy_steps(service) - 1
            self.truck.last_truck_mode = direction
            truck_time = service
            truck_trip = 1

        # ---------------- 2) 发券动作 ----------------
        self.prices = np.zeros(self.n, dtype=float)
        if mode == 2:
            self.prices[station] = self.coupon_tiers[tier]

        # ---------------- 3) 需求与反事实 ----------------
        D = self._realized_demand(self.step_idx)
        od = self.dm.od_matrix(D)
        P = self.dm.od_probabilities()

        # 反事实：不做搬运/发券，但保留自然移步（kappa）
        cf_b, cf_eb_origin = self.sm.borrow(D, avail_pre)
        cf_od = self.dm.realized_od(od, cf_b, D)
        cf_r = self.sm.returns(cf_od)
        cf_extra, _, cf_M = self.cm.redirect(
            cf_eb_origin, avail_pre - cf_b, D, np.zeros(self.n)
        )
        cf_eb_final = cf_eb_origin - cf_M.sum(axis=1)
        cf_returns = cf_r + (cf_extra[:, None] * P).sum(axis=0)
        cf_free = self.sm.return_free_space(inv_pre, cf_b + cf_extra, np.zeros(self.n))
        cf_er = self.sm.return_shortage(cf_returns, cf_free)
        cf_short = cf_eb_final + cf_er

        # ---------------- 4) 实际供需 ----------------
        avail_after = self.sm.available(self.inv)
        b, e_b_origin = self.sm.borrow(D, avail_after)
        realized_od = self.dm.realized_od(od, b, D)
        r = self.sm.returns(realized_od)

        extra, coupon_cost, M = self.cm.redirect(
            e_b_origin, avail_after - b, D, self.prices
        )

        remaining_budget = self.budget - self.coupon_used
        if coupon_cost > remaining_budget:
            factor = max(remaining_budget, 0.0) / max(coupon_cost, 1e-9)
            extra = extra * factor
            M = M * factor
            coupon_cost = coupon_cost * factor
        self.coupon_used += coupon_cost

        # 移步后仍未满足的需求，才是真正的借车短缺
        e_b = np.maximum(e_b_origin - M.sum(axis=1), 0.0)

        b_total = b + extra
        extra_returns = extra[:, None] * P
        r_total = r + extra_returns.sum(axis=0)

        free = self.sm.return_free_space(self.inv, b_total, np.zeros(self.n))
        e_r = self.sm.return_shortage(r_total, free)
        accepted = np.minimum(r_total, free)

        inv_next = self.inv - b_total + accepted
        inv_next = np.clip(inv_next, 0.0, self.capacity)

        # ---------------- 5) 奖励分解 ----------------
        actual_short = e_b + e_r
        env_def = np.minimum(actual_short, cf_short)
        agent_short = np.maximum(actual_short - cf_short, 0.0)

        reward = compute_reward(
            float(agent_short.sum()), float(env_def.sum()),
            truck_time, coupon_cost, self.cfg,
        ) * self.reward_scale

        # ---------------- 6) 指标 ----------------
        od_actual = realized_od + extra[:, None] * P
        self.metrics.add_step(
            demand=D,
            served=float(b_total.sum()),
            e_b=e_b,
            e_r=e_r,
            n_avail=avail_after,
            free_space=free,
            od=od_actual,
            agent_shortage=float(agent_short.sum()),
            env_deficit=float(env_def.sum()),
            truck_time=truck_time,
            truck_trip=truck_trip,
            coupon_cost=coupon_cost,
            dist_weight=self.dist_weight,
        )

        # ---------------- 7) 推进 ----------------
        self.inv = inv_next
        self.step_idx += 1
        terminated = self.step_idx >= self.T
        obs = self._obs()
        info = self._info(mode, station, tier, valid)
        info["reward_breakdown"] = reward_breakdown(
            float(agent_short.sum()), float(env_def.sum()),
            truck_time, coupon_cost, self.cfg,
        )
        return obs, float(reward), bool(terminated), False, info

    # ============================================================
    # 动作解码 / 掩码
    # ============================================================
    def _decode(self, action) -> Tuple[int, int, int]:
        a = np.asarray(action).reshape(-1)
        if a.size == 1:
            idx = int(a[0])
            total = 3 * self.n * 2
            idx = min(max(idx, 0), total - 1)
            mode = idx // (self.n * 2)
            rem = idx % (self.n * 2)
            station = rem // 2
            tier = rem % 2
            return mode, station, tier
        mode = int(a[0]) if a.size > 0 else 0
        station = int(a[1]) if a.size > 1 else 0
        tier = int(a[2]) if a.size > 2 else 0
        mode = min(max(mode, 0), 2)
        station = min(max(station, 0), self.n - 1)
        tier = min(max(tier, 0), 1)
        return mode, station, tier

    def _critical(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        avail = self.sm.available(self.inv)
        shortage = avail < self.delta * self.capacity
        overfull = (self.capacity - self.inv) < self.delta * self.capacity
        return shortage, overfull, avail

    def _truck_direction(self, station: int) -> Optional[str]:
        shortage, overfull, _ = self._critical()
        if shortage[station] and not overfull[station]:
            return "dropoff"
        if overfull[station] and not shortage[station]:
            return "pickup"
        if shortage[station] and overfull[station]:
            return "dropoff" if self.truck.load > 0 else "pickup"
        return None

    def _truck_reachable(self, station: int) -> bool:
        travel = self.sm.truck_travel_min(self.truck.station, station)
        return travel + self.sm.load_min <= self.sm.available_truck_min() + 1e-9

    def _truck_qty(self, station: int, tier: int) -> int:
        direction = self._truck_direction(station)
        if direction is None:
            return 0
        q = int(self.qty_tiers[tier])
        if direction == "dropoff":
            q = min(q, int(self.truck.load), int(self.capacity[station] - self.inv[station]))
        else:
            q = min(q, int(self.truck_cap - self.truck.load), int(self.inv[station]))
        travel = self.sm.truck_travel_min(self.truck.station, station)
        max_by_time = int(np.floor(
            (self.sm.available_truck_min() - travel) / max(self.sm.load_min, 1e-9)
        ))
        q = min(q, max_by_time)
        if q < 1:
            return 0
        if self.alternate and self.truck.last_truck_mode not in ("none", direction):
            # 允许交替；同向连续动作被禁止
            pass
        if self.alternate and self.truck.last_truck_mode == direction:
            return 0
        return q

    def _expected_demand(self) -> np.ndarray:
        if self._D_est_step != self.step_idx or self._D_est_cache is None:
            self._D_est_cache = self.dm.true_demand(self.step_idx)
            self._D_est_step = self.step_idx
        return self._D_est_cache

    def _coupon_feasible(self, station: int, tier: int) -> bool:
        price = self.coupon_tiers[tier]
        D = self._expected_demand()
        est = price * float(D[station]) * self.cm.gamma
        return (self.budget - self.coupon_used) + 1e-9 >= est

    def _is_valid(self, mode: int, station: int, tier: int) -> bool:
        if mode == 0:
            return True
        shortage, overfull, avail = self._critical()
        if mode == 1:
            if self.truck.busy_until >= self.step_idx:
                return False
            if not (shortage[station] or overfull[station]):
                return False
            return self._truck_qty(station, tier) > 0
        if mode == 2:
            if shortage[station] or avail[station] <= 0:
                return False
            if self.budget - self.coupon_used <= 1e-9:
                return False
            return self._coupon_feasible(station, tier)
        return False

    def _masks(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        shortage, overfull, avail = self._critical()
        reach = np.array([self._truck_reachable(s) for s in range(self.n)], dtype=bool)
        truck_cand = (shortage | overfull) & reach
        truck_idle = self.truck.busy_until < self.step_idx
        truck_valid = bool(
            truck_idle and any(
                self._truck_qty(s, t) > 0 for s in range(self.n) for t in (0, 1)
            )
        )
        coupon_cand = (~shortage) & (avail > 0)
        coupon_valid = bool(
            (self.budget - self.coupon_used) > 1e-9
            and any(self._coupon_feasible(s, t) for s in range(self.n) for t in (0, 1))
        )
        mode_mask = np.array([True, truck_valid, coupon_valid], dtype=bool)
        station_mask = (truck_cand | coupon_cand).astype(bool)
        qty_mask = np.array([True, True], dtype=bool)
        return mode_mask, station_mask, qty_mask

    def action_masks(self) -> np.ndarray:
        """供 sb3-contrib MaskablePPO 使用。

        discrete 模式返回长度 3*N*2 的精确扁平掩码；
        multidiscrete 模式返回按维度拼接的一维掩码。
        """
        if self.action_encoding != "multidiscrete":
            return self.valid_action_mask_flat()
        m, s, q = self._masks()
        return np.concatenate([m, s, q]).astype(bool)

    def action_masks_list(self) -> List[np.ndarray]:
        m, s, q = self._masks()
        return [m, s, q]

    def valid_action_mask_flat(self) -> np.ndarray:
        """扁平动作掩码（Discrete 回退用），长度 3*N*2。"""
        flat = np.zeros((3, self.n, 2), dtype=bool)
        for mode in range(3):
            for s in range(self.n):
                for t in range(2):
                    flat[mode, s, t] = self._is_valid(mode, s, t)
        return flat.reshape(-1)

    # ============================================================
    # 观测
    # ============================================================
    def _realized_demand(self, step: int) -> np.ndarray:
        D = self.dm.true_demand(step).astype(float)
        if self.noise_cv > 0:
            sigma = self.noise_cv
            noise = self._rng.lognormal(mean=-0.5 * sigma * sigma, sigma=sigma, size=self.n)
            D = D * noise
        if self.day_type == 1:
            D = D * self.weekend_factor
        return np.maximum(D, 0.0)

    def _obs(self) -> np.ndarray:
        L = np.maximum(self.capacity, 1.0)
        avail = self.sm.available(self.inv).astype(float)
        minute = self.grid[min(self.step_idx, self.T - 1)] + self.step_min / 2.0
        ang = 2.0 * np.pi * (minute % (24 * 60)) / (24 * 60)

        truck_pos = np.zeros(self.n, dtype=float)
        truck_pos[min(max(self.truck.station, 0), self.n - 1)] = 1.0

        day_type = np.zeros(2, dtype=float)
        day_type[min(max(self.day_type, 0), 1)] = 1.0

        last_mode = np.zeros(3, dtype=float)
        idx = {"none": 0, "pickup": 1, "dropoff": 2}.get(self.truck.last_truck_mode, 0)
        last_mode[idx] = 1.0

        parts = [
            np.clip(self.inv / L, 0.0, 1.0),
            np.clip((self.inv - self.target) / L * 0.5 + 0.5, 0.0, 1.0),
            np.clip(avail / L, 0.0, 1.0),
            np.array([np.clip(self.truck.load / max(self.truck_cap, 1), 0.0, 1.0)]),
            truck_pos,
            np.array([1.0 if self.truck.busy_until >= self.step_idx else 0.0]),
            np.array([(np.sin(ang) + 1.0) / 2.0, (np.cos(ang) + 1.0) / 2.0]),
            np.array([self.dm.pulse_flag(min(self.step_idx, self.T - 1)),
                      self.dm.pulse_phase(min(self.step_idx, self.T - 1))]),
            day_type,
            last_mode,
            np.array([np.clip((self.budget - self.coupon_used) / max(self.budget, 1e-9), 0.0, 1.0)]),
        ]
        return np.concatenate(parts).astype(np.float32)

    def _info(self, mode: int, station: int, tier: int, valid: bool) -> Dict[str, Any]:
        return {
            "step": self.step_idx,
            "mode": mode,
            "station": station,
            "tier": tier,
            "valid": valid,
            "truck_load": self.truck.load,
            "truck_station": self.truck.station,
            "truck_busy_until": self.truck.busy_until,
            "coupon_used": self.coupon_used,
            "inventory": self.inv.copy(),
            "metrics": self.metrics.summary(self.cfg),
        }

    # ---------------- 便捷方法 ----------------
    def metrics_summary(self) -> Dict[str, float]:
        return self.metrics.summary(self.cfg)

    def set_inventory(self, inv: np.ndarray) -> None:
        self.inv = np.clip(np.asarray(inv, dtype=float), 0.0, self.capacity)
