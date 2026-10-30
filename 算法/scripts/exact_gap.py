"""小规模精确解对照：3 个 P 点 × 4 个决策步。

做法：
  - 关闭需求噪声与发券，只保留 wait / 搬运；
  - 用动态规划穷举状态（库存、卡车位置、载量、忙标志、上一步方向）；
  - 在同一实例上评估贪心与 PPO，报告相对精确最优的 gap。

用法：
    python scripts/exact_gap.py
"""
from __future__ import annotations

import copy
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.baselines import GreedyPolicy  # noqa: E402
from bike_sched.config import load_config, time_grid  # noqa: E402
from bike_sched.entities import Scenario  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402
from bike_sched.rl.evaluate import PPOPolicy, run_episode  # noqa: E402
from bike_sched.rl.ppo import train_ppo  # noqa: E402
from bike_sched.scenario import make_synthetic_scenario  # noqa: E402


def make_tiny(cfg):
    """取 3 个点（宿舍/教学/食堂），窗口 07:40–08:20（4 步）。"""
    cfg_t = copy.deepcopy(cfg)
    cfg_t["time"]["day_start"] = "07:40"
    cfg_t["time"]["day_end"] = "08:20"
    cfg_t["demand"]["noise_cv"] = 0.0
    cfg_t["decision"]["coupon_budget_daily"] = 0.0
    cfg_t["truck"]["capacity"] = 8

    sc = make_synthetic_scenario(cfg_t)
    idx = [0, 3, 7]  # P01 宿舍, P04 教学, P08 食堂
    stations = []
    for i in idx:
        s = copy.deepcopy(sc.stations[i])
        s.capacity = min(s.capacity, 12)
        s.init_bikes = min(s.init_bikes, 8)
        s.target_bikes = s.capacity * 0.5
        stations.append(s)
    dist = sc.dist_m[np.ix_(idx, idx)]
    return cfg_t, Scenario(stations, sc.pulses, dist, cfg_t, "tiny")


def _key(env):
    return (
        env.step_idx,
        tuple(np.round(env.inv, 3)),
        env.truck.station,
        env.truck.load,
        env.truck.busy_until,
        env.truck.last_truck_mode,
        round(env.coupon_used, 3),
    )


def _snapshot(env):
    return (
        env.inv.copy(), env.truck.station, env.truck.load,
        env.truck.busy_until, env.truck.last_truck_mode,
        env.coupon_used, env.step_idx, env.prices.copy(),
    )


def _restore(env, s):
    env.inv = s[0].copy()
    env.truck.station = s[1]
    env.truck.load = s[2]
    env.truck.busy_until = s[3]
    env.truck.last_truck_mode = s[4]
    env.coupon_used = s[5]
    env.step_idx = s[6]
    env.prices = s[7].copy()


def exact_dp(cfg, sc, max_nodes: int = 2_000_000):
    env = CampusEnv(cfg, sc, seed=0)
    env.noise_cv = 0.0
    memo = {}
    nodes = {"n": 0}

    def dp(env):
        if env.step_idx >= env.T:
            return 0.0, []
        k = _key(env)
        if k in memo:
            return memo[k]
        nodes["n"] += 1
        if nodes["n"] > max_nodes:
            raise RuntimeError("DP 状态数超过上限，请缩小实例")

        mask = env.valid_action_mask_flat()
        valid = np.flatnonzero(mask)
        best_val, best_seq = -1e18, []
        snap = _snapshot(env)
        n2 = env.n * 2
        for idx in valid:
            mode = int(idx) // n2
            rem = int(idx) % n2
            station, tier = rem // 2, rem % 2
            _, r, term, trunc, _ = env.step([mode, station, tier])
            tail_val, tail_seq = dp(env)
            total = float(r) + tail_val
            if total > best_val:
                best_val, best_seq = total, [int(idx)] + tail_seq
            _restore(env, snap)
        memo[k] = (best_val, best_seq)
        return memo[k]

    env.reset(seed=0)
    val, seq = dp(env)
    return val, seq, nodes["n"], len(memo)


def main() -> None:
    cfg = load_config("configs/default.yaml")
    cfg_t, sc_t = make_tiny(cfg)

    print(f"[tiny] stations={sc_t.n} steps={len(time_grid(cfg_t))} "
          f"caps={sc_t.capacities.tolist()} init={sc_t.init_inventory().tolist()}")

    print("[exact] DP ...")
    opt_val, opt_seq, nodes, states = exact_dp(cfg_t, sc_t)
    print(f"  optimal reward={opt_val:.4f} nodes={nodes} states={states}")

    # 贪心
    env_g = CampusEnv(cfg_t, sc_t, seed=0)
    env_g.noise_cv = 0.0
    m_g = run_episode(env_g, GreedyPolicy(allow_truck=True, allow_coupon=False, name="pure_truck"), seed=0)

    # 小规模 PPO
    print("[ppo] tiny training ...")
    model, _ = train_ppo(cfg_t, sc_t, total_timesteps=30000, seed=0)
    env_p = CampusEnv(cfg_t, sc_t, seed=0)
    env_p.noise_cv = 0.0
    m_p = run_episode(env_p, PPOPolicy(model), seed=0)

    # 用同一目标函数（奖励）比较：这里用 -总成本 近似；精确 DP 给的是累计奖励
    # 贪心/PPO 的累计奖励需重新跑一遍记录 reward
    def total_reward(env, policy):
        obs, info = env.reset(seed=0)
        done, total = False, 0.0
        while not done:
            a = policy.act(env, obs)
            obs, r, term, trunc, info = env.step(a)
            total += float(r)
            done = bool(term or trunc)
        return total

    g_rew = total_reward(CampusEnv(cfg_t, sc_t, seed=0), GreedyPolicy(allow_truck=True, allow_coupon=False))
    p_rew = total_reward(CampusEnv(cfg_t, sc_t, seed=0), PPOPolicy(model))

    def gap(v):
        return (opt_val - v) / max(abs(opt_val), 1e-9)

    out = {
        "instance": {
            "stations": [s.id for s in sc_t.stations],
            "caps": sc_t.capacities.tolist(),
            "init": sc_t.init_inventory().tolist(),
            "steps": 4,
            "truck_capacity": int(cfg_t["truck"]["capacity"]),
            "coupon": False,
        },
        "exact": {"reward": opt_val, "sequence": opt_seq, "dp_states": states},
        "greedy": {"reward": g_rew, "gap": gap(g_rew),
                   "metrics": m_g},
        "ppo": {"reward": p_rew, "gap": gap(p_rew),
                "metrics": m_p},
    }
    os.makedirs("outputs/exact", exist_ok=True)
    with open("outputs/exact/exact_gap.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in ["exact", "greedy", "ppo"]}, ensure_ascii=False, indent=2))
    print("[done] -> outputs/exact/exact_gap.json")


if __name__ == "__main__":
    main()
