# app/api/endpoints/drone.py
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

_client = DJIControllerClient.get_singleton()
_runner = MoveRunner(_client)

@router.get("/v1/drone/ping")
async def drone_ping(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    try:
        resp = await _client.health()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Controller unreachable: {e}")

    return {"ok": True, "controller": _client.base_url, "health": resp, "received_at_ms": int(time.time() * 1000)}

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

    # For testing: block until finished if wait=True
    if body.wait:
        await _runner.start_and_wait(
            leftX=body.leftX, leftY=body.leftY, rightX=body.rightX, rightY=body.rightY,
            duration_ms=body.duration_ms, freq_hz=freq_hz
        )
    else:
        await _runner.start(
            leftX=body.leftX, leftY=body.leftY, rightX=body.rightX, rightY=body.rightY,
            duration_ms=body.duration_ms, freq_hz=freq_hz
        )

    photo_resp = None
    if body.take_photo_after:
        photo_resp = await _client.take_photo(upload_url=body.upload_url)

    return {
        "ok": True,
        "detail": "Move executed" if body.wait else "Move started",
        "freq_hz": freq_hz,
        "photo": photo_resp,
        "received_at_ms": int(time.time() * 1000),
    }

@router.post("/v1/drone/vs/stop")
async def vs_stop(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    await _runner.stop()
    return {"ok": True, "detail": "Stopped", "received_at_ms": int(time.time() * 1000)}

@router.post("/v1/drone/media/photo")
async def take_photo(
    body: PhotoRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    resp = await _client.take_photo(upload_url=body.upload_url)
    return {"ok": True, "data": resp, "received_at_ms": int(time.time() * 1000)}
