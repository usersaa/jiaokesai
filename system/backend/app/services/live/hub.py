"""实时会话与广播。"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Set

from .stream import LiveStream


class LiveHub:
    def __init__(self) -> None:
        self.stream: Optional[LiveStream] = None
        self.clients: Set[Any] = set()
        self.task: Optional[asyncio.Task] = None
        self.speed: float = 1.0
        self.running: bool = False

    # ---------------- 会话 ----------------
    async def start(self, stations, speed: float = 1.0, start_minute: Optional[int] = None,
                    seed: int = 2026) -> Dict[str, Any]:
        await self.stop(reset=True)
        self.stream = LiveStream(stations, seed=seed, start_minute=start_minute)
        self.speed = max(0.25, min(float(speed or 1.0), 8.0))
        self.running = True
        self.task = asyncio.create_task(self._loop())
        await self.broadcast({"type": "status", "payload": {"running": True, "speed": self.speed}})
        await self.broadcast({"type": "snapshot", "payload": self.stream.snapshot()})
        return self.stream.snapshot()

    async def pause(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        await self.broadcast({"type": "status", "payload": {"running": False, "speed": self.speed}})

    async def resume(self) -> None:
        if self.stream is None:
            return
        self.running = True
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())
        await self.broadcast({"type": "status", "payload": {"running": True, "speed": self.speed}})

    async def stop(self, reset: bool = False) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        if reset:
            self.stream = None
        await self.broadcast({"type": "status", "payload": {"running": False, "speed": self.speed}})

    async def set_speed(self, value: float) -> None:
        self.speed = max(0.25, min(float(value or 1.0), 8.0))
        await self.broadcast({"type": "status", "payload": {"running": self.running, "speed": self.speed}})

    # ---------------- 循环 ----------------
    async def _loop(self) -> None:
        try:
            while self.running and self.stream is not None:
                await asyncio.sleep(max(0.15, 1.0 / max(self.speed, 0.1)))
                if not self.running or self.stream is None:
                    break
                result = self.stream.tick()
                await self.broadcast({"type": "tick", "payload": result["tick"]})
                if result["events"]:
                    await self.broadcast({"type": "events", "payload": result["events"]})
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover
            print(f"[live] 循环异常：{exc}")
            self.running = False
            await self.broadcast({"type": "error", "payload": {"message": str(exc)}})

    # ---------------- 广播 ----------------
    async def add(self, ws) -> None:
        self.clients.add(ws)

    def remove(self, ws) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.clients:
            return
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


hub = LiveHub()
