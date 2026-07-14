"""
Processing API — triggers OCR pipeline and streams progress via SSE.
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.core.ocr_pipeline import OcrPipeline, cancelled_jobs
from app.utils.file_utils import cleanup_job_dirs
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["process"])

_pipeline = OcrPipeline()


class ProcessStatus(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/process/{job_id}", response_model=ProcessStatus)
async def start_processing(job_id: str) -> ProcessStatus:
    """
    Validate that the job upload directory exists and is ready.
    The actual processing happens via the SSE stream endpoint.
    """
    settings = get_settings()
    upload_dir = os.path.join(settings.UPLOAD_DIR, job_id)

    if not os.path.exists(upload_dir) or not os.listdir(upload_dir):
        raise HTTPException(
            status_code=404,
            detail=f"No uploaded files found for job {job_id!r}.",
        )

    return ProcessStatus(
        job_id=job_id,
        status="ready",
        message="Upload confirmed. Connect to the SSE stream to begin processing.",
    )


@router.get("/process/{job_id}/stream")
async def process_stream(job_id: str) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time OCR progress.
    Runs the full pipeline and yields progress events until complete.

    Connect with:
        const es = new EventSource('/api/process/{job_id}/stream');
        es.onmessage = e => { const d = JSON.parse(e.data); ... }
    """
    settings = get_settings()
    upload_dir = os.path.join(settings.UPLOAD_DIR, job_id)

    if not os.path.exists(upload_dir):
        raise HTTPException(
            status_code=404,
            detail=f"No upload directory for job {job_id!r}.",
        )

    async def event_generator():
        try:
            async for event in _pipeline.process_job(job_id, upload_dir):
                yield event.to_sse()
        except Exception as exc:
            logger.error("Pipeline error for job %s: %s", job_id, exc, exc_info=True)
            import json
            error_payload = json.dumps({
                "type": "error",
                "message": f"Pipeline error: {str(exc)}",
                "processed": 0,
                "total": 0,
            })
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/process/{job_id}/status", response_model=ProcessStatus)
async def get_processing_status(job_id: str) -> ProcessStatus:
    """
    Check if results exist for a job (i.e., processing has completed).
    """
    settings = get_settings()
    result_file = os.path.join(settings.RESULTS_DIR, f"{job_id}.json")

    if os.path.exists(result_file):
        return ProcessStatus(
            job_id=job_id,
            status="completed",
            message="Processing complete. Proceed to preview.",
        )

    upload_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    if os.path.exists(upload_dir):
        return ProcessStatus(
            job_id=job_id,
            status="uploaded",
            message="Files uploaded. Processing not yet started.",
        )

    return ProcessStatus(
        job_id=job_id,
        status="unknown",
        message="No data found for this job.",
    )


@router.delete("/process/{job_id}", status_code=204)
async def cancel_processing(job_id: str):
    """Cancel an ongoing processing job and clean up files."""
    cancelled_jobs.add(job_id)
    settings = get_settings()
    
    # Try to clean up files. The pipeline might still be holding a lock on the 
    # current file being processed, but it will exit soon after.
    try:
        cleanup_job_dirs(
            job_id,
            images_dir=settings.IMAGES_DIR,
            results_dir=settings.RESULTS_DIR,
            uploads_dir=settings.UPLOAD_DIR,
        )
        logger.info("Cleaned up files for cancelled job %s", job_id)
    except Exception as exc:
        logger.warning("Failed to clean up files for cancelled job %s: %s", job_id, exc)
