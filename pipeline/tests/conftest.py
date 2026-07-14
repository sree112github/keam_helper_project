"""
Pytest fixtures for the KEAM OCR Pipeline test suite.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Set environment variables BEFORE importing the app
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "testpassword")
os.environ.setdefault("DB_NAME", "test_keam")
os.environ.setdefault("DB_SSLMODE", "disable")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "minicpm-v:8b")
os.environ.setdefault("UPLOAD_DIR", "data/test_uploads")
os.environ.setdefault("IMAGES_DIR", "data/test_images")
os.environ.setdefault("RESULTS_DIR", "data/test_results")


@pytest.fixture(scope="session")
def sample_records():
    """A set of sample records for testing cleaner and validator."""
    return [
        {
            "year": 2026,
            "round": "First Phase Allotment",
            "course": "Applied Electronics & Instrumentation",
            "college_code": "KKE",
            "college_name": "Government Engineering College, Kozhikkode",
            "college_type": "G",
            "ranks": {"SM": 8302, "EZ": 13955, "MU": None, "FW": 7355},
        },
        {
            "year": 2026,
            "round": "First Phase Allotment",
            "course": "Civil Engineering",
            "college_code": "TVE",
            "college_name": "College of Engineering, Thiruvananthapuram",
            "college_type": "G",
            "ranks": {"SM": 5953, "EZ": "7,724", "MU": "-", "LA": 9716},
        },
        {
            # Invalid record — missing college_code
            "year": 2026,
            "round": "First Phase Allotment",
            "course": "Computer Science",
            "college_code": "",
            "college_name": "Some College",
            "college_type": "S",
            "ranks": {"SM": 100},
        },
    ]
