"""
Insert API — moves approved records from preview into PostgreSQL.
Only inserts college_type = 'G' records.
Uses upsert for idempotency.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ocr_pipeline import OcrPipeline
from app.core.validator import validate_records
from app.db import repository
from app.dependencies import db_session
from app.utils.file_utils import cleanup_job_dirs
from app.config import get_settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["insert"])

_pipeline = OcrPipeline()


class InsertPayload(BaseModel):
    global_year: int | None = None
    global_round: str | None = None


class InsertResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    failed: int
    errors: list[str]
    message: str


@router.post("/insert/{job_id}", response_model=InsertResult)
async def insert_approved_data(
    job_id: str,
    payload: InsertPayload,
    session: AsyncSession = Depends(db_session),
) -> InsertResult:
    """
    Insert all approved (valid) government college records into PostgreSQL.

    Steps:
    1. Load results from filesystem JSON.
    2. Filter to valid records only (is_valid=True).
    3. Re-validate to catch any edits that bypassed validation.
    4. Upsert into keam_cutoff_ranks (ON CONFLICT DO UPDATE).
    5. Cleanup temporary files.
    6. Return insert summary.
    """
    # Load results
    try:
        records = _pipeline.load_results(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not records:
        raise HTTPException(status_code=400, detail="No records found for this job.")

    from app.core.data_cleaner import _parse_other_categories

    # Apply global overrides (if provided by user, they overwrite the extracted values)
    for r in records:
        if payload.global_year:
            r["year"] = payload.global_year
        if payload.global_round:
            r["round"] = payload.global_round
        
        # Parse 'other_categories' and merge into ranks before validation and insertion
        other = r.get("other_categories")
        if other and isinstance(other, str):
            parsed_ranks = _parse_other_categories(other)
            for k, v in parsed_ranks.items():
                if v is not None:
                    r["ranks"][k] = v
        # We can remove other_categories from the record payload here so it isn't saved to DB
        r.pop("other_categories", None)

    # Filter valid records only. 
    # Note: Because year and round are required for validity, applying the 
    # global fallbacks might make previously invalid records valid. 
    # We re-run the core validator on ALL records to get fresh validity state.
    validated = validate_records(records)
    
    # Enforce year and round at insert time
    for r in validated:
        y = r.get("year")
        if not y or not (2020 <= y <= 2035):
            r["is_valid"] = False
            r.setdefault("validation_errors", []).append("Missing year (provide a default).")
        if not r.get("round"):
            r["is_valid"] = False
            r.setdefault("validation_errors", []).append("Missing round (provide a default).")

    valid_records: list[dict[str, Any]] = [
        r for r in validated if r.get("is_valid")
    ]
    if not valid_records:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid records to insert. "
                "All records have validation errors — fix them in the preview first."
            ),
        )

    # We already re-validated above, so valid_records are safe to use.
    final_records = valid_records
    rejected_count = len(records) - len(final_records)

    if rejected_count > 0:
        logger.warning(
            "Re-validation rejected %d records that appeared valid in preview.",
            rejected_count,
        )

    if not final_records:
        raise HTTPException(
            status_code=400,
            detail="All records failed re-validation. Cannot insert.",
        )

    errors: list[str] = []
    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    try:
        counts = await repository.batch_upsert(session, final_records)
    except Exception as exc:
        logger.error("Batch upsert failed for job %s: %s", job_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database insert failed: {exc}. No records were committed.",
        ) from exc

    # Cleanup temporary files after successful insert
    settings = get_settings()
    try:
        cleanup_job_dirs(
            job_id,
            images_dir=settings.IMAGES_DIR,
            results_dir=settings.RESULTS_DIR,
            uploads_dir=settings.UPLOAD_DIR,
        )
    except Exception as exc:
        logger.warning("Cleanup failed for job %s (non-fatal): %s", job_id, exc)
        errors.append(f"Cleanup warning: {exc}")

    if rejected_count > 0:
        errors.append(
            f"{rejected_count} records failed re-validation and were skipped."
        )

    message = (
        f"Successfully inserted {counts['inserted']} new records, "
        f"updated {counts['updated']} existing records. "
        f"Skipped {counts['skipped']} non-government records."
    )
    logger.info(message)

    return InsertResult(
        inserted=counts["inserted"],
        updated=counts["updated"],
        skipped=counts["skipped"],
        failed=rejected_count,
        errors=errors,
        message=message,
    )
