"""
Upload API endpoint.
Accepts PDF and image files, validates them, saves to disk, creates a DB job.
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.pdf_splitter import PdfSplitter
from app.dependencies import db_session, settings_dep
from app.db import repository
from app.db.models import OcrProcessingJob
from app.schemas.upload import FileInfo, UploadResponse
from app.utils.file_utils import (
    MAX_FILE_SIZE,
    MAX_TOTAL_SIZE,
    detect_file_type,
    ensure_dirs,
    save_upload,
)
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_TYPES = {"pdf", "png", "jpeg"}


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile] = File(..., description="PDF or image files to process"),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(settings_dep),
) -> UploadResponse:
    """
    Upload one or more PDF/image files for OCR processing.

    - Validates file types via magic bytes (not just extension).
    - Enforces 50 MB per file and 200 MB total limits.
    - Creates a processing job in the database.
    - Returns a job_id for subsequent processing requests.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    ensure_dirs(settings.UPLOAD_DIR, settings.IMAGES_DIR, settings.RESULTS_DIR)

    job_id = str(uuid.uuid4())
    upload_job_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    os.makedirs(upload_job_dir, exist_ok=True)

    file_infos: list[FileInfo] = []
    file_names: list[str] = []
    total_size = 0
    splitter = PdfSplitter(dpi=settings.OCR_DPI)

    for upload in files:
        # Read file data
        data = await upload.read()
        file_size = len(data)

        # Size checks
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload.filename}' exceeds 50 MB limit ({file_size / 1e6:.1f} MB).",
            )
        total_size += file_size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Total upload size exceeds 200 MB limit.",
            )

        # Type validation via magic bytes
        detected = detect_file_type(data)
        if detected not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"File '{upload.filename}' is not a supported type. "
                    f"Detected: {detected!r}. Allowed: PDF, PNG, JPEG."
                ),
            )

        file_type = "pdf" if detected == "pdf" else "image"
        original_name = upload.filename or f"file_{uuid.uuid4().hex[:8]}"
        save_name = f"{uuid.uuid4().hex}_{original_name}"
        save_path = os.path.join(upload_job_dir, save_name)
        save_upload(data, save_path)
        file_names.append(save_name)

        # For PDFs, count pages using PyMuPDF
        page_count: int | None = None
        if file_type == "pdf":
            try:
                page_count = splitter.get_page_count(save_path)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Could not read PDF '{original_name}': {exc}",
                ) from exc

        file_infos.append(
            FileInfo(
                filename=original_name,
                file_type=file_type,
                size_bytes=file_size,
                page_count=page_count,
            )
        )
        logger.info(
            "Uploaded '%s' (type=%s, size=%d, pages=%s)",
            original_name, file_type, file_size, page_count,
        )

    # Create job record in database using the pre-computed job_id
    # (so upload dir path matches the DB record)
    job = OcrProcessingJob(
        id=job_id,
        status="uploaded",
        file_names=file_names,
    )
    session.add(job)
    await session.flush()

    total_pages = sum(
        fi.page_count or 1 for fi in file_infos
    )

    logger.info("Created upload job %s: %d files, ~%d pages", job_id, len(files), total_pages)

    return UploadResponse(
        job_id=job_id,
        files=file_infos,
        total_pages=total_pages,
    )
