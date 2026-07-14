"""
Unit tests for the data_cleaner module.
These tests run with no external dependencies (no DB, no Ollama).
"""
import pytest
from app.core.data_cleaner import (
    _clean_rank_value,
    _normalize_college_type,
    _parse_other_categories,
    clean_record,
    clean_records,
)


class TestCleanRankValue:
    def test_integer_passthrough(self):
        assert _clean_rank_value(8302) == 8302

    def test_string_with_comma(self):
        assert _clean_rank_value("8,302") == 8302

    def test_dash_to_none(self):
        assert _clean_rank_value("-") is None

    def test_em_dash_to_none(self):
        assert _clean_rank_value("—") is None

    def test_empty_string_to_none(self):
        assert _clean_rank_value("") is None

    def test_none_passthrough(self):
        assert _clean_rank_value(None) is None

    def test_float_converted(self):
        assert _clean_rank_value(8302.0) == 8302

    def test_zero_becomes_none(self):
        assert _clean_rank_value(0) is None

    def test_negative_becomes_none(self):
        assert _clean_rank_value(-5) is None

    def test_string_integer(self):
        assert _clean_rank_value("13955") == 13955

    def test_string_with_spaces(self):
        assert _clean_rank_value("  8 302  ") == 8302

    def test_na_to_none(self):
        assert _clean_rank_value("N/A") is None


class TestParseOtherCategories:
    def test_single_entry(self):
        result = _parse_other_categories("FW:7355")
        assert result == {"FW": 7355}

    def test_multiple_entries(self):
        result = _parse_other_categories("FW:7355 SD:13549")
        assert result.get("FW") == 7355
        assert result.get("SD") == 13549

    def test_comma_in_value(self):
        result = _parse_other_categories("FW:7,355")
        assert result.get("FW") == 7355

    def test_dash_value(self):
        result = _parse_other_categories("FW:-")
        assert result.get("FW") is None

    def test_empty_string(self):
        assert _parse_other_categories("") == {}

    def test_none_input(self):
        assert _parse_other_categories(None) == {}


class TestNormalizeCollegeType:
    def test_g(self):
        assert _normalize_college_type("G") == "G"

    def test_government(self):
        assert _normalize_college_type("Government") == "G"

    def test_s(self):
        assert _normalize_college_type("S") == "S"

    def test_self_financing(self):
        assert _normalize_college_type("Self-Financing") == "S"

    def test_empty(self):
        assert _normalize_college_type("") == ""

    def test_lowercase_g(self):
        assert _normalize_college_type("g") == "G"


class TestCleanRecord:
    def test_clean_record_with_comma_ranks(self):
        raw = {
            "year": 2026,
            "round": "First Phase Allotment",
            "course": "Computer Science",
            "college_code": "kke",
            "college_name": "  Govt College  ",
            "college_type": "government",
            "ranks": {"SM": "8,302", "EZ": "-", "MU": None},
        }
        result = clean_record(raw)
        assert result["ranks"]["SM"] == 8302
        assert result["ranks"]["EZ"] is None
        assert result["ranks"]["MU"] is None
        assert result["college_code"] == "KKE"
        assert result["college_type"] == "G"
        assert result["college_name"] == "Govt College"

    def test_clean_records_never_throws(self):
        """Cleaner must never raise even on garbage input."""
        garbage = [{"totally": "wrong", "data": 123}]
        result = clean_records(garbage)
        assert len(result) == 1  # Returns stub, not exception

    def test_year_from_string(self):
        raw = {
            "year": "KEAM 2026",
            "round": "R", "course": "C", "college_code": "ABC",
            "college_name": "X", "college_type": "G", "ranks": {},
        }
        result = clean_record(raw)
        assert result["year"] == 2026

    def test_other_categories_parsed(self):
        raw = {
            "year": 2026, "round": "R", "course": "C",
            "college_code": "ABC", "college_name": "X", "college_type": "G",
            "ranks": {"SM": 100},
            "other_categories": "FW:7355 SD:13549",
        }
        result = clean_record(raw)
        assert result["ranks"].get("FW") == 7355
        assert result["ranks"].get("SD") == 13549
