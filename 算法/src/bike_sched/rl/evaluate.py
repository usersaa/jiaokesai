"""策略评估与统一 rollout。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np


class PPOPolicy:
    """把 SB3 模型包装成与基线一致的 policy 接口。"""

    name = "ppo"

    def __init__(self, model, deterministic: bool = True):
        self.model = model
        self.deterministic = deterministic

    def act(self, env, obs=None) -> np.ndarray:
        if obs is None:
            raise ValueError("PPOPolicy 需要显式传入 obs")
        masks = env.action_masks() if hasattr(env, "action_masks") else None
        a, _ = self.model.predict(obs, action_masks=masks, deterministic=self.deterministic)
        return np.asarray(a).reshape(-1)


def run_episode(env, policy, seed: Optional[int] = None, day_type: int = 0) -> Dict[str, float]:
    """跑完一天，返回指标汇总。"""
    obs, info = env.reset(seed=seed, options={"day_type": day_type})
    done = False
    while not done:
        action = policy.act(env, obs)
        obs, reward, terminated, truncated, info = env.step(action)
        done = bool(terminated or truncated)
    out = env.metrics_summary()
    out["seed"] = -1 if seed is None else int(seed)
    out["day_type"] = int(day_type)
    return out


def evaluate_policy(
    env_factory: Callable[[], Any],
    policy,
    seeds: Iterable[int],
    day_types: Iterable[int] = (0,),
) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for seed in seeds:
        for dt in day_types:
            env = env_factory()
            m = run_episode(env, policy, seed=int(seed), day_type=int(dt))
            m["policy"] = getattr(policy, "name", policy.__class__.__name__)
            rows.append(m)
    return rows


def aggregate(rows: List[Dict[str, float]]) -> Dict[str, float]:
    """对多次评估做均值/标准差汇总（忽略非数值列）。"""
    if not rows:
        return {}
    keys = [k for k, v in rows[0].items() if isinstance(v, (int, float))]
    out: Dict[str, float] = {}
    for k in keys:
        vals = np.array([float(r[k]) for r in rows], dtype=float)
        out[k] = float(vals.mean())
        out[k + "_std"] = float(vals.std(ddof=0))
    return out
