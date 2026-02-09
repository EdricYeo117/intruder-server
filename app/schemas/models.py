from pydantic import BaseModel, Field
from typing import Optional, Literal

EventType = Literal[
    "PERSON_DETECTED",
    "PERSON_STILL_PRESENT",
    "PERSON_LEFT",          # optional if you add it later
]

class IntrusionEvent(BaseModel):
    event_type: EventType
    timestamp_ms: int = Field(..., ge=0)
    device_id: str = Field(..., min_length=1, max_length=64)
    score: float = Field(..., ge=0.0, le=1.0)
    event_id: Optional[str] = Field(default=None, max_length=128)
