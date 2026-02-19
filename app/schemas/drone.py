# app/schemas/drone.py
from pydantic import BaseModel, Field

class EnableVSRequest(BaseModel):
    enabled: bool = True
    advanced: Optional[bool] = False

class MoveSequenceRequest(BaseModel):
    leftX: int = Field(0, ge=-660, le=660)
    leftY: int = Field(0, ge=-660, le=660)
    rightX: int = Field(0, ge=-660, le=660)
    rightY: int = Field(0, ge=-660, le=660)

    duration_ms: int = Field(800, ge=50, le=600000)
    freq_hz: int | None = Field(None, ge=1, le=50)

    # NEW: for your testing
    wait: bool = True                  # if True, endpoint blocks until movement ends
    take_photo_after: bool = False     # if True, trigger camera after movement
    upload_url: str | None = None      # optional: if Android listener uploads to Node-RED

class PhotoRequest(BaseModel):
    upload_url: str | None = None
