"""实时数据流发生器（L3 数据感知层）。

用建模文档里的需求模型产生「分钟级」的租还事件与车辆位置，
让三维镜像被一条持续的数据流驱动，而不是播放一段离线结果。

数据来源全部为模型生成，接口与界面必须标注「模拟数据流」。
本模块只读算法包，不修改需求、供给、选择、MDP、PPO 的任何逻辑。
"""
from __future__ import annotations

import math
from collections import deque
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..algorithm import build_scenario, get_cfg  # noqa: F401  (同时把算法路径加入 sys.path)
from bike_sched.config import fmt_hhmm
from bike_sched.demand import DemandModel

WALK_SPEED_M_PER_MIN = 250.0  # 15 km/h，与 configs 的 speed_kmh 一致
TRUCK_SPEED_M_PER_MIN = 250.0  # 运维三轮车 15 km/h
TRUCK_LOAD_MIN_PER_BIKE = 0.5  # 单辆装卸时间
TRUCK_CAPACITY = 20            # 车载量
MX = 111320.0
MY = 110540.0


@dataclass
class Trip:
    id: int
    from_id: str
    to_id: str
    qty: int
    start: float
    depart: float
    arrive: float
    done: bool = False


@dataclass
class Bike:
    id: str
    state: str = "idle"          # idle | riding | misplaced
    station: str = ""            # 空闲时所在站点；骑行时为起点
    from_id: str = ""
    to_id: str = ""
    depart: float = 0.0          # 出发时刻（当日分钟）
    arrive: float = 0.0
    duration: float = 1.0
    bend: float = 0.0
    lng: float = 0.0
    lat: float = 0.0
    misplaced_at: float = 0.0
    trace: List[List[float]] = field(default_factory=list)


class LiveStream:
    """一条可推进的实时流。调用 tick() 推进一分钟。"""

    def __init__(self, stations, seed: int = 2026, start_minute: Optional[int] = None):
        self.cfg = get_cfg()
        self.sc = build_scenario(stations, self.cfg)
        self.dm = DemandModel(self.cfg, self.sc)
        self.grid = list(self.dm.grid)
        self.rng = np.random.default_rng(seed)

        self.ids = [s.id for s in self.sc.stations]
        self.index = {sid: i for i, sid in enumerate(self.ids)}
        self.n = len(self.ids)
        self.lng = np.array([s.lng for s in self.sc.stations], dtype=float)
        self.lat = np.array([s.lat for s in self.sc.stations], dtype=float)
        self.cap = np.array([max(int(s.capacity), 0) for s in self.sc.stations], dtype=float)
        self.dist = np.asarray(self.sc.dist_m, dtype=float)
        self.prob = self.dm.od_probabilities()

        self.inv = np.array([max(int(s.init_bikes), 0) for s in self.sc.stations], dtype=float)
        self.bikes: Dict[str, Bike] = {}
        self.idle: Dict[str, List[str]] = {sid: [] for sid in self.ids}
        self._build_fleet()

        if start_minute is None:
            now = datetime.now()
            start_minute = now.hour * 60 + now.minute
        self.start_minute = int(min(max(start_minute, int(self.grid[0])), int(self.grid[-1]) - 1))
        self.cursor_sec = 0                  # 相对 start_minute 的秒数
        self.trips: List[Trip] = []
        self.trip_seq = 0
        self.truck_at = self.ids[0] if self.ids else ""
        self.truck_free_at = float(self.start_minute)
        self.events: deque = deque(maxlen=160)
        self._event_seq = 0
        self.stats = {
            "rents": 0, "returns": 0, "rejected": 0, "geofence": 0,
            "misplaced": 0, "riding": 0, "idle": 0, "in_station": 0,
            "truck_trips": 0,
        }

    # ---------------- 车队 ----------------
    def _build_fleet(self) -> None:
        seq = 0
        for i, sid in enumerate(self.ids):
            for _ in range(int(self.inv[i])):
                seq += 1
                bid = f"B{seq:04d}"
                self.bikes[bid] = Bike(id=bid, station=sid, lng=float(self.lng[i]), lat=float(self.lat[i]))
                self.idle[sid].append(bid)

    # ---------------- 时间 ----------------
    @property
    def minute(self) -> int:
        return self.start_minute + self.cursor_sec // 60

    @property
    def now_min(self) -> float:
        return self.start_minute + self.cursor_sec / 60.0

    @property
    def step(self) -> int:
        idx = (self.minute - int(self.grid[0])) // 10
        return int(min(max(idx, 0), len(self.grid) - 1))

    @property
    def clock(self) -> str:
        return f"{fmt_hhmm(self.minute)}:{self.cursor_sec % 60:02d}"

    # ---------------- 推进 ----------------
    def tick(self) -> Dict[str, Any]:
        """推进一秒；整分钟时结算借还与回收，每秒都更新车辆位置。"""
        self.cursor_sec += 1
        emitted: List[Dict[str, Any]] = []
        if self.cursor_sec % 60 == 0:
            emitted.extend(self._recover_misplaced())
        emitted.extend(self._generate_rents())
        emitted.extend(self._advance_riding())
        emitted.extend(self._advance_trips())
        self._refresh_stats()
        payload = {
            "t": self.clock,
            "minute": self.minute,
            "step": self.step,
            "inventory": {sid: int(self.inv[i]) for i, sid in enumerate(self.ids)},
            "bikes": [
                {"id": b.id, "lng": round(b.lng, 6), "lat": round(b.lat, 6), "to": b.to_id}
                for b in self.bikes.values() if b.state == "riding"
            ],
            "stats": dict(self.stats),
        }
        return {"tick": payload, "events": emitted}

    def _generate_rents(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        demand = self.dm.true_demand(self.step) / 600.0   # 每 10 分钟需求摊到每秒
        lam = np.maximum(demand, 0.0)
        draws = self.rng.poisson(lam)
        for i in range(self.n):
            k = int(draws[i])
            if k <= 0:
                continue
            sid = self.ids[i]
            pool = self.idle[sid]
            if not pool:
                continue
            k = min(k, len(pool))
            dests = self.rng.choice(self.n, size=k, p=self.prob[i])
            for j in dests:
                if not pool:
                    break
                bid = pool.pop()
                bike = self.bikes[bid]
                d = float(self.dist[i][j])
                duration = max(1.0, d / WALK_SPEED_M_PER_MIN)
                bike.state = "riding"
                bike.from_id = sid
                bike.to_id = self.ids[int(j)]
                bike.depart = self.now_min
                bike.arrive = bike.depart + duration
                bike.duration = duration
                bike.bend = float(self.rng.uniform(6.0, 22.0)) * float(self.rng.choice([-1.0, 1.0]))
                bike.trace = [[round(float(self.lng[i]), 6), round(float(self.lat[i]), 6)]]
                self.inv[i] -= 1
                self.stats["rents"] += 1
                out.append(self._event("rent", sid, self.ids[int(j)], bid, 1,
                                      f"{sid} → {self.ids[int(j)]}"))
        return out

    def _advance_riding(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        now = self.now_min
        for bike in self.bikes.values():
            if bike.state != "riding":
                continue
            f = min(1.0, max(0.0, (now - bike.depart) / max(bike.duration, 1e-6)))
            i = self.index.get(bike.from_id, 0)
            j = self.index.get(bike.to_id, 0)
            bike.lng, bike.lat = self._interp(self.lng[i], self.lat[i], self.lng[j], self.lat[j], f, bike.bend)
            bike.trace.append([round(bike.lng, 6), round(bike.lat, 6)])
            if len(bike.trace) > 40:
                bike.trace = bike.trace[-40:]
            if f < 1.0:
                continue
            out.extend(self._finish_ride(bike, j))
        return out

    def _finish_ride(self, bike: Bike, j: int) -> List[Dict[str, Any]]:
        sid = self.ids[j]
        # 12% 的骑行者未入栏，落在站点附近
        if float(self.rng.random()) < 0.05:
            off_lng, off_lat = self._offset(bike.lng, bike.lat, float(self.rng.uniform(40.0, 95.0)))
            bike.state = "misplaced"
            bike.lng, bike.lat = off_lng, off_lat
            bike.station = ""
            bike.misplaced_at = self.now_min
            self.stats["geofence"] += 1
            self.stats["misplaced"] += 1
            return [self._event("geofence", sid, sid, bike.id, 1, f"{sid} 周边未入栏", alert=True)]
        if self.inv[j] >= self.cap[j]:
            # 满位还车失败：车辆仍由骑行者持有，下一分钟重试
            bike.arrive = self.now_min + 1.0
            bike.duration = 1.0
            bike.depart = self.now_min
            self.stats["rejected"] += 1
            return [self._event("return_rejected", sid, sid, bike.id, 1, f"{sid} 已满，还车失败", alert=True)]
        self.inv[j] += 1
        bike.state = "idle"
        bike.station = sid
        bike.lng, bike.lat = float(self.lng[j]), float(self.lat[j])
        self.idle[sid].append(bike.id)
        self.stats["returns"] += 1
        return [self._event("return", sid, sid, bike.id, 1, f"{bike.from_id} → {sid} 已入栏")]

    def _recover_misplaced(self) -> List[Dict[str, Any]]:
        """运维回收：违停超过 20 分钟的车辆被拉回最近的有空位站点。"""
        out: List[Dict[str, Any]] = []
        for bike in self.bikes.values():
            if bike.state != "misplaced":
                continue
            if self.now_min - bike.misplaced_at < 20:
                continue
            order = np.argsort(self.dist[self.index.get(bike.to_id, 0)])
            for j in order:
                j = int(j)
                if self.inv[j] >= self.cap[j]:
                    continue
                self.inv[j] += 1
                bike.state = "idle"
                bike.station = self.ids[j]
                bike.lng, bike.lat = float(self.lng[j]), float(self.lat[j])
                self.idle[self.ids[j]].append(bike.id)
                out.append(self._event("recover", self.ids[j], self.ids[j], bike.id, 1,
                                       f"{bike.id} 已回收至 {self.ids[j]}"))
                break
        return out

    # ---------------- 工具 ----------------
    def _interp(self, lng1, lat1, lng2, lat2, f, bend):
        lng = lng1 + (lng2 - lng1) * f
        lat = lat1 + (lat2 - lat1) * f
        if bend:
            mx = MX * math.cos(math.radians((lat1 + lat2) / 2.0))
            px = -(lat2 - lat1) * MY
            py = (lng2 - lng1) * mx
            norm = math.hypot(px, py) or 1.0
            off = math.sin(math.pi * f) * bend
            lng += (px / norm) * off / mx
            lat += (py / norm) * off / MY
        return lng, lat

    def _offset(self, lng, lat, meters):
        ang = float(self.rng.uniform(0, 2 * math.pi))
        mx = MX * math.cos(math.radians(lat))
        return lng + math.cos(ang) * meters / mx, lat + math.sin(ang) * meters / MY

    def _event(self, typ, station, to, bike, qty, note, alert=False):
        self._event_seq += 1
        ev = {
            "id": self._event_seq,
            "t": self.clock,
            "type": typ,
            "station": station,
            "to": to,
            "bike": bike,
            "qty": qty,
            "note": note,
            "alert": bool(alert),
        }
        self.events.appendleft(ev)
        return ev

    def _refresh_stats(self) -> None:
        riding = sum(1 for b in self.bikes.values() if b.state == "riding")
        misplaced = sum(1 for b in self.bikes.values() if b.state == "misplaced")
        self.stats["riding"] = riding
        self.stats["misplaced"] = misplaced
        self.stats["in_station"] = int(self.inv.sum())
        self.stats["idle"] = sum(len(v) for v in self.idle.values())
        self.stats["in_transit"] = sum(t.qty for t in self.trips if not t.done)

    # ---------------- 快照 ----------------
    def snapshot(self) -> Dict[str, Any]:
        self._refresh_stats()
        return {
            "t": self.clock,
            "minute": self.minute,
            "step": self.step,
            "station_ids": self.ids,
            "inventory": {sid: int(self.inv[i]) for i, sid in enumerate(self.ids)},
            "bikes": [
                {"id": b.id, "lng": round(b.lng, 6), "lat": round(b.lat, 6), "to": b.to_id}
                for b in self.bikes.values() if b.state == "riding"
            ],
            "stats": dict(self.stats),
            "truck": {
                "at": self.truck_at,
                "busy": self.truck_free_at > self.now_min,
                "free_in_min": round(max(0.0, self.truck_free_at - self.now_min), 1),
            },
            "trips": [
                {"id": t.id, "from": t.from_id, "to": t.to_id, "qty": t.qty,
                 "eta_min": round(t.arrive - self.now_min, 1)}
                for t in self.trips if not t.done
            ],
            "events": list(self.events)[:40],
            "source": {
                "kind": "simulated",
                "generator": "demand-model / OD",
                "granularity": "1min",
                "note": "车辆实例由站点库存派生，非真实单车轨迹",
            },
        }

    def _advance_trips(self) -> List[Dict[str, Any]]:
        """三轮车到站卸车。"""
        out: List[Dict[str, Any]] = []
        now = self.now_min
        for trip in self.trips:
            if trip.done or now < trip.arrive:
                continue
            trip.done = True
            j = self.index.get(trip.to_id)
            if j is None:
                continue
            add = int(min(trip.qty, max(0, self.cap[j] - self.inv[j])))
            self.inv[j] += add
            self.stats["truck_trips"] = self.stats.get("truck_trips", 0) + 1
            out.append(self._event("truck_arrive", trip.from_id, trip.to_id, "", add,
                                   f"{trip.from_id} → {trip.to_id} {add} 辆已送达"))
        self.trips = [t for t in self.trips if not t.done]
        return out

    def apply_dispatch(self, from_id: str, to_id: str, qty: int) -> Dict[str, Any]:
        """下发一条调拨任务：起点装车出库，三轮车按行程时间送达终点。

        与真实调度一致：车辆在途中不可用，三轮车一次只能执行一趟，
        后续任务按到达时间排队（因此同一辆三轮车可以连续执行多趟）。
        """
        if from_id not in self.index or to_id not in self.index:
            raise ValueError("点位不存在")
        if from_id == to_id:
            raise ValueError("起点与终点不能相同")
        i, j = self.index[from_id], self.index[to_id]
        asked = int(max(1, min(qty, TRUCK_CAPACITY)))
        avail = int(self.inv[i])
        space = int(max(0, self.cap[j] - self.inv[j]))
        qty = int(min(asked, avail, space))
        if qty <= 0:
            raise ValueError("起点无车或终点无空位")

        now = self.now_min
        travel = float(self.dist[i][j]) / TRUCK_SPEED_M_PER_MIN
        load = qty * TRUCK_LOAD_MIN_PER_BIKE
        ready = max(now, self.truck_free_at)
        wait = max(0.0, ready - now)
        deadhead = 0.0
        if self.truck_at and self.truck_at != from_id:
            k = self.index.get(self.truck_at)
            if k is not None:
                deadhead = float(self.dist[k][i]) / TRUCK_SPEED_M_PER_MIN
        start = ready + deadhead
        depart = start + load
        arrive = depart + travel

        self.inv[i] -= qty          # 装车即出库，途中不可用
        self.trip_seq += 1
        self.trips.append(Trip(self.trip_seq, from_id, to_id, qty, start, depart, arrive))
        self.truck_at = to_id
        self.truck_free_at = arrive + load
        self._refresh_stats()

        eta = arrive - now
        note = f"{from_id} → {to_id} {qty} 辆，预计 {eta:.0f} 分钟"
        detail = []
        if wait > 0.5:
            detail.append(f"排队 {wait:.0f} 分")
        if deadhead > 0.5:
            detail.append(f"空驶 {deadhead:.0f} 分")
        if detail:
            note += f"（{'，'.join(detail)}）"
        if qty < asked:
            note += f"；受库存/空位限制，{asked} 辆只调 {qty} 辆"
        ev = self._event("dispatch", from_id, to_id, "", qty, note)
        ev["moves"] = [{"from": from_id, "to": to_id, "qty": qty}]
        ev["eta_min"] = round(eta, 1)
        ev["wait_min"] = round(wait, 1)
        ev["deadhead_min"] = round(deadhead, 1)
        ev["distance_m"] = int(self.dist[i][j])
        return ev
