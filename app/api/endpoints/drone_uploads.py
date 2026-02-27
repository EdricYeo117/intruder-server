# app/api/endpoints/drone_uploads.py
import os, time
from fastapi import APIRouter, UploadFile, File, Request
from app.services.security import enforce_api_key, enforce_lan_only

router = APIRouter()

UPLOAD_DIR = os.getenv("DRONE_UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/v1/drone/uploads/photo")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    enforce_lan_only(request)
    enforce_api_key(request)

    ts = int(time.time() * 1000)
    safe_name = (file.filename or f"photo_{ts}.jpg").replace("/", "_")
    out_path = os.path.join(UPLOAD_DIR, f"{ts}_{safe_name}")

    with open(out_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:   
                break
            f.write(chunk)

    return {"ok": True, "saved_to": out_path}

@router.post("/v1/drone/uploads/video")
async def upload_video(request: Request, file: UploadFile = File(...)):
    enforce_lan_only(request)
    enforce_api_key(request)

    ts = int(time.time() * 1000)
    safe_name = (file.filename or f"video_{ts}.mp4").replace("/", "_")
    out_path = os.path.join(UPLOAD_DIR, f"{ts}_{safe_name}")

    with open(out_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    return {"ok": True, "saved_to": out_path}
