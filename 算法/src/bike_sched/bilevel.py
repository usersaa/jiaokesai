"""双层固定点迭代（建模文档 10.5）。

下层：用户选择（ChoiceModel，含激励响应）
上层：PPO 调度策略

流程：
    p <- 初始券额
    repeat:
        ① 给定 p，运行/训练 PPO
        ② 评估，统计各点位未满足率
        ③ 按未满足率调整券额 scale
    until 收敛或达到迭代上限

说明：完整版应「给定 p 求下层均衡，再更新上层」；本实现用整日仿真替代
下层均衡求解，符合文档「结合仿真系统的启发式」的定位。
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .config import deep_update
from .env import CampusEnv
from .rl.evaluate import PPOPolicy, aggregate, evaluate_policy


def run_bilevel(
    cfg: Dict[str, Any],
    scenario,
    n_iter: int = 3,
    timesteps_per_iter: int = 20000,
    seed: int = 0,
    target_unmet: float = 0.05,
    tol: float = 0.01,
    train_fn: Optional[Callable] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """返回 history 与最优一轮的模型/配置。"""
    base_tiers = list(cfg["decision"]["coupon_tiers_yuan"])
    scale = 1.0
    history: List[Dict[str, Any]] = []
    best = None
    best_unmet = float("inf")

    if train_fn is None:
        from .rl.ppo import train_ppo

        def train_fn(c, sc, timesteps, seed):
            return train_ppo(c, sc, total_timesteps=timesteps, seed=seed)[0]

    for it in range(n_iter):
        cfg_i = copy.deepcopy(cfg)
        cfg_i["decision"]["coupon_tiers_yuan"] = [round(x * scale, 2) for x in base_tiers]

        model = train_fn(cfg_i, scenario, timesteps_per_iter, seed)
        policy = PPOPolicy(model)

        def env_factory(c=cfg_i):
            return CampusEnv(c, scenario, seed=seed)

        rows = evaluate_policy(env_factory, policy, seeds=[seed + 101, seed + 202])
        agg = aggregate(rows)
        unmet = float(agg.get("bike_shortage", 0.0)) / max(float(agg.get("demand_total", 1.0)), 1e-9)

        history.append({
            "iter": it,
            "coupon_scale": scale,
            "coupon_tiers": cfg_i["decision"]["coupon_tiers_yuan"],
            "unmet_rate": unmet,
            "unit_service_cost": agg.get("unit_service_cost", 0.0),
            "coupon_cost": agg.get("coupon_cost_yuan", 0.0),
            "service_rate": agg.get("service_rate", 0.0),
        })
        if verbose:
            print(f"[bilevel] iter={it} scale={scale:.2f} tiers={cfg_i['decision']['coupon_tiers_yuan']} "
                  f"unmet={unmet:.4f} cost={agg.get('unit_service_cost', 0):.3f}")

        if unmet < best_unmet:
            best_unmet = unmet
            best = {"model": model, "cfg": cfg_i, "metrics": agg, "iter": it}

        # 更新券额：未满足率高 -> 加大券额；过低 -> 减小
        if unmet > target_unmet:
            new_scale = min(scale * 1.25, 4.0)
        elif unmet < target_unmet * 0.5:
            new_scale = max(scale * 0.8, 0.2)
        else:
            break
        if abs(new_scale - scale) < tol:
            break
        scale = new_scale

    return {"history": history, "best": best}
