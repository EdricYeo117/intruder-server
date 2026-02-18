import os
from fastapi import HTTPException, Request
from dotenv import load_dotenv

load_dotenv()

API_KEY = (os.getenv("API_KEY") or os.getenv("RED_API_KEY") or "").strip()  # required if non-empty
ALLOW_LAN_ONLY = (os.getenv("ALLOW_LAN_ONLY", "true").lower() == "true")

_PRIVATE_PREFIXES = (
    "127.", "192.168.", "10.",
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
    "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.",
)

def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)

def _mask(k: str) -> str:
    k = (k or "").strip()
    if not k:
        return "None"
    n = len(k)
    return f"{k[:4]}***{k[-4:]}(len={n})" if n > 8 else f"{k[:2]}***{k[-2:]}(len={n})"

def enforce_lan_only(request: Request) -> None:
    if not ALLOW_LAN_ONLY:
        return
    ip = request.client.host if request.client else ""
    if ip and not _is_private(ip):
        raise HTTPException(status_code=403, detail="Forbidden (LAN only)")

def enforce_api_key(arg=None, *, x_api_key: str | None = None) -> None:
    """
    Backwards compatible:

      enforce_api_key(request)          # preferred (reads request headers)
      enforce_api_key(x_api_key="...")  # allowed
      enforce_api_key("...")            # allowed

    """
    received = ""

    if isinstance(arg, Request):
        received = (arg.headers.get("x-api-key") or "").strip()
    elif isinstance(arg, str):
        received = (arg or "").strip()
    elif x_api_key is not None:
        received = (x_api_key or "").strip()

    print(f"[AUTH] expected={_mask(API_KEY)} received={_mask(received)} raw_received_len={len(received)}")

    if API_KEY and received != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/v1/intrusion/events")
async def intrusion_events(request: Request):
    enforce_lan_only(request)
    enforce_api_key(request)

    body = await request.json()
    print("INTRUSION EVENT:", body)
    return {"ok": True, "received_at_ms": int(time.time() * 1000)}
