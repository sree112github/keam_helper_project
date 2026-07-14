"""
Data cleaning service.
Normalizes raw OCR output into clean, type-safe records.
All cleaning is non-destructive — unparseable values become null with a warning.
"""
import re
from typing import Any

from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Known valid category codes from category_info.json
KNOWN_CATEGORIES = {
    "SM", "EZ", "MU", "BH", "LA", "DV", "VK", "BX",
    "KN", "KU", "SC", "ST", "EW", "FW", "SD", "XS",
    "CC", "PD", "PI", "PT", "RP", "HR", "DK", "LG", "MM", "SG"
}


def _clean_rank_value(value: Any) -> int | None:
    """
    Convert a raw rank value to an integer or None.

    Handles:
    - Integer passthrough
    - String with commas: "8,302" → 8302
    - Dash or empty: "-", "", "—" → None
    - None passthrough
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped in {"-", "—", "–", "N/A", "n/a", "nil"}:
            return None
        # Remove commas and spaces from numbers
        cleaned = stripped.replace(",", "").replace(" ", "")
        try:
            num = int(float(cleaned))
            return num if num > 0 else None
        except (ValueError, OverflowError):
            logger.debug("Cannot parse rank value: %r → null", value)
            return None
    return None


def _parse_other_categories(value: Any) -> dict[str, int | None]:
    """
    Parse "Other Categories" column entries like "FW:7355 SD:13549"
    or "FW:7,355\nSD:13,549" into a dict.
    """
    if not value or not isinstance(value, str):
        return {}

    result: dict[str, int | None] = {}
    # Match patterns like CODE:NUMBER, CODE NUMBER, CODE-NUMBER, CODENUMBER
    pattern = re.compile(r"(?<![A-Z])([A-Z]{2,3})(?![A-Z])\s*[:=\-]?\s*([\d,]+|-|—)")
    for match in pattern.finditer(value.upper()):
        code = match.group(1).strip()
        raw_val = match.group(2).strip()
        result[code] = _clean_rank_value(raw_val)

    return result


def _normalize_college_type(raw: Any) -> str:
    """
    Normalize college_type to 'G' or 'S'.
    Defaults to 'G' (Government) if empty or unrecognized.
    """
    if not raw:
        return "G"
    s = str(raw).strip().upper()
    if s in {"G", "GOVT", "GOVERNMENT", "GOV"}:
        return "G"
    if s in {"S", "SELF", "SELF-FINANCING", "SELF FINANCING", "PRIVATE"}:
        return "S"
    return "G"


def _normalize_round(raw: Any) -> str:
    """Normalize round string to consistent casing."""
    if not raw:
        return ""
    s = str(raw).strip()
    # Standardize common patterns
    s = re.sub(r"\bphase\b", "Phase", s, flags=re.IGNORECASE)
    s = re.sub(r"\ballotment\b", "Allotment", s, flags=re.IGNORECASE)
    s = re.sub(r"\bfirst\b", "First", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsecond\b", "Second", s, flags=re.IGNORECASE)
    s = re.sub(r"\bthird\b", "Third", s, flags=re.IGNORECASE)
    return s


def clean_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Clean a single raw OCR record.

    - Cleans all rank values (int | None)
    - Parses "other_categories" if present
    - Normalizes college_type
    - Removes commas from any string-formatted numbers
    - Returns a clean dict matching the DB schema
    """
    ranks: dict[str, int | None] = {}

    other_str = ""

    # Extract main ranks object
    raw_ranks = raw.get("ranks") or {}
    if isinstance(raw_ranks, dict):
        for code, val in raw_ranks.items():
            clean_code = str(code).strip().upper()
            if clean_code in {"OTHER CATEGORIES", "OTHERS", "OTHER", "OTHER_CATEGORIES"}:
                # Keep it as a raw string for the UI
                other_str = str(val) if val is not None else ""
            else:
                ranks[clean_code] = _clean_rank_value(val)
    elif isinstance(raw_ranks, str):
        other_str = raw_ranks

    # Parse "other_categories" field if model extracted it separately
    other = raw.get("other_categories") or raw.get("others") or raw.get("other")
    if other:
        if isinstance(other, dict):
            # If it's a dict, it's already parsed
            for code, val in other.items():
                ranks.setdefault(str(code).strip().upper(), _clean_rank_value(val))
        elif isinstance(other, str):
            other_str = other if not other_str else other_str + ", " + other

    # Remove ranks with completely unknown codes (keep unknowns with a warning)
    unknown_codes = set(ranks.keys()) - KNOWN_CATEGORIES
    if unknown_codes:
        logger.debug(
            "Unknown category codes for %s: %s",
            raw.get("college_code", "?"), unknown_codes,
        )

    return {
        "year": _clean_year(raw.get("year")),
        "round": _normalize_round(raw.get("round")),
        "course": str(raw.get("course") or "").strip(),
        "college_code": str(raw.get("college_code") or "").strip().upper(),
        "college_name": str(raw.get("college_name") or raw.get("name") or "").strip(),
        "college_type": _normalize_college_type(raw.get("college_type") or raw.get("type")),
        "ranks": ranks,
        "other_categories": other_str,
    }


def _clean_year(raw: Any) -> int | None:
    """Parse year to integer."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if 2000 <= raw <= 2100 else None
    try:
        # Handle "KEAM 2026" or "2026" etc.
        match = re.search(r"\b(20\d{2})\b", str(raw))
        if match:
            return int(match.group(1))
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return None


def clean_records(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Clean a list of raw OCR records.
    Never raises — returns best-effort cleaned records.
    """
    cleaned: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_records):
        try:
            cleaned.append(clean_record(raw))
        except Exception as exc:
            logger.error("Unexpected error cleaning record %d: %s", i, exc)
            # Still include a stub so the validator can flag it
            cleaned.append({
                "year": None,
                "round": "",
                "course": "",
                "college_code": "",
                "college_name": "",
                "college_type": "",
                "ranks": {},
                "_clean_error": str(exc),
            })
    return cleaned
