"""
Main OCR pipeline orchestrator.
Coordinates: PDF split → image preprocessing → OCR → clean → validate → save.
"""
import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from app.config import get_settings
from app.core.data_cleaner import clean_records
from app.core.ocr_engine import OcrEngine
from app.core.pdf_splitter import PdfSplitter
from app.core.validator import check_batch_duplicates, validate_records
from app.utils.file_utils import results_path, safe_job_dir
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Global set to track cancelled job IDs
cancelled_jobs: set[str] = set()


class ProgressEvent:
    """Represents a progress update to stream to the frontend."""

    def __init__(
        self,
        event_type: str,         # "progress" | "complete" | "error"
        processed: int,
        total: int,
        message: str = "",
        data: dict | None = None,
    ) -> None:
        self.event_type = event_type
        self.processed = processed
        self.total = total
        self.message = message
        self.data = data or {}

    def to_sse(self) -> str:
        """Format as a Server-Sent Event string."""
        payload = json.dumps({
            "type": self.event_type,
            "processed": self.processed,
            "total": self.total,
            "message": self.message,
            **self.data,
        })
        return f"data: {payload}\n\n"


class OcrPipeline:
    """
    Full pipeline from uploaded files to validated records.
    Saves results to JSON for persistence across requests.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._engine = OcrEngine()
        self._splitter = PdfSplitter(dpi=self._settings.OCR_DPI)

    async def process_job(
        self,
        job_id: str,
        upload_job_dir: str,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """
        Process all uploaded files for a job.
        Yields ProgressEvent instances for SSE streaming.

        Args:
            job_id: The processing job UUID.
            upload_job_dir: Directory containing uploaded files.

        Yields:
            ProgressEvent for each processed image.
        """
        settings = self._settings

        # Collect all files
        files = sorted(os.listdir(upload_job_dir))
        if not files:
            yield ProgressEvent("error", 0, 0, "No files found in upload directory.")
            return

        # Build list of images to process
        images_dir = safe_job_dir(settings.IMAGES_DIR, job_id)
        image_paths: list[tuple[str, str]] = []  # (image_path, source_label)

        for filename in files:
            file_path = os.path.join(upload_job_dir, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext == ".pdf":
                logger.info("Splitting PDF: %s", filename)
                try:
                    pages = self._splitter.split(file_path, images_dir)
                    for page in pages:
                        if page.image_path:
                            image_paths.append((page.image_path, f"{filename}:p{page.page_number}"))
                        else:
                            image_paths.append(("", f"{filename}:p{page.page_number}"))
                except ValueError as exc:
                    yield ProgressEvent(
                        "error", 0, 0, f"PDF error in {filename}: {exc}"
                    )
                    return

            elif ext in {".png", ".jpg", ".jpeg"}:
                image_paths.append((file_path, filename))

        total = len(image_paths)
        if total == 0:
            yield ProgressEvent("error", 0, 0, "No processable images found.")
            return

        logger.info("Processing job %s: %d images total", job_id, total)

        all_records: list[dict[str, Any]] = []
        processed = 0

        for image_path, source_label in image_paths:
            if job_id in cancelled_jobs:
                logger.info("Job %s cancelled during processing.", job_id)
                yield ProgressEvent("error", processed, total, "Processing cancelled by user.")
                cancelled_jobs.discard(job_id)
                return

            processed += 1

            if not image_path:
                # Page that failed to render
                yield ProgressEvent(
                    "progress", processed, total,
                    f"Skipped (render failed): {source_label}",
                )
                continue

            yield ProgressEvent(
                "progress", processed, total,
                f"Processing: {source_label}",
            )

            # Run OCR
            ocr_result = await self._engine.process_image(image_path)

            if ocr_result.error and not ocr_result.records:
                yield ProgressEvent(
                    "progress", processed, total,
                    f"OCR failed for {source_label}: {ocr_result.error[:100]}",
                    data={"ocr_error": True, "source": source_label},
                )
                continue

            # Clean and validate
            if ocr_result.records:
                cleaned = clean_records(ocr_result.records)
                for rec in cleaned:
                    rec["source_image"] = source_label

                validated = validate_records(cleaned)
                all_records.extend(validated)

                logger.info(
                    "Image %s: %d records extracted, %d valid",
                    source_label,
                    len(validated),
                    sum(1 for r in validated if r.get("is_valid")),
                )

        # Final deduplication pass
        all_records = check_batch_duplicates(all_records)

        # Add sequential index
        for i, rec in enumerate(all_records):
            rec["index"] = i

        # Save results to disk
        out_path = results_path(settings.RESULTS_DIR, job_id)
        os.makedirs(settings.RESULTS_DIR, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)

        valid_count = sum(1 for r in all_records if r.get("is_valid"))
        logger.info(
            "Job %s complete: %d total records, %d valid. Results: %s",
            job_id, len(all_records), valid_count, out_path,
        )

        yield ProgressEvent(
            "complete",
            processed,
            total,
            f"Processing complete: {len(all_records)} records extracted, {valid_count} valid.",
            data={
                "total_records": len(all_records),
                "valid_records": valid_count,
                "job_id": job_id,
            },
        )

    def load_results(self, job_id: str) -> list[dict[str, Any]]:
        """
        Load previously saved results from disk.

        Raises:
            FileNotFoundError: If results don't exist for this job.
        """
        settings = self._settings
        path = results_path(settings.RESULTS_DIR, job_id)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No results found for job {job_id!r}. Has it been processed?"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_results(self, job_id: str, records: list[dict[str, Any]]) -> None:
        """Save (updated) results back to disk."""
        settings = self._settings
        os.makedirs(settings.RESULTS_DIR, exist_ok=True)
        path = results_path(settings.RESULTS_DIR, job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        logger.debug("Saved %d records to %s", len(records), path)
