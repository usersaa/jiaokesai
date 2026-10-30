"""L3 实时数据流接口：启动、暂停、快照、事件、沙盒预演、指令下发。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models import Station, User
from ..services.algorithm import build_scenario, get_cfg
from ..services.audit import audit
from ..services.live.hub import hub

router = APIRouter(prefix="/api/live", tags=["live"])

from bike_sched.baselines import NoOpPolicy  # noqa: E402
from bike_sched.demand import DemandModel  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402


class StartBody(BaseModel):
    speed: float = 1.0
    start_minute: Optional[int] = None
    seed: int = 2026


class SpeedBody(BaseModel):
    value: float = 1.0


class PreviewBody(BaseModel):
    from_id: str
    to_id: str
    qty: int = Field(default=10, ge=1, le=20)
    horizon_min: int = Field(default=30, ge=10, le=180)
    stress: float = Field(default=1.0, ge=1.0, le=3.0)


class DispatchBody(BaseModel):
    from_id: str
    to_id: str
    qty: int = Field(default=10, ge=1, le=20)


def _service_stations(db: Session) -> List[Station]:
    return [s for s in db.query(Station).order_by(Station.id).all() if s.func != "nopark"]


@router.get("/state")
def live_state(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    if hub.stream is None:
        return {"running": False, "speed": hub.speed, "stream": None}
    return {"running": hub.running, "speed": hub.speed, "stream": hub.stream.snapshot()}


@router.get("/events")
def live_events(limit: int = Query(40, ge=1, le=160),
                user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    if hub.stream is None:
        return []
    return list(hub.stream.events)[:limit]


@router.post("/start")
async def live_start(body: StartBody, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> Dict[str, Any]:
    stations = _service_stations(db)
    if len(stations) < 3:
        raise HTTPException(status_code=400, detail="点位数不足，至少需要 3 个点位")
    snap = await hub.start(stations, speed=body.speed, start_minute=body.start_minute, seed=body.seed)
    return {"ok": True, "snapshot": snap}


@router.post("/pause")
async def live_pause(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    await hub.pause()
    return {"ok": True, "running": hub.running}


@router.post("/resume")
async def live_resume(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    await hub.resume()
    return {"ok": True, "running": hub.running}


@router.post("/stop")
async def live_stop(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    await hub.stop(reset=True)
    return {"ok": True, "running": False}


@router.post("/speed")
async def live_speed(body: SpeedBody, user: User = Depends(get_current_user)) -> Dict[str, Any]:
    await hub.set_speed(body.value)
    return {"ok": True, "speed": hub.speed}


def _roll_horizon(stations, inv: np.ndarray, step_idx: int, steps: int,
                  stress: float = 1.0) -> Dict[str, Any]:
    """用 CampusEnv 把未来 steps 步真跑一遍（NoOp 策略，只观察不干预）。

    同一环境、同一种子、同一需求，两次调用只有初始库存不同，
    因此差异可归因到调拨本身。
    """
    cfg = get_cfg()
    if stress and stress != 1.0:
        # 压力情景：同比例放大基础需求与脉冲幅度，仅用于推演对比
        cfg["demand"]["baseline_rate_per_hour"] = float(cfg["demand"]["baseline_rate_per_hour"]) * stress
        cfg["demand"]["pulse_gain"] = float(cfg["demand"]["pulse_gain"]) * stress
    sc = build_scenario(stations, cfg)
    env = CampusEnv(cfg, sc, seed=7)
    env.reset(seed=7)
    env.step_idx = int(min(max(step_idx, 0), len(env.grid) - 2))
    env.inv = np.asarray(inv, dtype=float)
    policy = NoOpPolicy()
    for _ in range(int(max(1, steps))):
        action = policy.act(env, None)
        _, _, term, trunc, _ = env.step(action)
        if term or trunc:
            break
    summary = env.metrics_summary()
    return {
        "shortage": round(float(summary.get("total_shortage", 0.0)), 2),
        "service_rate": round(float(summary.get("service_rate", 0.0)), 4),
        "bike_shortage": round(float(summary.get("bike_shortage", 0.0)), 2),
        "return_shortage": round(float(summary.get("return_shortage", 0.0)), 2),
        "served": round(float(summary.get("served_rides", 0.0)), 1),
    }


def _shift(inv: np.ndarray, cap: np.ndarray, ids: List[str],
           from_id: str, to_id: str, qty: int) -> Optional[np.ndarray]:
    if from_id not in ids or to_id not in ids or from_id == to_id:
        return None
    i, j = ids.index(from_id), ids.index(to_id)
    moved = int(min(qty, inv[i], max(0, cap[j] - inv[j])))
    if moved <= 0:
        return None
    out = inv.astype(float).copy()
    out[i] -= moved
    out[j] += moved
    return out


@router.post("/preview")
def live_preview(body: PreviewBody, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """沙盒预演：对比「不调拨」与「按指令调拨」的未来供需缺口。

    只用需求模型与库存做供需核对，不调用策略，也不写运行记录。
    """
    stations = _service_stations(db)
    if len(stations) < 3:
        raise HTTPException(status_code=400, detail="点位数不足")
    cfg = get_cfg()
    sc = build_scenario(stations, cfg)
    ids = [s.id for s in sc.stations]
    cap = np.array([max(int(s.capacity), 0) for s in sc.stations], dtype=float)

    if hub.stream is not None:
        inv = hub.stream.inv.copy()
        step_idx = hub.stream.step
        clock = hub.stream.clock
    else:
        inv = np.array([max(int(s.init_bikes), 0) for s in sc.stations], dtype=float)
        step_idx = 0
        clock = "06:30"

    shifted = _shift(inv, cap, ids, body.from_id, body.to_id, body.qty)
    if shifted is None:
        raise HTTPException(status_code=400, detail="该调拨无法执行：起点无车或终点无空位")

    steps = max(1, int(round(body.horizon_min / 10.0)))
    dm = DemandModel(cfg, sc)
    demand = np.zeros(len(ids), dtype=float)
    for k in range(steps):
        idx = min(step_idx + k, len(dm.grid) - 1)
        demand += dm.true_demand(idx)

    j = ids.index(body.to_id)
    i = ids.index(body.from_id)
    base_gap = np.maximum(demand - inv, 0.0)
    shifted_gap = np.maximum(demand - shifted, 0.0)
    dist = float(sc.dist_m[i][j])
    eta = dist / 250.0 + body.qty * 0.5
    base_run = _roll_horizon(stations, inv, step_idx, steps, body.stress)
    plan_run = _roll_horizon(stations, shifted, step_idx, steps, body.stress)
    return {
        "clock": clock,
        "horizon_min": body.horizon_min,
        "from_id": body.from_id,
        "to_id": body.to_id,
        "qty": body.qty,
        "demand": round(float(demand[j]), 1),
        "base_inventory": int(inv[j]),
        "shifted_inventory": int(shifted[j]),
        "base_gap": round(float(base_gap[j]), 1),
        "shifted_gap": round(float(shifted_gap[j]), 1),
        "delta": round(float(shifted_gap[j] - base_gap[j]), 1),
        "system_base_gap": round(float(base_gap.sum()), 1),
        "system_shifted_gap": round(float(shifted_gap.sum()), 1),
        "distance_m": int(dist),
        "eta_min": round(eta, 1),
        "env": {
            "steps": steps,
            "stress": body.stress,
            "base": base_run,
            "plan": plan_run,
            "shortage_delta": round(plan_run["shortage"] - base_run["shortage"], 2),
            "service_delta": round(plan_run["service_rate"] - base_run["service_rate"], 4),
        },
        "strategy": "campus-env-rollout",
        "note": "同一环境、同一种子跑 N 步（NoOp 策略）；差异仅来自初始库存，未调用 PPO",
    }


@router.post("/dispatch")
async def live_dispatch(body: DispatchBody, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> Dict[str, Any]:
    if hub.stream is None:
        raise HTTPException(status_code=400, detail="实时镜像未启动")
    try:
        ev = hub.stream.apply_dispatch(body.from_id, body.to_id, body.qty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit(db, user, "dispatch_order", f"{body.from_id}->{body.to_id} {body.qty}",
          {"from_id": body.from_id, "to_id": body.to_id, "qty": body.qty,
           "channel": "simulated"}, ip="")
    await hub.broadcast({"type": "event", "payload": ev})
    await hub.broadcast({"type": "tick", "payload": {
        "t": hub.stream.clock,
        "minute": hub.stream.minute,
        "step": hub.stream.step,
        "inventory": {sid: int(hub.stream.inv[i]) for i, sid in enumerate(hub.stream.ids)},
        "bikes": [{"id": b.id, "lng": round(b.lng, 6), "lat": round(b.lat, 6), "to": b.to_id}
                  for b in hub.stream.bikes.values() if b.state == "riding"],
        "stats": dict(hub.stream.stats),
    }})
    return {"ok": True, "event": ev, "channel": "simulated"}
