"""
OCR schemas for raw Ollama responses.
"""
from pydantic import BaseModel


class RawOCRResponse(BaseModel):
    image_path: str
    raw_text: str
    attempt: int
    success: bool
    error: str | None = None


class OCRResult(BaseModel):
    image_path: str
    records: list[dict]      # Raw parsed records before cleaning/validation
    attempt: int
    processing_time_ms: int
    error: str | None = None
