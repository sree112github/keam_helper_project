"""
Shared Pydantic schemas used across all API responses.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""
    success: bool = True
    data: T | None = None
    message: str = "OK"


class ErrorDetail(BaseModel):
    """Structured error detail for failed operations."""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    success: bool = False
    error: ErrorDetail


class PaginationParams(BaseModel):
    """Common pagination query parameters."""
    page: int = 1
    per_page: int = 25

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    model_config = {"extra": "ignore"}
