"""地理与 CSV 读写工具。"""
from __future__ import annotations

import csv
import math
import os
from typing import Iterable, List

import numpy as np

from ..entities import Station

EARTH_R_M = 6371008.8


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """两点球面距离（米）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def distance_matrix(lngs: Iterable[float], lats: Iterable[float]) -> np.ndarray:
    """站点间距离矩阵（米），对角为 0。"""
    lngs = list(lngs)
    lats = list(lats)
    n = len(lngs)
    d = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            v = haversine_m(lngs[i], lats[i], lngs[j], lats[j])
            d[i, j] = d[j, i] = v
    return d


def load_stations_csv(path: str) -> List[Station]:
    """读取 stations.csv。

    必需列：id,name,lng,lat,capacity,func,init_bikes
    可选列：attraction,target_bikes
    """
    out: List[Station] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out.append(
                Station(
                    id=str(row["id"]).strip(),
                    name=str(row.get("name", "")).strip(),
                    lng=float(row["lng"]),
                    lat=float(row["lat"]),
                    capacity=int(float(row["capacity"])),
                    func=str(row.get("func", "other")).strip() or "other",
                    attraction=float(row.get("attraction", 0.5) or 0.5),
                    init_bikes=int(float(row.get("init_bikes", 0) or 0)),
                    target_bikes=float(row.get("target_bikes", 0) or 0),
                )
            )
    return out


def save_stations_csv(stations: List[Station], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "lng", "lat", "capacity", "func",
                    "attraction", "init_bikes", "target_bikes"])
        for s in stations:
            w.writerow([s.id, s.name, f"{s.lng:.6f}", f"{s.lat:.6f}",
                        s.capacity, s.func, f"{s.attraction:.3f}",
                        s.init_bikes, f"{s.target_bikes:.1f}"])
