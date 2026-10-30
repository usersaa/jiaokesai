"""领域实体：站点、脉冲、运维车、场景。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class Station:
    """一个 P 点（虚拟桩停车点）。"""

    id: str
    name: str
    lng: float
    lat: float
    capacity: int
    func: str = "other"          # dorm/teach/canteen/library/gate/sport/other
    attraction: float = 0.5      # 目的地吸引量 A_j
    init_bikes: int = 0          # 当日初始车辆数
    target_bikes: float = 0.0    # 夜间静态调度的目标库存
    polygon: Optional[List[List[float]]] = None
    area_m2: Optional[float] = None


@dataclass
class Pulse:
    """一个需求脉冲。"""

    id: str
    start_min: int
    peak_min: int
    end_min: int
    width_min: float
    label: str = ""


@dataclass
class TruckState:
    """单辆运维车的状态。"""

    station: int = 0             # 当前所在站点索引
    load: int = 0                # 当前载车数
    busy_until: int = -1         # 忙碌到第几步（含）
    last_truck_mode: str = "none"  # pickup / dropoff / none


@dataclass
class Scenario:
    """一个完整算例：站点 + 脉冲 + 距离矩阵 + 配置。"""

    stations: List[Station]
    pulses: List[Pulse]
    dist_m: np.ndarray
    cfg: Dict[str, Any] = field(default_factory=dict)
    name: str = "synthetic"

    @property
    def n(self) -> int:
        return len(self.stations)

    @property
    def capacities(self) -> np.ndarray:
        return np.array([s.capacity for s in self.stations], dtype=np.int64)

    @property
    def attractions(self) -> np.ndarray:
        return np.array([s.attraction for s in self.stations], dtype=np.float64)

    @property
    def funcs(self) -> List[str]:
        return [s.func for s in self.stations]

    def init_inventory(self) -> np.ndarray:
        return np.array([s.init_bikes for s in self.stations], dtype=np.int64)
