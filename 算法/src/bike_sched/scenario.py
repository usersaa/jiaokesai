"""场景构建：合成占位算例与 CSV 载入。"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import numpy as np

from .config import pulses_from_config
from .entities import Scenario, Station
from .utils.geo import distance_matrix, load_stations_csv

# 12 个占位 P 点：名称、功能、容量、相对校区中心的偏移（米）
# [TODO] 待用小程序地图 + 实地踏勘替换为真实点位
_SYNTHETIC_STATIONS = [
    ("P01", "北苑公寓1号楼", "dorm", 50, -320, 360),
    ("P02", "北苑公寓7号楼", "dorm", 55, -160, 430),
    ("P03", "南苑公寓3号楼", "dorm", 45, -260, -300),
    ("P04", "笃行楼", "teach", 70, 350, 300),
    ("P05", "1-7号楼", "teach", 60, 300, 180),
    ("P06", "田家炳教学楼", "teach", 65, 450, 80),
    ("P07", "实验楼", "teach", 50, 250, -120),
    ("P08", "第一食堂", "canteen", 55, 50, 150),
    ("P09", "第二食堂", "canteen", 45, -80, -80),
    ("P10", "图书馆", "library", 60, 120, 20),
    ("P11", "南门", "gate", 40, 0, -450),
    ("P12", "运动场", "sport", 45, 500, -250),
]

_M_PER_DEG_LAT = 111320.0


def _offset_to_lnglat(lng0: float, lat0: float, dx_m: float, dy_m: float):
    lat = lat0 + dy_m / _M_PER_DEG_LAT
    lng = lng0 + dx_m / (_M_PER_DEG_LAT * np.cos(np.radians(lat0)))
    return float(lng), float(lat)


def make_synthetic_scenario(cfg: Dict[str, Any], name: str = "synthetic") -> Scenario:
    """生成 12 个占位 P 点的算例。数据缺失时用于跑通全链路。"""
    center = cfg["campus"]
    lng0, lat0 = float(center["center_lng"]), float(center["center_lat"])
    func_attr = cfg["demand"]["function_attraction"]

    stations: List[Station] = []
    for sid, sname, func, cap, dx, dy in _SYNTHETIC_STATIONS:
        lng, lat = _offset_to_lnglat(lng0, lat0, dx, dy)
        stations.append(
            Station(
                id=sid, name=sname, lng=lng, lat=lat, capacity=cap,
                func=func, attraction=float(func_attr.get(func, 0.5)),
            )
        )

    # 初始库存：按容量比例分配 500 辆，并留出 20% 余量
    total = int(cfg["system"]["total_bikes"])
    caps = np.array([s.capacity for s in stations], dtype=float)
    share = caps / caps.sum()
    init = np.floor(share * total * 0.80).astype(int)
    # 余量按最大容量点补齐
    diff = total - int(init.sum())
    order = np.argsort(-caps)
    k = 0
    while diff > 0:
        i = order[k % len(order)]
        if init[i] < stations[i].capacity:
            init[i] += 1
            diff -= 1
        k += 1
    for s, v in zip(stations, init):
        s.init_bikes = int(v)
        s.target_bikes = float(s.capacity * 0.5)

    dist = distance_matrix([s.lng for s in stations], [s.lat for s in stations])
    return Scenario(
        stations=stations,
        pulses=pulses_from_config(cfg),
        dist_m=dist,
        cfg=cfg,
        name=name,
    )


def load_scenario_from_csv(cfg: Dict[str, Any], path: str, name: str | None = None) -> Scenario:
    """从 stations.csv 载入真实点位。"""
    stations = load_stations_csv(path)
    if not stations:
        raise ValueError(f"未从 {path} 读到任何点位")
    for s in stations:
        if s.attraction <= 0:
            s.attraction = float(cfg["demand"]["function_attraction"].get(s.func, 0.5))
        if s.target_bikes <= 0:
            s.target_bikes = float(s.capacity * 0.5)
    dist = distance_matrix([s.lng for s in stations], [s.lat for s in stations])
    return Scenario(
        stations=stations,
        pulses=pulses_from_config(cfg),
        dist_m=dist,
        cfg=cfg,
        name=name or os.path.basename(path),
    )
