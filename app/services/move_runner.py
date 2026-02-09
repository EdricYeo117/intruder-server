# app/services/move_runner.py
import asyncio
import time

class MoveRunner:
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

    async def start(self, leftX: int, leftY: int, rightX: int, rightY: int, duration_ms: int, freq_hz: int) -> None:
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
            self._task = asyncio.create_task(self._loop(leftX, leftY, rightX, rightY, duration_ms, freq_hz))

    async def start_and_wait(self, leftX: int, leftY: int, rightX: int, rightY: int, duration_ms: int, freq_hz: int) -> None:
        await self.start(leftX, leftY, rightX, rightY, duration_ms, freq_hz)
        # wait for current task to finish
        async with self._lock:
            t = self._task
        if t:
            await t

    async def _loop(self, leftX: int, leftY: int, rightX: int, rightY: int, duration_ms: int, freq_hz: int) -> None:
        interval = 1.0 / float(freq_hz)
        end = time.time() + (duration_ms / 1000.0)

        try:
            await self._client.enable_virtual_stick(True)
            while time.time() < end:
                await self._client.move_sticks(leftX, leftY, rightX, rightY)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        finally:
            await self._client.stop()
            self._status = {"running": False}
