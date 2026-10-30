"""奖励函数（建模文档 8.1 / 9.3，依据 Staffolani 2025 式(6)(10)）。

r_t = -[ w1 * E_agent + w2 * E_env + w3 * T_truck + w4 * P_inc ]

各项先按尺度归一化，避免量纲差异导致某一项主导。
"""
from __future__ import annotations

from typing import Dict


def compute_reward(
    e_agent: float,
    e_env: float,
    truck_time: float,
    coupon_cost: float,
    cfg: Dict,
) -> float:
    w = cfg["cost"]["weights"]
    s = cfg["cost"]["normalize"]

    agent_term = float(w["agent"]) * float(e_agent) / max(float(s["shortage_scale"]), 1e-9)
    env_term = float(w["env"]) * float(e_env) / max(float(s["shortage_scale"]), 1e-9)
    truck_term = float(w["truck"]) * float(truck_time) / max(float(s["truck_time_scale"]), 1e-9)
    inc_term = float(w["incentive"]) * float(coupon_cost) / max(float(s["incentive_scale"]), 1e-9)

    return -(agent_term + env_term + truck_term + inc_term)


def reward_breakdown(
    e_agent: float,
    e_env: float,
    truck_time: float,
    coupon_cost: float,
    cfg: Dict,
) -> Dict[str, float]:
    """返回奖励各分项，便于日志与论文作图。"""
    w = cfg["cost"]["weights"]
    s = cfg["cost"]["normalize"]
    parts = {
        "agent": float(w["agent"]) * float(e_agent) / max(float(s["shortage_scale"]), 1e-9),
        "env": float(w["env"]) * float(e_env) / max(float(s["shortage_scale"]), 1e-9),
        "truck": float(w["truck"]) * float(truck_time) / max(float(s["truck_time_scale"]), 1e-9),
        "incentive": float(w["incentive"]) * float(coupon_cost) / max(float(s["incentive_scale"]), 1e-9),
    }
    parts["total"] = -sum(parts.values())
    return parts
