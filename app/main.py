import os
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
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
async def intrusion_events(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    enforce_api_key(x_api_key)
    enforce_lan_only(request)

    body_bytes = await request.body()
    if len(body_bytes) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    try:
        payload = IntrusionEvent.model_validate_json(body_bytes)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid payload")

    if not allow(payload.device_id):
        raise HTTPException(status_code=429, detail="Rate limited")

    print("INTRUSION EVENT:", payload.model_dump())
    return {"ok": True, "received_at_ms": int(time.time() * 1000)}
