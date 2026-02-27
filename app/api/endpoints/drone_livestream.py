# app/api/endpoints/drone_livestream.py
import os, time
from fastapi import APIRouter, Request, HTTPException
from app.services.security import enforce_api_key, enforce_lan_only
from app.api.endpoints.drone_sse import enqueue_command

router = APIRouter()

# in-memory state (good enough for LAN demo)
_live = {}  # device_id -> {rtmp_url, started_at_ms}

RTMP_INGEST_BASE = os.getenv("RTMP_INGEST_BASE", "rtmp://192.168.1.49:1935/live")
# Optional: where clients should PLAY (depends on your media server)
PLAY_BASE = os.getenv("STREAM_PLAY_BASE", "")  # e.g. "http://192.168.1.49:8080/live"

@router.post("/v1/drone/livestream/start")
async def livestream_start(request: Request, body: dict):
    enforce_lan_only(request)
    enforce_api_key(request)

    device_id = (body.get("device_id") or "android-controller-01").strip()
    rtmp_url = (body.get("rtmp_url") or "").strip()
    if not rtmp_url:
        rtmp_url = f"{RTMP_INGEST_BASE}/{device_id}"

    await enqueue_command(device_id=device_id, cmd_type="LIVESTREAM_START", payload={"rtmp_url": rtmp_url})
    _live[device_id] = {"rtmp_url": rtmp_url, "started_at_ms": int(time.time() * 1000)}

    resp = {"ok": True, "device_id": device_id, "rtmp_url": rtmp_url}
    if PLAY_BASE:
        # common convention for HTTP-FLV/HLS/WebRTC depends on server; keep it simple
        resp["play_hint"] = f"{PLAY_BASE}/{device_id}"
    return resp

@router.post("/v1/drone/livestream/stop")
async def livestream_stop(request: Request, body: dict):
    enforce_lan_only(request)
    enforce_api_key(request)

    device_id = (body.get("device_id") or "android-controller-01").strip()
    await enqueue_command(device_id=device_id, cmd_type="LIVESTREAM_STOP", payload={})
    _live.pop(device_id, None)
    return {"ok": True, "device_id": device_id}

@router.get("/v1/drone/livestream/status")
async def livestream_status(request: Request, device_id: str = "android-controller-01"):
    enforce_lan_only(request)
    enforce_api_key(request)
    return {"ok": True, "device_id": device_id, "state": _live.get(device_id)}