# app/services/dji_controller_client.py

import os
import httpx
from dotenv import load_dotenv

load_dotenv()


class DJIControllerClient:
    """
    Client that talks to the Android DJI controller HTTP server (OracleDJIDroneMSDK).

    Matches RemoteHttpServer.kt endpoints:

      GET  /v1/drone/status
      POST /v1/drone/vs/enable      { "enable": true }
      POST /v1/drone/vs/moveSequence{ "moves": [...], "defaultHz": 25 }
      POST /v1/drone/vs/stop
      POST /v1/drone/media/photo    { "uploadUrl": "http://..." }

    """
    _singleton = None
    _http: httpx.AsyncClient | None = None

    def __init__(self) -> None:
        base = os.getenv("CONTROLLER_BASE_URL", "").rstrip("/")
        if not base:
            raise RuntimeError("CONTROLLER_BASE_URL is not set")

        self.base_url = base
        timeout_s = float(os.getenv("HTTP_TIMEOUT_S", "5.0"))
        self._controller_api_key = (os.getenv("CONTROLLER_API_KEY") or "").strip()

        DJIControllerClient._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_s,
        )

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
        h: dict[str, str] = {}
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

    # ---- Controller API (matches OracleDJIDroneMSDK RemoteHttpServer.kt) ----

    async def health(self) -> dict:
        return await self._get("/v1/drone/status")

    async def enable_virtual_stick(self, enabled: bool) -> dict:
        # Controller expects {"enable": true}
        return await self._post("/v1/drone/vs/enable", {"enable": enabled})

    async def stop(self) -> dict:
        return await self._post("/v1/drone/vs/stop", {})

    async def move_sequence(self, moves: list[dict], default_hz: int = 25) -> dict:
        """
        Controller expects:
          POST /v1/drone/vs/moveSequence
          {
            "moves": [
              {"leftX":..., "leftY":..., "rightX":..., "rightY":..., "durationMs":..., "hz":...},
              ...
            ],
            "defaultHz": 25
          }
        """
        return await self._post("/v1/drone/vs/moveSequence", {"moves": moves, "defaultHz": default_hz})

    async def take_photo(self, upload_url: str | None = None) -> dict:
        # Controller PhotoReq is (uploadUrl: String). Send empty string if not provided.
        return await self._post("/v1/drone/media/photo", {"uploadUrl": upload_url or ""})