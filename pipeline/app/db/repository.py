"""
Database repository layer.
All SQL interactions go through this module — no raw SQL in API handlers.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KeamCutoffRank, OcrProcessingJob, OcrProcessingLog
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


# ── Job management ────────────────────────────────────────────────────────────

async def create_job(
    session: AsyncSession,
    file_names: list[str],
) -> OcrProcessingJob:
    """Create a new processing job record."""
    job = OcrProcessingJob(
        id=str(uuid.uuid4()),
        status="uploaded",
        file_names=file_names,
    )
    session.add(job)
    await session.flush()
    logger.info("Created job %s with %d files", job.id, len(file_names))
    return job


async def get_job(session: AsyncSession, job_id: str) -> OcrProcessingJob | None:
    """Fetch a job by ID."""
    result = await session.execute(
        select(OcrProcessingJob).where(OcrProcessingJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    status: str,
    **kwargs: Any,
) -> None:
    """Update job status and optional numeric fields."""
    values: dict[str, Any] = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    if status in ("completed", "inserted", "failed"):
        values["completed_at"] = datetime.now(timezone.utc)

    await session.execute(
        update(OcrProcessingJob)
        .where(OcrProcessingJob.id == job_id)
        .values(**values)
    )
    logger.debug("Job %s → status=%s extra=%s", job_id, status, kwargs)


async def list_jobs(session: AsyncSession, limit: int = 20) -> list[OcrProcessingJob]:
    """List recent jobs ordered by creation time descending."""
    result = await session.execute(
        select(OcrProcessingJob)
        .order_by(OcrProcessingJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Log management ────────────────────────────────────────────────────────────

async def create_log_entry(
    session: AsyncSession,
    job_id: str,
    image_filename: str,
    raw_response: str | None = None,
    extracted_count: int = 0,
    error_message: str | None = None,
    processing_time_ms: int | None = None,
) -> OcrProcessingLog:
    """Append an OCR log entry for a single image."""
    log = OcrProcessingLog(
        job_id=job_id,
        image_filename=image_filename,
        raw_response=raw_response,
        extracted_count=extracted_count,
        error_message=error_message,
        processing_time_ms=processing_time_ms,
    )
    session.add(log)
    await session.flush()
    return log


async def get_logs_for_job(
    session: AsyncSession, job_id: str
) -> list[OcrProcessingLog]:
    """Fetch all log entries for a given job."""
    result = await session.execute(
        select(OcrProcessingLog)
        .where(OcrProcessingLog.job_id == job_id)
        .order_by(OcrProcessingLog.id)
    )
    return list(result.scalars().all())


# ── keam_cutoff_ranks interactions ────────────────────────────────────────────

async def check_conflicts(
    session: AsyncSession,
    records: list[dict[str, Any]],
) -> dict[str, bool]:
    """
    For each record, check if (year, round, course, college_code) already exists.
    Returns a dict keyed by "<year>|<round>|<course>|<college_code>" → True if exists.
    """
    if not records:
        return {}

    conflicts: dict[str, bool] = {}
    for record in records:
        key = f"{record['year']}|{record['round']}|{record['course']}|{record['college_code']}"
        result = await session.execute(
            select(KeamCutoffRank.id).where(
                KeamCutoffRank.year == record["year"],
                KeamCutoffRank.round == record["round"],
                KeamCutoffRank.course == record["course"],
                KeamCutoffRank.college_code == record["college_code"],
            )
        )
        conflicts[key] = result.scalar_one_or_none() is not None

    logger.debug(
        "Conflict check: %d records, %d existing",
        len(records),
        sum(1 for v in conflicts.values() if v),
    )
    return conflicts


async def batch_upsert(
    session: AsyncSession,
    records: list[dict[str, Any]],
) -> dict[str, int]:
    """
    Batch upsert records into keam_cutoff_ranks.
    Uses PostgreSQL ON CONFLICT ... DO UPDATE for idempotency.
    Only inserts records where college_type = 'G'.

    Returns counts: inserted, updated, skipped.
    """
    inserted = 0
    updated = 0
    skipped = 0

    govt_records = [r for r in records if r.get("college_type") == "G"]
    skipped = len(records) - len(govt_records)

    if not govt_records:
        logger.info("No government college records to insert (all skipped).")
        return {"inserted": 0, "updated": 0, "skipped": skipped}

    # Check which records already exist before upsert
    conflicts = await check_conflicts(session, govt_records)

    # Batch in chunks of 100
    chunk_size = 100
    for i in range(0, len(govt_records), chunk_size):
        chunk = govt_records[i : i + chunk_size]

        stmt = pg_insert(KeamCutoffRank).values(
            [
                {
                    "year": r["year"],
                    "round": r["round"],
                    "course": r["course"],
                    "college_code": r["college_code"],
                    "college_name": r["college_name"],
                    "college_type": r["college_type"],
                    "ranks": r["ranks"],
                }
                for r in chunk
            ]
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["year", "round", "course", "college_code"],
            set_={
                "college_name": stmt.excluded.college_name,
                "college_type": stmt.excluded.college_type,
                "ranks": stmt.excluded.ranks,
            },
        )
        await session.execute(stmt)

    # Count inserted vs updated
    for record in govt_records:
        key = f"{record['year']}|{record['round']}|{record['course']}|{record['college_code']}"
        if conflicts.get(key):
            updated += 1
        else:
            inserted += 1

    logger.info(
        "Batch upsert complete: inserted=%d updated=%d skipped=%d",
        inserted, updated, skipped,
    )
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


async def get_existing_record_count(session: AsyncSession, year: int) -> int:
    """Count how many records exist for a given year."""
    result = await session.execute(
        select(text("COUNT(*)")).select_from(KeamCutoffRank).where(
            KeamCutoffRank.year == year
        )
    )
    return result.scalar() or 0
