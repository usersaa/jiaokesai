"""需求侧模型（建模文档第五章）。

真实借车需求：
    D_i^b(t) = B_i * h(t) + sum_r A_i^r * phi((t - t_r) / w_r)

OD 分布（胡宝雨 2024 的思路，略去拥堵指数）：
    q_ij(t) = D_i^b(t) * [A_j * f(d_ij)] / sum_{k != i} [A_k * f(d_ik)]

关键立场（桂志鹏 2026）：历史订单是供给约束下的观测值，会低估真实需求。
因此本模块输出的是「真实需求」，供给截断在 supply 模块中处理。
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .config import time_grid
from .entities import Scenario


class DemandModel:
    def __init__(self, cfg: Dict, scenario: Scenario):
        self.cfg = cfg
        self.sc = scenario
        self.step_min = int(cfg["time"]["step_minutes"])
        self.grid = time_grid(cfg)
        self.pulses = scenario.pulses
        self.n = scenario.n
        self.r = len(self.pulses)

        self.attr = scenario.attractions
        self.attr_norm = self.attr / max(float(self.attr.mean()), 1e-9)
        self.dist = scenario.dist_m

        self.intensity = cfg["demand"]["function_origin_intensity"]
        self._fallback_intensity = {
            "P1": 0.2, "P2": 0.2, "P3": 0.2, "P4": 0.2,
            "P5": 0.2, "P6": 0.2, "P7": 0.2,
        }

        self.kernel = str(cfg["demand"].get("kernel", "gaussian")).lower()
        self.f_dist = self._build_distance_kernel()
        self.baseline = self._build_baseline()
        self.A = self._build_pulse_amplitude()

        self.pulse_centers = np.array([p.peak_min for p in self.pulses], dtype=float)
        self.pulse_widths = np.array([p.width_min for p in self.pulses], dtype=float)

    # ---------------- 构造 ----------------
    def _build_distance_kernel(self) -> np.ndarray:
        d = self.dist.astype(float).copy()
        np.fill_diagonal(d, np.inf)
        dec = self.cfg["demand"]["distance_decay"]
        d0 = float(dec["d0_m"])
        if str(dec.get("type", "lognormal")).lower() == "lognormal":
            sigma = float(dec.get("sigma", 0.8))
            f = np.exp(-0.5 * (np.log(np.maximum(d, 1.0) / d0) / sigma) ** 2)
        else:
            f = np.exp(-d / d0)
        f[~np.isfinite(f)] = 0.0
        np.fill_diagonal(f, 0.0)
        return f

    def _build_baseline(self) -> np.ndarray:
        rate = float(self.cfg["demand"]["baseline_rate_per_hour"])
        dt_h = self.step_min / 60.0
        return rate * dt_h * self.attr_norm

    def _build_pulse_amplitude(self) -> np.ndarray:
        rate = float(self.cfg["demand"]["baseline_rate_per_hour"])
        gain = float(self.cfg["demand"].get("pulse_gain", 8.0))
        dt_h = self.step_min / 60.0
        A = np.zeros((self.n, self.r), dtype=float)
        for i, st in enumerate(self.sc.stations):
            row = self.intensity.get(st.func, self._fallback_intensity)
            for r, p in enumerate(self.pulses):
                A[i, r] = rate * dt_h * gain * float(row.get(p.id, 0.2)) * self.attr_norm[i]
        return A

    # ---------------- 需求 ----------------
    def smoothing(self, minute: int) -> float:
        """日内平滑因子 h(t)。"""
        if minute < 8 * 60 or minute >= 22 * 60 + 30:
            return float(self.cfg["demand"]["smooth_night"])
        return float(self.cfg["demand"]["smooth_day"])

    def _kernel_value(self, x: np.ndarray) -> np.ndarray:
        if self.kernel == "exponential":
            return np.exp(-np.abs(x))
        return np.exp(-0.5 * x ** 2)

    def true_demand(self, step: int) -> np.ndarray:
        """第 step 步各站点的真实借车需求 D_i^b(t)。"""
        t = self.grid[step] + self.step_min / 2.0
        D = self.baseline * self.smoothing(int(t))
        for r in range(self.r):
            x = (t - self.pulse_centers[r]) / max(self.pulse_widths[r], 1e-6)
            D = D + self.A[:, r] * self._kernel_value(np.array([x]))[0]
        return np.maximum(D, 0.0)

    def demand_matrix(self, n_steps: int) -> np.ndarray:
        """(n_steps, N) 的整日需求矩阵，便于批量分析。"""
        return np.vstack([self.true_demand(t) for t in range(n_steps)])

    # ---------------- OD ----------------
    def od_probabilities(self) -> np.ndarray:
        """目的地选择概率矩阵 P[i, j]。"""
        W = self.f_dist * self.attr[None, :]
        rs = W.sum(axis=1, keepdims=True)
        P = np.divide(W, rs, out=np.zeros_like(W), where=rs > 0)
        # 极端情况：所有目的地权重为 0 -> 均匀分给其他站点
        bad = (rs[:, 0] <= 0)
        if np.any(bad):
            n = self.n
            for i in np.where(bad)[0]:
                P[i, :] = 1.0 / max(n - 1, 1)
                P[i, i] = 0.0
        return P

    def od_matrix(self, D: np.ndarray) -> np.ndarray:
        """由借车需求生成 OD 矩阵 q_ij(t)。"""
        return D[:, None] * self.od_probabilities()

    def realized_od(self, od: np.ndarray, borrowed: np.ndarray, D: np.ndarray) -> np.ndarray:
        """按实际借出量对 OD 做等比缩放（需求被供给截断）。"""
        scale = np.divide(borrowed, D, out=np.zeros_like(borrowed), where=D > 0)
        return od * scale[:, None]

    def pulse_flag(self, step: int) -> float:
        """当前步是否处于任一脉冲窗口内（0/1）。"""
        t = self.grid[step] + self.step_min / 2.0
        for p in self.pulses:
            if p.start_min <= t <= p.end_min:
                return 1.0
        return 0.0

    def pulse_phase(self, step: int) -> float:
        """当前步在最近脉冲内的相对相位 [0,1]；不在脉冲内为 0。"""
        t = self.grid[step] + self.step_min / 2.0
        best = None
        for p in self.pulses:
            if p.start_min <= t <= p.end_min:
                span = max(p.end_min - p.start_min, 1e-6)
                best = (t - p.start_min) / span
        return float(best) if best is not None else 0.0
