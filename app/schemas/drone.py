from pydantic import BaseModel, Field


class EnableVSRequest(BaseModel):
    enabled: bool = True


class MoveSequenceRequest(BaseModel):
    # match your Android listener contract (/vs/move)
    leftX: int = Field(0, ge=-660, le=660)
    leftY: int = Field(0, ge=-660, le=660)
    rightX: int = Field(0, ge=-660, le=660)
    rightY: int = Field(0, ge=-660, le=660)

    # sequence params controlled by python
    duration_ms: int = Field(800, ge=50, le=600000)
    freq_hz: int | None = Field(None, ge=1, le=50)


class PhotoRequest(BaseModel):
    upload_url: str | None = None
