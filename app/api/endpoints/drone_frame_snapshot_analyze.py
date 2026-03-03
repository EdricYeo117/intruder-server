import os
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import time

from app.services.analysis_store import STORE
from app.services.security import enforce_api_key, enforce_lan_only
from app.services.photo_wait_registry import REGISTRY
from app.services.human_analyzer import HumanAnalyzer

router = APIRouter()

_analyzer: HumanAnalyzer | None = None

@router.on_event("startup")
def _startup():
    global _analyzer
    _analyzer = HumanAnalyzer()

# This must be reachable *from inside the api container*.
# Use loopback, not SERVER_PUBLIC_BASE.
INTERNAL_API_BASE = os.getenv("INTERNAL_API_BASE", "http://127.0.0.1:8080").rstrip("/")
SERVER_PUBLIC_BASE = os.getenv("SERVER_PUBLIC_BASE", "http://localhost:8080").rstrip("/")

DEFAULT_TIMEOUT_S = float(os.getenv("SNAPSHOT_WAIT_TIMEOUT_S", "20"))

class Req(BaseModel):
    device_id: str = os.getenv("DRONE_DEVICE_ID", "android-controller-01")
    timeout_s: float | None = None

@router.post("/v1/drone/frame_snapshot/analyze")
async def frame_snapshot_analyze(request: Request, body: Req):
    enforce_lan_only(request)
    enforce_api_key(request)

    if _analyzer is None:
        raise HTTPException(status_code=503, detail="analyzer not ready")

    command_id = str(uuid.uuid4())
    await REGISTRY.create(command_id)

    # Android will upload here, with the command_id query param
    upload_url = f"{SERVER_PUBLIC_BASE}/v1/drone/uploads/photo?command_id={command_id}"

    # This is exactly what your Android CommandDispatcher expects
    cmd = {
        "device_id": body.device_id,
        "cmd_type": "FRAME_SNAPSHOT",
        "command_id": command_id,
        "payload": {
            "upload_url": upload_url
        }
    }

    # Send the command through your existing SSE send endpoint
       # Send the command through your existing SSE send endpoint
    try:
        # forward API key so /v1/drone/send passes enforce_api_key()
        headers = {}
        incoming_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        if incoming_key:
            headers["x-api-key"] = incoming_key

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{INTERNAL_API_BASE}/v1/drone/send",
                json=cmd,
                headers=headers,
            )
            if r.status_code >= 300:
                await REGISTRY.cleanup(command_id)
                raise HTTPException(status_code=502, detail=f"/v1/drone/send failed: {r.status_code} {r.text}")
    except HTTPException:
        raise
    except Exception as e:
        await REGISTRY.cleanup(command_id)
        raise HTTPException(status_code=502, detail=f"failed to call /v1/drone/send: {e}")

    timeout_s = body.timeout_s if body.timeout_s is not None else DEFAULT_TIMEOUT_S
    arrived = await REGISTRY.wait(command_id, timeout_s)
    if arrived is None:
        await REGISTRY.cleanup(command_id)
        raise HTTPException(status_code=504, detail=f"timeout waiting upload (command_id={command_id})")
    try:
        with open(arrived.saved_to, "rb") as f:
            data = f.read()

        t0 = time.time()
        print(f"[ANALYZE] start kind=frame_snapshot device_id={body.device_id} command_id={command_id} "
              f"bytes={len(data)} saved_to={arrived.saved_to}")

        result = _analyzer.analyze_image_bytes(data)

        wall_ms = int((time.time() - t0) * 1000)
        print(f"[ANALYZE] done kind=frame_snapshot device_id={body.device_id} command_id={command_id} "
              f"ok={result.get('ok')} faces={result.get('num_faces')} "
              f"model_latency_ms={result.get('latency_ms')} wall_ms={wall_ms}")

        idx = STORE.save(
            result,
            kind="frame_snapshot",
            device_id=body.device_id,
            command_id=command_id,
            image_path=arrived.saved_to,
        )

        result.update({
            "ok": True,
            "device_id": body.device_id,
            "command_id": command_id,
            "saved_to": arrived.saved_to,
            "analysis_id": idx["analysis_id"],
        })
        return result
    finally:
        await REGISTRY.cleanup(command_id)