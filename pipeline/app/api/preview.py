"""
Preview API — search, sort, paginate, edit, and delete extracted records.
Records are stored in filesystem JSON and loaded on demand.
"""
import math
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.data_cleaner import clean_record
from app.core.ocr_pipeline import OcrPipeline
from app.core.validator import validate_records, check_batch_duplicates
from app.db import repository
from app.dependencies import db_session
from app.schemas.preview import PaginatedPreview, PreviewStats
from app.schemas.record import CutoffRecord, CutoffRecordUpdate
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/preview", tags=["preview"])

_pipeline = OcrPipeline()


def _compute_stats(records: list[dict[str, Any]]) -> PreviewStats:
    total = len(records)
    valid = sum(1 for r in records if r.get("is_valid"))
    new_rec = sum(1 for r in records if r.get("db_status") == "new")
    update_rec = sum(1 for r in records if r.get("db_status") == "update")
    govt = sum(1 for r in records if r.get("college_type") == "G")
    return PreviewStats(
        total=total,
        valid=valid,
        invalid=total - valid,
        new_records=new_rec,
        update_records=update_rec,
        govt_records=govt,
        non_govt_records=total - govt,
    )


def _filter_records(
    records: list[dict[str, Any]],
    search: str | None,
) -> list[dict[str, Any]]:
    """Filter records by search term (matches course, college_name, college_code)."""
    if not search:
        return records
    term = search.lower().strip()
    return [
        r for r in records
        if term in str(r.get("course", "")).lower()
        or term in str(r.get("college_name", "")).lower()
        or term in str(r.get("college_code", "")).lower()
    ]


def _sort_records(
    records: list[dict[str, Any]],
    sort_by: str,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Sort records by a field."""
    valid_fields = {"course", "college_code", "college_name", "college_type", "year", "round"}
    if sort_by not in valid_fields:
        return records
    reverse = sort_order.lower() == "desc"
    return sorted(
        records,
        key=lambda r: str(r.get(sort_by) or "").lower(),
        reverse=reverse,
    )


@router.get("/{job_id}", response_model=PaginatedPreview)
async def get_preview(
    job_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=1000),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="course"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(db_session),
) -> PaginatedPreview:
    """
    Get paginated preview of extracted records for a job.
    Supports search across course, college name, and college code.
    Also performs DB conflict detection for NEW/UPDATE badges.
    """
    try:
        all_records = _pipeline.load_results(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Perform DB conflict detection on first access (db_status not yet set)
    if all_records and "db_status" not in all_records[0]:
        govt_records = [r for r in all_records if r.get("college_type") == "G"]
        try:
            conflicts = await repository.check_conflicts(session, govt_records)
        except Exception as exc:
            logger.warning("Conflict check failed (non-fatal): %s", exc)
            conflicts = {}

        for rec in all_records:
            key = f"{rec.get('year')}|{rec.get('round')}|{rec.get('course')}|{rec.get('college_code')}"
            if rec.get("college_type") == "G":
                rec["db_status"] = "update" if conflicts.get(key) else "new"
            else:
                rec["db_status"] = "new"

        _pipeline.save_results(job_id, all_records)

    # Apply filters and sorting
    # Filter out non-G (Government) colleges as per user request
    filtered = [r for r in all_records if r.get("college_type") == "G"]
    filtered = _filter_records(filtered, search)
    sorted_records = _sort_records(filtered, sort_by, sort_order)

    # Paginate
    total = len(sorted_records)
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    page_records = sorted_records[offset : offset + per_page]

    # Build response
    stats = _compute_stats(all_records)
    cutoff_records = [CutoffRecord(**r) for r in page_records]

    return PaginatedPreview(
        records=cutoff_records,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        stats=stats,
    )


@router.get("/{job_id}/stats", response_model=PreviewStats)
async def get_stats(job_id: str) -> PreviewStats:
    """Return summary statistics for a job's extracted records."""
    try:
        records = _pipeline.load_results(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _compute_stats(records)


@router.put("/{job_id}/records/{idx}", response_model=CutoffRecord)
async def update_record(
    job_id: str,
    idx: int,
    update: CutoffRecordUpdate,
) -> CutoffRecord:
    """
    Edit a single record in the preview batch.
    Re-validates the record after editing.
    """
    try:
        records = _pipeline.load_results(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Find record by index
    target = next((r for r in records if r.get("index") == idx), None)
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"Record with index {idx} not found."
        )

    # Apply updates (only provided fields)
    updated_data = update.model_dump(exclude_none=True)
    target.update(updated_data)

    # Re-clean and re-validate
    cleaned = clean_record(target)
    cleaned["source_image"] = target.get("source_image", "")
    cleaned["index"] = idx
    cleaned["db_status"] = target.get("db_status", "new")

    validated_list = validate_records([cleaned])
    validated = validated_list[0]

    # Replace in the list
    for i, r in enumerate(records):
        if r.get("index") == idx:
            records[i] = validated
            break

    _pipeline.save_results(job_id, records)
    logger.info("Updated record idx=%d for job %s", idx, job_id)

    return CutoffRecord(**validated)


@router.delete("/{job_id}/records/{idx}", status_code=204)
async def delete_record(job_id: str, idx: int) -> None:
    """Remove a single record from the preview batch."""
    try:
        records = _pipeline.load_results(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    original_count = len(records)
    records = [r for r in records if r.get("index") != idx]

    if len(records) == original_count:
        raise HTTPException(
            status_code=404, detail=f"Record with index {idx} not found."
        )

    _pipeline.save_results(job_id, records)
    logger.info("Deleted record idx=%d from job %s", idx, job_id)
