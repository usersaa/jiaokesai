"""模拟退火基线。

说明：Staffolani 2025 的 SA 直接扰动「一天的动作序列」；本实现为可运行性，
改为扰动「参数化贪心策略」的参数（临界阈值偏移、数量档、券档、优先通道），
用同一目标函数评估整日 episode。这是元启发式基线的一种可复现简化，
论文中须如实说明。
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional

import numpy as np

from .greedy import GreedyPolicy


class SimulatedAnnealingPolicy:
    name = "sa"

    def __init__(
        self,
        env_factory: Callable[[], Any],
        seed: int = 0,
        iterations: int = 60,
        init_temp: float = 1.0,
        cooling: float = 0.95,
        eval_seed: int = 12345,
    ):
        self.env_factory = env_factory
        self.rng = np.random.default_rng(seed)
        self.iterations = int(iterations)
        self.init_temp = float(init_temp)
        self.cooling = float(cooling)
        self.eval_seed = int(eval_seed)
        self.params: Dict[str, Any] = {
            "delta_offset": 0.0, "qty_pref": 1, "coupon_tier": 1, "prefer": "truck"
        }
        self.best_score = -1e18
        self.history = []

    # ---------------- 评估 ----------------
    def _evaluate(self, params: Dict[str, Any]) -> float:
        env = self.env_factory()
        base_delta = env.delta
        env.delta = float(np.clip(base_delta + params["delta_offset"], 0.05, 0.6))
        policy = GreedyPolicy(
            allow_truck=True, allow_coupon=True, params=params, name="sa"
        )
        obs, info = env.reset(seed=self.eval_seed)
        done = False
        total = 0.0
        while not done:
            a = policy.act(env, obs)
            obs, r, term, trunc, info = env.step(a)
            total += r
            done = term or trunc
        env.delta = base_delta
        return float(total)

    # ---------------- 退火 ----------------
    def _perturb(self, p: Dict[str, Any]) -> Dict[str, Any]:
        q = dict(p)
        q["delta_offset"] = float(np.clip(
            q["delta_offset"] + self.rng.normal(0, 0.04), -0.15, 0.25
        ))
        if self.rng.random() < 0.25:
            q["qty_pref"] = 1 - int(q["qty_pref"])
        if self.rng.random() < 0.25:
            q["coupon_tier"] = 1 - int(q["coupon_tier"])
        if self.rng.random() < 0.15:
            q["prefer"] = "coupon" if q["prefer"] == "truck" else "truck"
        return q

    def fit(self) -> Dict[str, Any]:
        cur = dict(self.params)
        cur_score = self._evaluate(cur)
        self.best_score, self.params = cur_score, dict(cur)
        temp = self.init_temp
        for it in range(self.iterations):
            cand = self._perturb(cur)
            score = self._evaluate(cand)
            if score >= cur_score or self.rng.random() < math.exp((score - cur_score) / max(temp, 1e-9)):
                cur, cur_score = cand, score
            if score > self.best_score:
                self.best_score, self.params = score, dict(cand)
            self.history.append({"iter": it, "score": score, "best": self.best_score, "temp": temp})
            temp *= self.cooling
        return self.params

    def act(self, env, obs=None) -> np.ndarray:
        policy = GreedyPolicy(allow_truck=True, allow_coupon=True,
                              params=self.params, name="sa")
        return policy.act(env, obs)
