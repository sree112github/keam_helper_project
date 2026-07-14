"""
ORM models.

- KeamCutoffRank: mirrors the EXISTING table owned by the Go backend.
  Never run create_all on this — it's here for reading/writing only.

- OcrProcessingJob, OcrProcessingLog: pipeline-specific tables managed here.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ── Shared base (includes keam_cutoff_ranks) ──────────────────────────────────
class Base(DeclarativeBase):
    pass


class KeamCutoffRank(Base):
    """
    Mirrors the existing keam_cutoff_ranks table.
    The Go backend owns this table — we only INSERT/UPDATE records here.
    """
    __tablename__ = "keam_cutoff_ranks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    round: Mapped[str] = mapped_column(String, nullable=False)
    course: Mapped[str] = mapped_column(String, nullable=False)
    college_code: Mapped[str] = mapped_column(String, nullable=False)
    college_name: Mapped[str] = mapped_column(String, nullable=False)
    college_type: Mapped[str] = mapped_column(String, nullable=False)
    ranks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<KeamCutoffRank year={self.year} round={self.round!r} "
            f"course={self.course!r} college_code={self.college_code!r}>"
        )


# ── Pipeline-specific base (we own these tables) ─────────────────────────────
class PipelineBase(DeclarativeBase):
    pass


class OcrProcessingJob(PipelineBase):
    """Tracks one OCR processing job (one upload session)."""
    __tablename__ = "ocr_processing_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="uploaded",
        # States: uploaded → processing → completed → inserted → failed
    )
    file_names = Column(ARRAY(Text), nullable=False, default=list)
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    processed_images: Mapped[int] = mapped_column(Integer, default=0)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    valid_records: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<OcrProcessingJob id={self.id!r} status={self.status!r}>"


class OcrProcessingLog(PipelineBase):
    """Per-image OCR log entry for debugging and auditing."""
    __tablename__ = "ocr_processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    image_filename: Mapped[str] = mapped_column(String, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<OcrProcessingLog job={self.job_id!r} "
            f"image={self.image_filename!r} count={self.extracted_count}>"
        )
