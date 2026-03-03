# app/services/photo_wait_registry.py
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class PhotoArrived:
    command_id: str
    saved_to: str

class PhotoWaitRegistry:
    def __init__(self) -> None:
        self._events: Dict[str, asyncio.Event] = {}
        self._results: Dict[str, PhotoArrived] = {}
        self._lock = asyncio.Lock()

    async def create(self, command_id: str) -> None:
        async with self._lock:
            self._events[command_id] = asyncio.Event()

    async def fulfill(self, command_id: str, saved_to: str) -> None:
        async with self._lock:
            self._results[command_id] = PhotoArrived(command_id, saved_to)
            ev = self._events.get(command_id)
            if ev:
                ev.set()

    async def wait(self, command_id: str, timeout_s: float) -> Optional[PhotoArrived]:
        async with self._lock:
            ev = self._events.get(command_id)
        if ev is None:
            return None
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            return None
        async with self._lock:
            return self._results.get(command_id)

    async def cleanup(self, command_id: str) -> None:
        async with self._lock:
            self._events.pop(command_id, None)
            self._results.pop(command_id, None)

REGISTRY = PhotoWaitRegistry()