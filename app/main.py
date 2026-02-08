import os
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from dotenv import load_dotenv

from .models import IntrusionEvent
from .security import enforce_api_key, enforce_lan_only
from .rate_limit import allow

load_dotenv()

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "8192"))

app = FastAPI()

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
