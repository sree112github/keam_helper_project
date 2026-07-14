"""
Unit tests for the validator module.
No external dependencies required.
"""
import pytest
from app.core.validator import (
    check_batch_duplicates,
    validate_record,
    validate_records,
)


class TestValidateRecord:
    def _valid_record(self, **overrides):
        base = {
            "year": 2026,
            "round": "First Phase Allotment",
            "course": "Computer Science & Engineering",
            "college_code": "KKE",
            "college_name": "Government Engineering College, Kozhikkode",
            "college_type": "G",
            "ranks": {"SM": 8302, "EZ": 13955},
        }
        base.update(overrides)
        return base

    def test_valid_record_no_errors(self):
        errors = validate_record(self._valid_record())
        assert errors == []

    def test_missing_year(self):
        errors = validate_record(self._valid_record(year=None))
        assert any("year" in e.lower() for e in errors)

    def test_year_out_of_range(self):
        errors = validate_record(self._valid_record(year=1999))
        assert any("range" in e.lower() for e in errors)

    def test_missing_round(self):
        errors = validate_record(self._valid_record(round=""))
        assert any("round" in e.lower() for e in errors)

    def test_missing_course(self):
        errors = validate_record(self._valid_record(course=""))
        assert any("course" in e.lower() for e in errors)

    def test_missing_college_code(self):
        errors = validate_record(self._valid_record(college_code=""))
        assert any("college_code" in e.lower() for e in errors)

    def test_invalid_college_code_format(self):
        errors = validate_record(self._valid_record(college_code="123"))
        assert any("college_code" in e.lower() for e in errors)

    def test_missing_college_name(self):
        errors = validate_record(self._valid_record(college_name=""))
        assert any("college_name" in e.lower() for e in errors)

    def test_invalid_college_type(self):
        errors = validate_record(self._valid_record(college_type="X"))
        assert any("college_type" in e.lower() for e in errors)

    def test_empty_ranks_flagged(self):
        errors = validate_record(self._valid_record(ranks={}))
        assert any("empty" in e.lower() for e in errors)

    def test_null_rank_values_valid(self):
        """null values in ranks are valid."""
        errors = validate_record(self._valid_record(ranks={"SM": 8302, "EZ": None}))
        assert errors == []

    def test_string_rank_flagged(self):
        errors = validate_record(self._valid_record(ranks={"SM": "not-an-int"}))
        assert any("SM" in e for e in errors)


class TestValidateRecords:
    def test_annotates_is_valid(self):
        records = [
            {"year": 2026, "round": "R", "course": "C", "college_code": "ABC",
             "college_name": "X", "college_type": "G", "ranks": {"SM": 100}},
            {"year": None, "round": "", "course": "", "college_code": "",
             "college_name": "", "college_type": "", "ranks": {}},
        ]
        result = validate_records(records)
        assert result[0]["is_valid"] is True
        assert result[1]["is_valid"] is False
        assert len(result[1]["validation_errors"]) > 0


class TestBatchDuplicates:
    def test_detects_duplicate(self):
        records = [
            {"year": 2026, "round": "R", "course": "C", "college_code": "ABC",
             "is_valid": True, "validation_errors": []},
            {"year": 2026, "round": "R", "course": "C", "college_code": "ABC",
             "is_valid": True, "validation_errors": []},
        ]
        result = check_batch_duplicates(records)
        # Second record should be flagged
        assert any("Duplicate" in e for e in result[1]["validation_errors"])
        assert result[1]["is_valid"] is False

    def test_no_false_positives(self):
        records = [
            {"year": 2026, "round": "R", "course": "C", "college_code": "ABC",
             "is_valid": True, "validation_errors": []},
            {"year": 2026, "round": "R", "course": "C", "college_code": "TVE",
             "is_valid": True, "validation_errors": []},
        ]
        result = check_batch_duplicates(records)
        assert result[0]["is_valid"] is True
        assert result[1]["is_valid"] is True
