"""
Record schemas used in preview and insert operations.
"""
from typing import Any, Literal

from pydantic import BaseModel


class CutoffRecord(BaseModel):
    """A single extracted and validated cutoff rank record."""
    index: int                          # Position in batch (for edit/delete)
    year: int | None
    round: str
    course: str
    college_code: str
    college_name: str
    college_type: str
    ranks: dict[str, int | None]
    other_categories: str = ""
    is_valid: bool
    validation_errors: list[str]
    source_image: str                   # Which image produced this record
    db_status: Literal["new", "update"] = "new"  # From conflict detection

    model_config = {"extra": "ignore"}


class CutoffRecordUpdate(BaseModel):
    """Editable fields for inline editing in preview."""
    year: int | None = None
    round: str | None = None
    course: str | None = None
    college_code: str | None = None
    college_name: str | None = None
    college_type: str | None = None
    ranks: dict[str, Any] | None = None
    other_categories: str | None = None
