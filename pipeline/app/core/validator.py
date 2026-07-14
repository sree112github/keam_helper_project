"""
Validation service.
Validates cleaned records against schema and business rules.
Collects ALL errors per record (fail-all, not fail-fast).
"""
import re
from typing import Any

from app.core.data_cleaner import KNOWN_CATEGORIES
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# 3-letter uppercase college code pattern
_COLLEGE_CODE_RE = re.compile(r"^[A-Z]{2,4}$")

VALID_COLLEGE_TYPES = {"G", "S"}
MIN_YEAR = 2020
MAX_YEAR = 2035


def validate_record(record: dict[str, Any]) -> list[str]:
    """
    Validate a single cleaned record.
    Returns a list of error messages (empty list = valid).
    """
    errors: list[str] = []

    # year (optional during preview, checked at insert)
    year = record.get("year")
    if year is not None and not (MIN_YEAR <= year <= MAX_YEAR):
        errors.append(f"Year {year} is outside expected range ({MIN_YEAR}–{MAX_YEAR}).")

    # round (optional during preview, checked at insert)

    # course
    if not record.get("course"):
        errors.append("Missing course name.")

    # college_code
    code = record.get("college_code", "")
    if not code:
        errors.append("Missing college_code.")
    elif not _COLLEGE_CODE_RE.match(code):
        errors.append(
            f"Invalid college_code format: {code!r}. Expected 2–4 uppercase letters."
        )

    # college_name (optional, auto-filled or ignored if missing)

    # college_type
    ctype = record.get("college_type", "")
    if ctype not in VALID_COLLEGE_TYPES:
        errors.append(
            f"Invalid college_type: {ctype!r}. Expected 'G' or 'S'."
        )


    # ranks
    ranks = record.get("ranks")
    if ranks is None or not isinstance(ranks, dict):
        errors.append("ranks must be a dictionary.")
    elif len(ranks) == 0:
        errors.append("ranks is empty — no category data extracted.")
    else:
        # Validate individual rank values
        for code_key, val in ranks.items():
            if val is not None and not isinstance(val, int):
                errors.append(
                    f"Rank value for {code_key!r} must be int or null, got {type(val).__name__}."
                )
            if isinstance(val, int) and val <= 0:
                errors.append(f"Rank value for {code_key!r} is non-positive: {val}.")

    # Internal cleaning error flag
    if record.get("_clean_error"):
        errors.append(f"Cleaning error: {record['_clean_error']}")

    return errors


def validate_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Validate a list of cleaned records.
    Returns each record annotated with:
      - is_valid: bool
      - validation_errors: list[str]
    """
    result: list[dict[str, Any]] = []
    valid_count = 0
    invalid_count = 0

    for i, record in enumerate(records):
        errors = validate_record(record)
        annotated = {**record, "is_valid": len(errors) == 0, "validation_errors": errors}
        result.append(annotated)
        if errors:
            invalid_count += 1
            logger.debug(
                "Record %d invalid (%s/%s): %s",
                i, record.get("college_code"), record.get("course"), errors,
            )
        else:
            valid_count += 1

    logger.info(
        "Validation complete: %d valid, %d invalid out of %d records",
        valid_count, invalid_count, len(records),
    )
    return result


def check_batch_duplicates(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect duplicate records within the current batch
    (same year + round + course + college_code).
    Marks duplicates with an additional validation error.
    """
    seen: dict[tuple, int] = {}
    for i, record in enumerate(records):
        key = (
            record.get("year"),
            record.get("round"),
            record.get("course"),
            record.get("college_code"),
        )
        if key in seen:
            dup_msg = (
                f"Duplicate record in batch (same as record #{seen[key] + 1}). "
                f"Key: {key}"
            )
            records[i]["validation_errors"].append(dup_msg)
            records[i]["is_valid"] = False
            logger.warning("Batch duplicate detected at index %d: %s", i, key)
        else:
            seen[key] = i
    return records
