# app/drone_sse.py
import asyncio
import json
import time
import uuid
from typing import Dict, Set, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

# device_id -> set of subscriber queues
_subs: Dict[str, Set[asyncio.Queue]] = {}
_subs_lock = asyncio.Lock()

# optional: track command acks
_pending: Dict[str, dict] = {}   # command_id -> metadata (optional)

def _sse(event: str, data_obj: dict, event_id: Optional[str] = None) -> str:
    # SSE format: optional id, event, data (data must be line-safe)
    data = json.dumps(data_obj, separators=(",", ":"))
    out = []
    if event_id:
        out.append(f"id: {event_id}")
    out.append(f"event: {event}")
    out.append(f"data: {data}")
    out.append("")  # blank line terminates message
    return "\n".join(out) + "\n"

async def enqueue_command(device_id: str, cmd_type: str, payload: dict, command_id: Optional[str] = None):
    """
    Push a single command to all active SSE subscribers for that device_id.
    Command JSON must match your Android CommandDispatcher.kt schema:
      { "cmd_type": "...", "command_id": "...", "payload": {...} }
    """
    if command_id is None:
        command_id = str(uuid.uuid4())

    cmd = {
        "cmd_type": cmd_type,
        "command_id": command_id,
        "payload": payload or {}
    }

    # optional: track pending
    _pending[command_id] = {"device_id": device_id, "cmd": cmd, "ts_ms": int(time.time() * 1000)}

    async with _subs_lock:
        qs = list(_subs.get(device_id, set()))
        total = sum(len(v) for v in _subs.values())

    print(f"[SSE] ENQUEUE device_id={device_id} cmd_type={cmd_type} subs_for_device={len(qs)} total_subs={total} command_id={command_id}")

    # if nobody connected, you can decide to drop, or store for later replay
    for q in qs:
        # avoid blocking if client is slow
        try:
            q.put_nowait(cmd)
        except asyncio.QueueFull:
            pass

@router.get("/v1/drone/stream")
async def drone_stream(request: Request, device_id: str):
    # If you require auth, do it via middleware or check header here.
    q: asyncio.Queue = asyncio.Queue(maxsize=200)

    async with _subs_lock:
        _subs.setdefault(device_id, set()).add(q)
        total = sum(len(v) for v in _subs.values())
        per = len(_subs.get(device_id, set()))

    print(f"[SSE] CONNECT device_id={device_id} from={request.client.host if request.client else '?'} subs_for_device={per} total_subs={total}")

    async def gen():
        # initial hello (optional)
        yield _sse("status", {"status": "connected", "device_id": device_id, "ts_ms": int(time.time()*1000)})

        last_ping = time.time()

        try:
            while True:
                # client disconnected?
                if await request.is_disconnected():
                    break

                try:
                    # wait for a command, but also send keepalive ping
                    cmd = await asyncio.wait_for(q.get(), timeout=10.0)
                    yield _sse("command", cmd, event_id=cmd.get("command_id"))
                except asyncio.TimeoutError:
                    # keepalive (prevents idle timeouts on some networks/proxies)
                    now = time.time()
                    if now - last_ping >= 10.0:
                        last_ping = now
                        yield _sse("ping", {"ts_ms": int(now * 1000)})
        finally:
            async with _subs_lock:
                s = _subs.get(device_id)
                if s:
                    s.discard(q)
                    if not s:
                        _subs.pop(device_id, None)
                total = sum(len(v) for v in _subs.values())
                per = len(_subs.get(device_id, set()))
            print(f"[SSE] DISCONNECT device_id={device_id} subs_for_device={per} total_subs={total}")

    return StreamingResponse(gen(), media_type="text/event-stream")

@router.post("/v1/drone/ack")
async def drone_ack(body: dict):
    """
    Android calls this via DroneHttpClient.postAck():
      { device_id, command_id, ok, error }
    """
    device_id = (body.get("device_id") or "").strip()
    command_id = (body.get("command_id") or "").strip()
    ok = bool(body.get("ok"))
    error = body.get("error")

    if not device_id or not command_id:
        raise HTTPException(status_code=400, detail="Missing device_id/command_id")

   
    if meta and meta.get("device_id") != device_id:
        raise HTTPException(status_code=400, detail="Ack device mismatch")

    # mark as done
    removed = _pending.pop(command_id, None)

    print(
        f"[ACK] device_id={device_id} command_id={command_id} "
        f"ok={ok} error={error} pending_found={removed is not None}"
    )

    return {"ok": True, "device_id": device_id, "command_id": command_id, "ack_ok": ok, "error": error}

@router.get("/v1/drone/clients")
async def clients():
    async with _subs_lock:
        return {
            "devices": {k: len(v) for k, v in _subs.items()},
            "total_subs": sum(len(v) for v in _subs.values()),
        }
