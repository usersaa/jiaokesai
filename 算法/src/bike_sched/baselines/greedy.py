"""约束贪心基线：就近 + 最临界点位 + 最大数量。

同时作为「纯搬运」「纯激励」消融的实现基础：
    allow_truck=False -> 纯激励
    allow_coupon=False -> 纯搬运
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


class GreedyPolicy:
    name = "greedy"

    def __init__(
        self,
        allow_truck: bool = True,
        allow_coupon: bool = True,
        params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ):
        self.allow_truck = allow_truck
        self.allow_coupon = allow_coupon
        self.params = params or {}
        self.qty_pref = int(self.params.get("qty_pref", 1))
        self.coupon_tier = int(self.params.get("coupon_tier", 1))
        self.prefer = str(self.params.get("prefer", "truck"))
        if name:
            self.name = name
        elif not allow_coupon:
            self.name = "pure_truck"
        elif not allow_truck:
            self.name = "pure_coupon"

    def _truck_action(self, env) -> Optional[np.ndarray]:
        mode_mask, station_mask, _ = env._masks()
        if not mode_mask[1]:
            return None
        shortage, overfull, avail = env._critical()
        best = None
        for s in range(env.n):
            if not station_mask[s]:
                continue
            q = env._truck_qty(s, self.qty_pref)
            if q <= 0:
                continue
            travel = env.sm.truck_travel_min(env.truck.station, s)
            gap_s = max(env.delta * env.capacity[s] - avail[s], 0.0)
            gap_o = max(env.delta * env.capacity[s] - (env.capacity[s] - env.inv[s]), 0.0)
            score = max(gap_s, gap_o) / (1.0 + travel / 500.0)
            if best is None or score > best[0]:
                best = (score, s)
        if best is None:
            return None
        return np.array([1, best[1], self.qty_pref], dtype=np.int64)

    def _coupon_action(self, env) -> Optional[np.ndarray]:
        mode_mask, station_mask, _ = env._masks()
        if not mode_mask[2]:
            return None
        D = env._expected_demand()
        best = None
        for s in range(env.n):
            if not station_mask[s]:
                continue
            if not env._is_valid(2, s, self.coupon_tier):
                continue
            surplus = float(env.inv[s] - env.target[s])
            score = surplus + 0.1 * float(D[s])
            if best is None or score > best[0]:
                best = (score, s)
        if best is None:
            return None
        return np.array([2, best[1], self.coupon_tier], dtype=np.int64)

    def act(self, env, obs=None) -> np.ndarray:
        acts = []
        if self.allow_truck:
            acts.append(("truck", self._truck_action))
        if self.allow_coupon:
            acts.append(("coupon", self._coupon_action))
        if self.prefer == "coupon":
            acts.reverse()
        for _, fn in acts:
            a = fn(env)
            if a is not None:
                return a
        return np.array([0, 0, 0], dtype=np.int64)
