from __future__ import annotations

import copy
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.config import ALGO_SRC, CONFIG_YAML, EXPERIMENTS_CSV, MODEL_PATH

if str(ALGO_SRC) not in sys.path:
    sys.path.insert(0, str(ALGO_SRC))

from bike_sched.baselines import GreedyPolicy, NoOpPolicy, RandomPolicy  # noqa: E402
from bike_sched.config import fmt_hhmm, load_config, pulses_from_config  # noqa: E402
from bike_sched.entities import Scenario as AlgoScenario  # noqa: E402
from bike_sched.entities import Station as AlgoStation  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402
from bike_sched.night import solve_night_rebalancing  # noqa: E402
from bike_sched.rl.evaluate import PPOPolicy  # noqa: E402
from bike_sched.utils.geo import distance_matrix  # noqa: E402

_CFG: Optional[Dict[str, Any]] = None
_MODEL = None
_MODEL_TRIED = False


def get_cfg() -> Dict[str, Any]:
    global _CFG
    if _CFG is None:
        _CFG = load_config(str(CONFIG_YAML))
    return copy.deepcopy(_CFG)


def apply_overrides(cfg: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    if not overrides:
        return cfg
    o = overrides
    if "lambda_per_min" in o:
        cfg["choice"]["lambda_per_min"] = float(o["lambda_per_min"])
    if "vot_yuan_per_min" in o:
        cfg["choice"]["vot_yuan_per_min"] = float(o["vot_yuan_per_min"])
    if "gamma_single_ride" in o:
        cfg["system"]["gamma_single_ride"] = float(o["gamma_single_ride"])
    if "rho_soc" in o:
        cfg["system"]["rho_soc"] = float(o["rho_soc"])
    if "pulse_gain" in o:
        cfg["demand"]["pulse_gain"] = float(o["pulse_gain"])
    if "noise_cv" in o:
        cfg["demand"]["noise_cv"] = float(o["noise_cv"])
    if "weekend_factor" in o:
        cfg["demand"]["weekend_factor"] = float(o["weekend_factor"])
    return cfg


def build_scenario(stations, cfg: Dict[str, Any]) -> AlgoScenario:
    algo_stations = [
        AlgoStation(
            id=s.id,
            name=s.name or s.id,
            lng=float(s.lng),
            lat=float(s.lat),
            capacity=int(s.capacity),
            func=s.func or "other",
            attraction=float(s.attraction or 0.5),
            init_bikes=int(s.init_bikes or 0),
            target_bikes=float(s.target_bikes or s.capacity * 0.5),
        )
        for s in stations
    ]
    dist = distance_matrix([s.lng for s in algo_stations], [s.lat for s in algo_stations])
    return AlgoScenario(
        stations=algo_stations,
        pulses=pulses_from_config(cfg),
        dist_m=dist,
        cfg=cfg,
        name="system",
    )


def get_model():
    global _MODEL, _MODEL_TRIED
    if _MODEL_TRIED:
        return _MODEL
    _MODEL_TRIED = True
    if not MODEL_PATH.exists():
        return None
    try:
        from sb3_contrib import MaskablePPO

        _MODEL = MaskablePPO.load(str(MODEL_PATH), device="cpu")
    except Exception as exc:  # pragma: no cover
        print(f"[algorithm] 模型加载失败，回退贪心：{exc}")
        _MODEL = None
    return _MODEL


def make_policy(name: str, scenario: AlgoScenario):
    name = (name or "ppo").lower()
    if name == "ppo":
        model = get_model()
        if model is not None and scenario.n == 12:
            return PPOPolicy(model)
        return GreedyPolicy(name="ppo")
    if name == "greedy":
        return GreedyPolicy()
    if name == "pure_truck":
        return GreedyPolicy(allow_coupon=False, name="pure_truck")
    if name == "pure_coupon":
        return GreedyPolicy(allow_truck=False, name="pure_coupon")
    if name == "random":
        return RandomPolicy(seed=0)
    return NoOpPolicy()


def _describe(env: CampusEnv, mode: int, station: int, tier: int) -> str:
    sid = env.sc.stations[station].id if 0 <= station < env.n else "—"
    if mode == 1:
        qty = env.qty_tiers[tier]
        direction = env.truck.last_truck_mode
        verb = "调入" if direction == "dropoff" else "调出" if direction == "pickup" else "搬运"
        return f"{sid} {verb} {qty} 辆"
    if mode == 2:
        return f"{sid} 发券 {env.coupon_tiers[tier]:.1f} 元"
    return "等待"


def _snapshot(env: CampusEnv, action, reward: float, info: Dict[str, Any],
              step_idx: Optional[int] = None) -> Dict[str, Any]:
    if step_idx is None:
        step_idx = max(env.step_idx - 1, 0)
    step_idx = int(min(step_idx, len(env.grid) - 1))
    if action is None:
        mode, station, tier = 0, 0, 0
    else:
        mode, station, tier = env._decode(action)
    inv = np.asarray(info.get("inventory", env.inv), dtype=float)
    return {
        "step": step_idx,
        "time": fmt_hhmm(env.grid[step_idx]),
        "inventory": [round(float(x), 1) for x in inv],
        "action": {
            "mode": int(mode),
            "station": int(station),
            "tier": int(tier),
            "valid": bool(info.get("valid", True)),
            "label": _describe(env, mode, station, tier),
        },
        "truck": {
            "station": int(info.get("truck_station", 0)),
            "load": int(info.get("truck_load", 0)),
            "busy": bool(info.get("truck_busy_until", -1) >= step_idx),
        },
        "metrics": info.get("metrics", {}),
        "reward": info.get("reward_breakdown", {}),
    }


def run_day(stations, policy_name: str = "ppo", seed: int = 101,
            overrides: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], Dict, Dict]:
    cfg = apply_overrides(get_cfg(), overrides or {})
    scenario = build_scenario(stations, cfg)
    env = CampusEnv(cfg, scenario, seed=seed)
    policy = make_policy(policy_name, scenario)
    obs, info = env.reset(seed=seed)
    steps = [_snapshot(env, None, 0.0, info, step_idx=0)]
    done = False
    while not done:
        try:
            action = policy.act(env, obs)
        except Exception:
            action = np.array([0, 0, 0])
        obs, reward, term, trunc, info = env.step(action)
        done = bool(term or trunc)
        steps.append(_snapshot(env, action, reward, info))
    return steps, env.metrics_summary(), cfg


def station_dicts(stations) -> List[Dict[str, Any]]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "lng": s.lng,
            "lat": s.lat,
            "capacity": s.capacity,
            "func": s.func,
            "init_bikes": s.init_bikes,
        }
        for s in stations
    ]


def read_compare() -> List[Dict[str, Any]]:
    if not EXPERIMENTS_CSV.exists():
        return []
    try:
        import pandas as pd

        df = pd.read_csv(EXPERIMENTS_CSV)
        keep = [c for c in [
            "policy", "service_rate", "total_shortage", "unit_service_cost",
            "truck_trips", "bike_shortage", "return_shortage", "coupon_cost_yuan",
            "truck_time_min", "imbalance_point", "imbalance_flow",
        ] if c in df.columns]
        return df[keep].round(4).to_dict(orient="records")
    except Exception:
        return []


def quick_compare(stations, seed: int = 101) -> List[Dict[str, Any]]:
    rows = []
    for name in ["noop", "greedy", "pure_truck", "pure_coupon", "ppo"]:
        _, summary, _ = run_day(stations, policy_name=name, seed=seed)
        rows.append({
            "policy": name,
            "service_rate": round(float(summary.get("service_rate", 0)), 4),
            "total_shortage": round(float(summary.get("total_shortage", 0)), 2),
            "unit_service_cost": round(float(summary.get("unit_service_cost", 0)), 4),
            "truck_trips": int(summary.get("truck_trips", 0)),
            "bike_shortage": round(float(summary.get("bike_shortage", 0)), 2),
            "return_shortage": round(float(summary.get("return_shortage", 0)), 2),
        })
    return rows


def run_night(stations, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = apply_overrides(get_cfg(), overrides or {})
    scenario = build_scenario(stations, cfg)
    res = solve_night_rebalancing(cfg, scenario, time_limit_s=20)
    if res.get("feasible"):
        res["station_ids"] = [s.id for s in scenario.stations]
        res["station_names"] = [s.name for s in scenario.stations]
    return res
