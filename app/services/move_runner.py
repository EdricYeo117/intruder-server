# app/services/move_runner.py

import asyncio
import time


class MoveRunner:
    """
    Server-side runner used by intruder-server's /v1/drone/vs/moveSequence endpoint.

    IMPORTANT: This is NOT the Android MoveRunner.
    This one now calls the Android controller's /v1/drone/vs/moveSequence exactly once
    (the controller handles timing internally).
    """

    def __init__(self, client) -> None:
        self._client = client
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._status = {"running": False}

    def status(self) -> dict:
        return self._status

    async def stop(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except Exception:
                    pass
            self._task = None
            self._status = {"running": False}
        await self._client.stop()

    async def start(
        self,
        leftX: int,
        leftY: int,
        rightX: int,
        rightY: int,
        duration_ms: int,
        freq_hz: int,
    ) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except Exception:
                    pass

            self._status = {
                "running": True,
                "started_at_ms": int(time.time() * 1000),
                "duration_ms": duration_ms,
                "freq_hz": freq_hz,
                "last_cmd": {"leftX": leftX, "leftY": leftY, "rightX": rightX, "rightY": rightY},
            }

            self._task = asyncio.create_task(
                self._run_controller_move_sequence(leftX, leftY, rightX, rightY, duration_ms, freq_hz)
            )

    async def start_and_wait(
        self,
        leftX: int,
        leftY: int,
        rightX: int,
        rightY: int,
        duration_ms: int,
        freq_hz: int,
    ) -> None:
        await self.start(leftX, leftY, rightX, rightY, duration_ms, freq_hz)
        async with self._lock:
            t = self._task
        if t:
            await t

    async def _run_controller_move_sequence(
        self,
        leftX: int,
        leftY: int,
        rightX: int,
        rightY: int,
        duration_ms: int,
        freq_hz: int,
    ) -> None:
        try:
            await self._client.enable_virtual_stick(True)

            # Controller expects floats + durationMs + hz
            moves = [
                {
                    "leftX": float(leftX),
                    "leftY": float(leftY),
                    "rightX": float(rightX),
                    "rightY": float(rightY),
                    "durationMs": int(duration_ms),
                    "hz": int(freq_hz),
                }
            ]

            await self._client.move_sequence(moves=moves, default_hz=int(freq_hz))
        except asyncio.CancelledError:
            raise
        finally:
            await self._client.stop()
            self._status = {"running": False}