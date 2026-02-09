# app/services/dji_controller_client.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class DJIControllerClient:
    _singleton = None
    _http: httpx.AsyncClient | None = None

    def __init__(self) -> None:
        base = os.getenv("CONTROLLER_BASE_URL", "").rstrip("/")
        if not base:
            raise RuntimeError("CONTROLLER_BASE_URL is not set")
        self.base_url = base
        timeout_s = float(os.getenv("HTTP_TIMEOUT_S", "5.0"))
        self._controller_api_key = os.getenv("CONTROLLER_API_KEY", "")

        DJIControllerClient._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_s)

    @classmethod
    def get_singleton(cls) -> "DJIControllerClient":
        if cls._singleton is None:
            cls._singleton = DJIControllerClient()
        return cls._singleton

    @classmethod
    async def aclose_singleton(cls) -> None:
        if cls._http is not None:
            await cls._http.aclose()
            cls._http = None
        cls._singleton = None

    def _headers(self) -> dict[str, str]:
        h = {}
        if self._controller_api_key:
            h["X-API-Key"] = self._controller_api_key
        return h

    async def _post(self, path: str, payload: dict) -> dict:
        assert DJIControllerClient._http is not None
        r = await DJIControllerClient._http.post(path, json=payload, headers=self._headers())
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    async def _get(self, path: str) -> dict:
        assert DJIControllerClient._http is not None
        r = await DJIControllerClient._http.get(path, headers=self._headers())
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    async def health(self) -> dict:
        return await self._get("/health")

    async def enable_virtual_stick(self, enabled: bool) -> dict:
        return await self._post("/vs/enable", {"enabled": enabled})

    async def move_sticks(self, leftX: int, leftY: int, rightX: int, rightY: int) -> dict:
        return await self._post("/vs/move", {"leftX": leftX, "leftY": leftY, "rightX": rightX, "rightY": rightY})

    async def stop(self) -> dict:
        try:
            return await self._post("/vs/stop", {})
        except Exception:
            return await self.move_sticks(0, 0, 0, 0)

    async def take_photo(self, upload_url: str | None = None) -> dict:
        payload = {}
        if upload_url:
            payload["upload_url"] = upload_url
        return await self._post("/media/photo", payload)
