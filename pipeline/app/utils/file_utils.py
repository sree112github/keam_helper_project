"""
File system utilities.
Handles safe path construction, directory management, and cleanup.
"""
import os
import shutil
import uuid
from pathlib import Path

from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Allowed MIME types by magic bytes
_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "png": b"\x89PNG",
    "jpeg": b"\xff\xd8\xff",
}

MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB per file
MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200 MB per upload


def detect_file_type(data: bytes) -> str | None:
    """
    Detect file type from magic bytes.
    Returns 'pdf', 'png', 'jpeg', or None if unknown.
    """
    for file_type, magic in _MAGIC_BYTES.items():
        if data[: len(magic)] == magic:
            return file_type
    return None


def ensure_dirs(*paths: str) -> None:
    """Create directories if they don't exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)
        logger.debug("Ensured directory: %s", path)


def safe_job_dir(base_dir: str, job_id: str) -> str:
    """Return a job-specific subdirectory path (safe, no traversal)."""
    # job_id must be a valid UUID
    try:
        uuid.UUID(job_id)
    except ValueError as exc:
        raise ValueError(f"Invalid job_id: {job_id!r}") from exc
    path = os.path.join(base_dir, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def save_upload(data: bytes, destination: str) -> None:
    """Write bytes to destination path atomically."""
    tmp = destination + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, destination)
    logger.debug("Saved upload: %s (%d bytes)", destination, len(data))


def cleanup_job_dirs(
    job_id: str,
    images_dir: str,
    results_dir: str,
    uploads_dir: str,
) -> None:
    """Remove all temporary files for a completed job."""
    for base in [images_dir, uploads_dir]:
        job_path = os.path.join(base, job_id)
        if os.path.exists(job_path):
            shutil.rmtree(job_path, ignore_errors=True)
            logger.info("Cleaned up directory: %s", job_path)
            
    # Remove the results JSON file
    res_path = results_path(results_dir, job_id)
    if os.path.exists(res_path):
        try:
            os.remove(res_path)
            logger.info("Cleaned up file: %s", res_path)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", res_path, exc)

    # Also remove top-level upload files with job_id prefix
    if os.path.exists(uploads_dir):
        for fname in os.listdir(uploads_dir):
            if fname.startswith(job_id):
                fpath = os.path.join(uploads_dir, fname)
                try:
                    os.remove(fpath)
                except OSError as exc:
                    logger.warning("Could not remove %s: %s", fpath, exc)


def results_path(results_dir: str, job_id: str) -> str:
    """Return the canonical path for a job's results JSON file."""
    return os.path.join(results_dir, f"{job_id}.json")
