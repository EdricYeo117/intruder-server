# app/services/sse_broker.py
import asyncio
import json
import time
from typing import Dict, Any

class DroneSseBroker:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def get_queue(self, device_id: str) -> asyncio.Queue:
        async with self._lock:
            q = self._queues.get(device_id)
            if q is None:
                q = asyncio.Queue(maxsize=200)
                self._queues[device_id] = q
            return q

    async def publish(self, device_id: str, msg: Dict[str, Any]) -> None:
        q = await self.get_queue(device_id)
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            # drop oldest, keep latest behavior
            _ = q.get_nowait()
            q.put_nowait(msg)

broker = DroneSseBroker()

def sse_event(event: str, data: dict) -> str:
    # SSE wire format
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def now_ms() -> int:
    return int(time.time() * 1000)
