import os
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from dotenv import load_dotenv

from app.services.security import enforce_api_key, enforce_lan_only
from app.schemas.drone import EnableVSRequest, MoveSequenceRequest, PhotoRequest
from app.services.dji_controller_client import DJIControllerClient
from app.services.move_runner import MoveRunner

load_dotenv()

router = APIRouter()

DEFAULT_FREQ_HZ = int(os.getenv("DEFAULT_MOVE_FREQ_HZ", "25"))

# Singletons for this process
_client = DJIControllerClient.get_singleton()
_runner = MoveRunner(_client)


@router.get("/v1/drone/status")
async def drone_status(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    st = _runner.status()
    return {
        "ok": True,
        "controller_base_url": _client.base_url,
        "move_running": st.get("running", False),
        "started_at_ms": st.get("started_at_ms"),
        "duration_ms": st.get("duration_ms"),
        "freq_hz": st.get("freq_hz"),
        "last_cmd": st.get("last_cmd"),
    }


@router.post("/v1/drone/vs/enable")
async def vs_enable(
    body: EnableVSRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    resp = await _client.enable_virtual_stick(body.enabled)
    return {"ok": True, "data": resp, "received_at_ms": int(time.time() * 1000)}


@router.post("/v1/drone/vs/moveSequence")
async def vs_move_sequence(
    body: MoveSequenceRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    freq_hz = body.freq_hz or DEFAULT_FREQ_HZ

    # start async movement loop (continuous send)
    await _runner.start(
        leftX=body.leftX,
        leftY=body.leftY,
        rightX=body.rightX,
        rightY=body.rightY,
        duration_ms=body.duration_ms,
        freq_hz=freq_hz,
    )

    return {"ok": True, "detail": "Move started", "freq_hz": freq_hz, "received_at_ms": int(time.time() * 1000)}


@router.post("/v1/drone/vs/stop")
async def vs_stop(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_ap_
