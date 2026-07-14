"""
Settings API — get and set runtime OCR configurations.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings, runtime_settings

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsResponse(BaseModel):
    ocr_provider: str
    has_gemini_key: bool
    gemini_model: str


class SettingsUpdateRequest(BaseModel):
    ocr_provider: str


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_state() -> SettingsResponse:
    """Get current configuration and runtime OCR provider."""
    settings = get_settings()
    return SettingsResponse(
        ocr_provider=runtime_settings.ocr_provider,
        has_gemini_key=bool(settings.GEMINI_API_KEY),
        gemini_model=settings.GEMINI_MODEL,
    )


@router.post("/settings", response_model=SettingsResponse)
async def update_settings_state(payload: SettingsUpdateRequest) -> SettingsResponse:
    """Update runtime OCR provider dynamically."""
    if payload.ocr_provider not in ("ollama", "gemini"):
        raise HTTPException(
            status_code=400,
            detail="Invalid OCR provider. Must be 'ollama' or 'gemini'.",
        )

    runtime_settings.ocr_provider = payload.ocr_provider
    settings = get_settings()
    return SettingsResponse(
        ocr_provider=runtime_settings.ocr_provider,
        has_gemini_key=bool(settings.GEMINI_API_KEY),
        gemini_model=settings.GEMINI_MODEL,
    )
