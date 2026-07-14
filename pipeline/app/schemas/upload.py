"""
Upload-related Pydantic schemas.
"""
from pydantic import BaseModel


class FileInfo(BaseModel):
    filename: str
    file_type: str          # "pdf" | "image"
    size_bytes: int
    page_count: int | None  # Only for PDFs


class UploadResponse(BaseModel):
    job_id: str
    files: list[FileInfo]
    total_pages: int
