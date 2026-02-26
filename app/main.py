import os
import time
from typing import Optional
import httpx
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.schemas.models import IntrusionEvent
from app.services.security import enforce_api_key, enforce_lan_only
from app.services.rate_limit import allow

# NEW:
from app.api.endpoints.drone import router as drone_router
from app.api.endpoints.drone_sse import router as drone_sse_router, enqueue_command
from app.api.endpoints.drone_uploads import router as drone_uploads_router
from app.api.endpoints.drone_livestream import router as drone_livestream_router
from app.services.dji_controller_client import DJIControllerClient

load_dotenv()

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "8192"))
DRONE_DEVICE_ID = os.getenv("DRONE_DEVICE_ID", "android-controller-01")
SERVER_PUBLIC_BASE = os.getenv("SERVER_PUBLIC_BASE", "http://192.168.1.49:8080") 

app = FastAPI()
@app.on_event("startup")
async def _startup():
    print("[BOOT] intruder-server starting up")
    print(f"[BOOT] DRONE_DEVICE_ID={DRONE_DEVICE_ID}")
    print(f"[BOOT] SERVER_PUBLIC_BASE={SERVER_PUBLIC_BASE}")

    # show which SSE devices are currently connected (will be empty at boot)
    try:
        from .api.endpoints import drone_sse
        print("[BOOT] SSE router mounted: /v1/drone/stream, /v1/drone/clients, /v1/drone/ack")
    except Exception as e:
        print(f"[BOOT] SSE import check failed: {type(e).__name__}: {e}")

    # Optional: print all registered routes (helps confirm routers are included)
    try:
        routes = []
        for r in app.routes:
            methods = ",".join(sorted(getattr(r, "methods", []) or []))
            routes.append(f"{methods:12s} {getattr(r, 'path', '')}")
        print("[BOOT] Registered routes:")
        for line in routes:
            print("  " + line)
    except Exception as e:
        print(f"[BOOT] route listing failed: {type(e).__name__}: {e}")

    print("[BOOT] startup complete")

@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    start = time.time()
    client_ip = request.client.host if request.client else "?"
    client_port = request.client.port if request.client else "?"
    path = request.url.path

    print(f"[REQ] {client_ip}:{client_port} {request.method} {path}")

    try:
        response = await call_next(request)
    except Exception as e:
        # If something crashes inside, you still see it
        print(f"[ERR] {request.method} {path} exception={type(e).__name__}: {e}")
        raise

    ms = int((time.time() - start) * 1000)
    print(f"[RES] {request.method} {path} -> {response.status_code} ({ms}ms)")
    return response

DRONE_COMMAND_URL = os.getenv("DRONE_COMMAND_URL", "http://127.0.0.1:9090/commands")

def build_scripted_flight_path(event: dict) -> dict:
    # Replace this later with your real flight path generator
    return {
        "mission_id": f"intrusion-{int(time.time())}",
        "source_event": event,
        "commands": [
            {"type": "yaw", "deg": 30, "duration_ms": 500},
            {"type": "forward", "mps": 0.4, "duration_ms": 2000},
            {"type": "hover", "duration_ms": 1000},
        ],
    }

async def post_commands(cmd_payload: dict) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(DRONE_COMMAND_URL, json=cmd_payload)
        # Helpful debug
        print(f"[CMD] POST -> {DRONE_COMMAND_URL} status={r.status_code}")

# NEW: include router
app.include_router(drone_router)
app.include_router(drone_sse_router)
app.include_router(drone_uploads_router)
app.include_router(drone_livestream_router)

# NEW: clean shutdown for httpx client
@app.on_event("shutdown")
async def _shutdown():
    await DJIControllerClient.aclose_singleton()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/v1/intrusion/events")
async def intrusion_events(event: IntrusionEvent, request: Request, background: BackgroundTasks):
    enforce_lan_only(request)
    enforce_api_key(request)

    payload = event.model_dump()
    print("INTRUSION EVENT:", payload)

    # OPTIONAL: keep your old cmd print for logging only
    cmd = build_scripted_flight_path(payload)
    print("[CMD] dispatching:", cmd)

    # NEW: send mission over SSE to the DJI controller device
    background.add_task(dispatch_intrusion_mission, payload)
    print("[SSE] queued dispatch_intrusion_mission")

    return {"ok": True, "received_at_ms": int(time.time() * 1000)}


async def dispatch_intrusion_mission(source_event: dict) -> None:
    # 1) enable VS
    await enqueue_command(
        device_id=DRONE_DEVICE_ID,
        cmd_type="VS_ENABLE",
        payload={"enabled": True, "reason": "intrusion", "source_event": source_event},
    )

    # 2) move sequence
    moves = [
        {"leftX": 0, "leftY": 0, "rightX": 0, "rightY": 0.25, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": 0, "rightY": -0.25, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": 0.25, "rightY": 0, "durationMs": 800, "hz": 25},
        {"leftX": 0, "leftY": 0, "rightX": -0.25, "durationMs": 800, "hz": 25},
    ]
    await enqueue_command(
        device_id=DRONE_DEVICE_ID,
        cmd_type="MOVE_SEQUENCE",
        payload={"moves": moves, "defaultHz": 25},
    )

    # 3) snapshot (controller uploads back to server)
    await enqueue_command(
        device_id=DRONE_DEVICE_ID,
        cmd_type="SNAPSHOT",
        payload={"upload_url": f"{SERVER_PUBLIC_BASE}/v1/drone/uploads/photo"},
    )