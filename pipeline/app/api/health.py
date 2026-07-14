"""
Health check endpoint.
Verifies: database, Ollama, required model, and disk directories.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings, runtime_settings
from app.db.database import check_db_connection, check_table_exists
from app.utils.logging_config import get_logger
import httpx
import os

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


class HealthStatus(BaseModel):
    status: str                         # "healthy" | "degraded" | "unhealthy"
    database: bool
    required_table_exists: bool
    ollama_running: bool
    ollama_model_loaded: bool
    ollama_model: str
    data_dirs_writable: bool
    ocr_provider: str
    gemini_key_configured: bool
    details: dict



@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Comprehensive system health check.
    Returns status of all dependencies required for processing.
    """
    settings = get_settings()
    details: dict = {}

    # 1. Database
    db_ok = await check_db_connection()
    table_ok = await check_table_exists("keam_cutoff_ranks") if db_ok else False

    if not db_ok:
        details["database_error"] = "Cannot connect to PostgreSQL."
    if db_ok and not table_ok:
        details["table_error"] = "keam_cutoff_ranks table not found."

    # 2. Ollama connectivity
    ollama_running = False
    model_loaded = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                ollama_running = True
                data = resp.json()
                loaded_models = [m["name"] for m in data.get("models", [])]
                # minicpm-v:8b may appear as "minicpm-v:8b" or "minicpm-v"
                model_loaded = any(
                    settings.OLLAMA_MODEL in m or m.startswith(settings.OLLAMA_MODEL.split(":")[0])
                    for m in loaded_models
                )
                details["ollama_models"] = loaded_models
    except Exception as exc:
        details["ollama_error"] = str(exc)
        logger.warning("Ollama health check failed: %s", exc)

    # 3. Data directories
    dirs_ok = True
    for dir_path in [settings.UPLOAD_DIR, settings.IMAGES_DIR, settings.RESULTS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
        if not os.access(dir_path, os.W_OK):
            dirs_ok = False
            details["dir_error"] = f"Not writable: {dir_path}"

    # Determine overall status
    ocr_provider = runtime_settings.ocr_provider
    gemini_key_configured = bool(settings.GEMINI_API_KEY)

    if ocr_provider == "gemini":
        critical_ok = db_ok and table_ok and gemini_key_configured
    else:
        critical_ok = db_ok and table_ok and ollama_running and model_loaded

    all_ok = critical_ok and dirs_ok

    if all_ok:
        status = "healthy"
    elif db_ok and (gemini_key_configured if ocr_provider == "gemini" else ollama_running):
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthStatus(
        status=status,
        database=db_ok,
        required_table_exists=table_ok,
        ollama_running=ollama_running,
        ollama_model_loaded=model_loaded,
        ollama_model=settings.OLLAMA_MODEL,
        data_dirs_writable=dirs_ok,
        ocr_provider=ocr_provider,
        gemini_key_configured=gemini_key_configured,
        details=details,
    )

