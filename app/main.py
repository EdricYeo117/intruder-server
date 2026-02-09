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
from .api.endpoints.drone import router as drone_router
from .services.dji_controller_client import DJIControllerClient

load_dotenv()

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "8192"))

app = FastAPI()
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

    print("INTRUSION EVENT:", event.model_dump())

    cmd = build_scripted_flight_path(event.model_dump())
    print("[CMD] dispatching:", cmd)

    background.add_task(post_commands, cmd)
    return {"ok": True, "received_at_ms": int(time.time() * 1000)}
