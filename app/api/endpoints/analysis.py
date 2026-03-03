from fastapi import APIRouter, HTTPException, Request, Query
from app.services.security import enforce_api_key, enforce_lan_only
from app.services.analysis_store import STORE

router = APIRouter()

@router.get("/v1/drone/analysis/recent")
def recent(request: Request, limit: int = Query(50, ge=1, le=200)):
    enforce_lan_only(request)
    enforce_api_key(request)
    return {"ok": True, "items": STORE.recent(limit)}

@router.get("/v1/drone/analysis/{analysis_id}")
def get_one(request: Request, analysis_id: str):
    enforce_lan_only(request)
    enforce_api_key(request)
    try:
        return STORE.load(analysis_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))