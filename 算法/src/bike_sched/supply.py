"""供给侧模型（建模文档第六章）。"""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .entities import Scenario


class SupplyModel:
    def __init__(self, cfg: Dict, scenario: Scenario):
        self.cfg = cfg
        self.sc = scenario
        self.step_min = float(cfg["time"]["step_minutes"])
        self.rho_soc = float(cfg["system"]["rho_soc"])
        self.v_truck_kmh = float(cfg["truck"]["speed_kmh"])
        self.load_min = float(cfg["truck"]["load_min_per_bike"])
        self.swap_min = float(cfg["truck"]["swap_minutes_per_step"])
        self.capacity = scenario.capacities
        self.dist = scenario.dist_m

    # ---------------- 可用车 ----------------
    def available(self, n: np.ndarray) -> np.ndarray:
        """账面车辆数 -> 实际可用车数（电量/故障折减，聚合为 rho_soc）。"""
        return np.maximum(np.round(n * self.rho_soc), 0).astype(np.int64)

    # ---------------- 借还 ----------------
    def borrow(self, D: np.ndarray, n_avail: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """实际借出 b_i = min(D_i, n_avail_i)，以及借车短缺 e_i^b。"""
        b = np.minimum(D, n_avail.astype(float))
        e_b = np.maximum(D - b, 0.0)
        return b, e_b

    def returns(self, realized_od: np.ndarray) -> np.ndarray:
        """实际还入 r_i = sum_j Q_ji（校园骑行 < 10 min，忽略时滞）。"""
        return realized_od.sum(axis=0)

    def return_free_space(self, n: np.ndarray, borrowed: np.ndarray,
                          extra_borrowed: np.ndarray) -> np.ndarray:
        """还车可用空位 = L_i - n_i + 借出 + 额外承接。"""
        return np.maximum(self.capacity - n + borrowed + extra_borrowed, 0.0)

    def return_shortage(self, returns: np.ndarray, free_space: np.ndarray) -> np.ndarray:
        """还车短缺 e_i^r = max(0, r_i - 空位)。"""
        return np.maximum(returns - free_space, 0.0)

    # ---------------- 作业时间 ----------------
    def truck_travel_min(self, i: int, j: int) -> float:
        return float(self.dist[i, j]) / max(self.v_truck_kmh * 1000.0 / 60.0, 1e-9)

    def truck_service_min(self, i: int, j: int, q: int) -> float:
        """L3 式(5)：tau_ij = d_ij / v_truck + |q| * t_load。"""
        return self.truck_travel_min(i, j) + abs(int(q)) * self.load_min

    def available_truck_min(self) -> float:
        """单步可用作业时间 = 步长 - 换电占用。"""
        return max(self.step_min - self.swap_min, 0.0)

    def busy_steps(self, service_min: float) -> int:
        """作业时间换算为忙碌步数（向上取整）。"""
        return max(int(np.ceil(service_min / max(self.step_min, 1e-9))), 1)
