"""下层用户选择行为（建模文档第七章，依据李兴华 2020 式(16)(17)）。

- 移步意愿：kappa(dw) = exp(-lambda * dw)
- 竞争取车：f_j = n_j^avail / (n_j^avail + N_j)
- 激励作用：dw_eff = dw - p_j / VOT
- 月卡用户（1-gamma）不受价格激励影响，单次用户（gamma）受影响
"""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .entities import Scenario


class ChoiceModel:
    def __init__(self, cfg: Dict, scenario: Scenario):
        self.cfg = cfg
        self.sc = scenario
        self.lam = float(cfg["choice"]["lambda_per_min"])
        self.vot = max(float(cfg["choice"]["vot_yuan_per_min"]), 1e-6)
        self.gamma = float(cfg["system"]["gamma_single_ride"])
        self.walk_speed = float(cfg["demand"]["walk_speed_m_per_min"])
        self.max_walk = float(cfg["demand"]["max_walk_min"])
        self.competition = bool(cfg["choice"].get("competition", True))

        d = scenario.dist_m.astype(float)
        self.walk_time = d / max(self.walk_speed, 1e-6)
        np.fill_diagonal(self.walk_time, 0.0)

    # ---------------- 基础函数 ----------------
    def kappa(self, dw: np.ndarray | float) -> np.ndarray:
        """移步意愿（负指数）。"""
        return np.exp(-self.lam * np.asarray(dw, dtype=float))

    def pickup_prob(self, n_avail: np.ndarray, n_users: np.ndarray) -> np.ndarray:
        """竞争型取车概率 f_j。"""
        if not self.competition:
            return (n_avail > 0).astype(float)
        denom = n_avail.astype(float) + n_users.astype(float)
        return np.divide(n_avail.astype(float), denom,
                         out=np.zeros_like(denom), where=denom > 0)

    # ---------------- 需求再分配 ----------------
    def redirect(self, unmet: np.ndarray, n_avail: np.ndarray,
                 arriving: np.ndarray, prices: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
        """把未满足需求按移步意愿 + 激励 + 竞争概率再分配到邻点。

        参数
        ----
        unmet : (N,) 各点未满足的借车需求
        n_avail : (N,) 各点当前可用车
        arriving : (N,) 本步到达各点的用户数（用于竞争）
        prices : (N,) 各点券额（元）

        返回
        ----
        extra_borrowed : (N,) 各点额外承接的借车量（不超过可用车）
        coupon_cost : float 本步券支出
        redirect_matrix : (N, N) 从 i 转向 j 的人次
        """
        n = self.sc.n
        M = np.zeros((n, n), dtype=float)

        for i in range(n):
            if unmet[i] <= 1e-9:
                continue
            cand = (n_avail > 0) & (self.walk_time[i] <= self.max_walk)
            cand[i] = False
            if not np.any(cand):
                continue

            dw = self.walk_time[i][cand]
            kappa_nat = self.kappa(dw)
            p = prices[cand]
            kappa_coupon = self.kappa(np.maximum(dw - p / self.vot, 0.0))

            # 月卡用户不受价格影响，单次用户受激励影响
            mix = (1.0 - self.gamma) * kappa_nat + self.gamma * kappa_coupon
            f = self.pickup_prob(n_avail[cand], arriving[cand])
            w = mix * f
            s = float(w.sum())
            if s <= 1e-12:
                continue
            M[i, cand] = unmet[i] * (w / s)

        # 汇总到目标点，受剩余可用车限制
        extra = np.zeros(n, dtype=float)
        for j in range(n):
            if n_avail[j] <= 0:
                continue
            col = M[:, j]
            total = float(col.sum())
            if total <= 0:
                continue
            take = min(total, float(n_avail[j]))
            if total > 0:
                M[:, j] = col * (take / total)
            extra[j] = take

        # 券支出：单次用户占比 gamma × 实际承接量 × 券额
        coupon_cost = float(np.sum(M.sum(axis=0) * prices * self.gamma))
        return extra, coupon_cost, M
