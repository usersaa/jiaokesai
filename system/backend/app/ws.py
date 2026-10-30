from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .core.database import SessionLocal
from .core.security import decode_token
from .models import SimulationStep, User
from .services.live.hub import hub

router = APIRouter()


@router.websocket("/ws/live")
async def live_ws(websocket: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        user = db.get(User, int(payload.get("sub", 0)))
        if user is None or not user.is_active:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    await websocket.accept()
    await hub.add(websocket)
    try:
        await websocket.send_json({
            "type": "snapshot",
            "payload": hub.stream.snapshot() if hub.stream is not None else None,
        })
        await websocket.send_json({
            "type": "status",
            "payload": {"running": hub.running, "speed": hub.speed},
        })
        while True:
            msg = await websocket.receive_json()
            typ = msg.get("type")
            if typ == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})
            elif typ == "snapshot":
                await websocket.send_json({
                    "type": "snapshot",
                    "payload": hub.stream.snapshot() if hub.stream is not None else None,
                })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.remove(websocket)



@router.websocket("/ws/simulations/{run_id}")
async def simulation_ws(websocket: WebSocket, run_id: int, token: str = Query(...)):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        user = db.get(User, int(payload.get("sub", 0)))
        if user is None or not user.is_active:
            await websocket.close(code=4403)
            return
        rows = (db.query(SimulationStep)
                .filter(SimulationStep.run_id == run_id)
                .order_by(SimulationStep.step)
                .all())
        if not rows:
            await websocket.close(code=4404)
            return
        steps = [
            {
                "step": r.step,
                "time": r.time,
                "inventory": r.inventory_json,
                "action": r.action_json,
                "truck": r.truck_json,
                "metrics": r.metrics_json,
                "reward": r.reward_json,
            }
            for r in rows
        ]
    finally:
        db.close()

    await websocket.accept()
    total = len(steps) - 1
    state = {"cursor": 0, "playing": False, "speed": 1.0}
    send_lock = asyncio.Lock()
    task: asyncio.Task | None = None

    async def send_state():
        async with send_lock:
            await websocket.send_json({
                "type": "state",
                "payload": {
                    "run_id": run_id,
                    "step": state["cursor"],
                    "total": total,
                    "playing": state["playing"],
                    "speed": state["speed"],
                    "data": steps[state["cursor"]],
                },
            })

    async def play_loop():
        while state["playing"] and state["cursor"] < total:
            await asyncio.sleep(1.0 / max(state["speed"], 0.1))
            if not state["playing"]:
                break
            state["cursor"] += 1
            await send_state()
        state["playing"] = False
        async with send_lock:
            await websocket.send_json({
                "type": "done",
                "payload": {"run_id": run_id, "step": state["cursor"], "total": total},
            })

    await send_state()
    try:
        while True:
            msg = await websocket.receive_json()
            typ = msg.get("type")
            body = msg.get("payload") or {}
            if typ == "start":
                if state["cursor"] >= total:
                    state["cursor"] = 0
                if task is None or task.done():
                    state["playing"] = True
                    task = asyncio.create_task(play_loop())
                await send_state()
            elif typ == "pause":
                state["playing"] = False
                await send_state()
            elif typ == "step":
                state["playing"] = False
                state["cursor"] = min(state["cursor"] + int(body.get("n", 1)), total)
                await send_state()
            elif typ == "seek":
                state["playing"] = False
                state["cursor"] = max(0, min(int(body.get("step", 0)), total))
                await send_state()
            elif typ == "speed":
                state["speed"] = max(float(body.get("speed", 1.0)), 0.1)
                await send_state()
            elif typ == "snapshot":
                await send_state()
    except WebSocketDisconnect:
        state["playing"] = False
        if task is not None:
            task.cancel()
    except Exception:
        state["playing"] = False
        if task is not None:
            task.cancel()
