"""
Preview schemas for paginated data display.
"""
from pydantic import BaseModel

from app.schemas.record import CutoffRecord


class PreviewStats(BaseModel):
    total: int
    valid: int
    invalid: int
    new_records: int
    update_records: int
    govt_records: int
    non_govt_records: int


class PaginatedPreview(BaseModel):
    records: list[CutoffRecord]
    total: int
    page: int
    per_page: int
    total_pages: int
    stats: PreviewStats
