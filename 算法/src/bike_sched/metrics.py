"""评价指标（建模文档第十一章）。

八项指标：
  1. 借车短缺次数
  2. 还车短缺次数
  3. 搬运趟次
  4. 搬运作业时间
  5. 单位服务成本
  6. 点供需失衡指数（桂志鹏 式(3)）
  7. 流供需失衡指数（桂志鹏 式(1)，含距离权重）
  8. 智能体导致短缺 / 环境赤字（Staffolani 式(10)）
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict

import numpy as np


@dataclass
class EpisodeMetrics:
    steps: int = 0
    demand_total: float = 0.0
    served_rides: float = 0.0

    bike_shortage: float = 0.0
    return_shortage: float = 0.0

    truck_trips: int = 0
    truck_time: float = 0.0
    coupon_cost: float = 0.0

    agent_shortage: float = 0.0
    env_deficit: float = 0.0

    # 失衡指数：按步累计分子/分母，最后取均值
    imbalance_point_num: float = 0.0
    imbalance_point_den: int = 0
    imbalance_flow_num: float = 0.0
    imbalance_flow_den: float = 0.0

    def add_step(
        self,
        *,
        demand: np.ndarray,
        served: float,
        e_b: np.ndarray,
        e_r: np.ndarray,
        n_avail: np.ndarray,
        free_space: np.ndarray,
        od: np.ndarray,
        agent_shortage: float,
        env_deficit: float,
        truck_time: float,
        truck_trip: int,
        coupon_cost: float,
        dist_weight: np.ndarray,
    ) -> None:
        self.steps += 1
        self.demand_total += float(np.sum(demand))
        self.served_rides += float(served)
        self.bike_shortage += float(np.sum(e_b))
        self.return_shortage += float(np.sum(e_r))
        self.truck_time += float(truck_time)
        self.truck_trips += int(truck_trip)
        self.coupon_cost += float(coupon_cost)
        self.agent_shortage += float(agent_shortage)
        self.env_deficit += float(env_deficit)

        # 点失衡：D_i / S_i，S_i 用可用车 + 1 平滑
        mask = demand > 1e-9
        if np.any(mask):
            ratio = demand[mask] / (n_avail[mask] + 1.0)
            self.imbalance_point_num += float(np.mean(np.minimum(ratio, 50.0)))
            self.imbalance_point_den += 1

        # 流失衡：q_ij / min(起点可用车, 终点空位)，按 q_ij 加权
        q = od
        total_q = float(q.sum())
        if total_q > 1e-9:
            cap = np.minimum(n_avail[:, None], free_space[None, :])
            ratio = np.divide(q, cap + 1.0, out=np.zeros_like(q), where=q > 0)
            w = q / total_q
            self.imbalance_flow_num += float(np.sum(np.minimum(ratio, 50.0) * w))
            self.imbalance_flow_den += 1.0

    # ---------------- 汇总 ----------------
    def summary(self, cfg: Dict) -> Dict[str, float]:
        c = cfg["cost"]
        truck_cost = self.truck_time * float(c["c_truck_min"])
        total_cost = truck_cost + self.coupon_cost * float(c["c_coupon_per_yuan"])
        served = max(self.served_rides, 1e-9)
        return {
            "steps": self.steps,
            "demand_total": self.demand_total,
            "served_rides": self.served_rides,
            "service_rate": self.served_rides / max(self.demand_total, 1e-9),
            "bike_shortage": self.bike_shortage,
            "return_shortage": self.return_shortage,
            "total_shortage": self.bike_shortage + self.return_shortage,
            "truck_trips": self.truck_trips,
            "truck_time_min": self.truck_time,
            "coupon_cost_yuan": self.coupon_cost,
            "total_cost_yuan": total_cost,
            "unit_service_cost": total_cost / served,
            "agent_shortage": self.agent_shortage,
            "env_deficit": self.env_deficit,
            "imbalance_point": (self.imbalance_point_num / self.imbalance_point_den
                                if self.imbalance_point_den else 0.0),
            "imbalance_flow": (self.imbalance_flow_num / self.imbalance_flow_den
                               if self.imbalance_flow_den else 0.0),
        }

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def distance_weight_matrix(dist_m: np.ndarray, alpha_m: float = 400.0) -> np.ndarray:
    """桂志鹏 式(1) 的距离权重 q = d / (d + alpha)。"""
    d = dist_m.astype(float)
    return d / (d + float(alpha_m) + 1e-9)
