"""
FastAPI application factory.
Configures lifespan, mounts static/templates, registers API routes, and page routes.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.router import api_router
from app.config import get_settings
from app.db.database import (
    check_db_connection,
    check_table_exists,
    create_pipeline_tables,
    dispose_db,
    init_db,
)
from app.utils.file_utils import ensure_dirs
from app.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)

# Resolve template and static directories relative to this file
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "templates")
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    setup_logging(debug=settings.APP_DEBUG)

    # Initialize runtime settings from configuration
    from app.config import runtime_settings
    runtime_settings.ocr_provider = settings.OCR_PROVIDER


    logger.info("=" * 60)
    logger.info("KEAM OCR Pipeline starting up...")
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # Ensure data directories exist
    ensure_dirs(settings.UPLOAD_DIR, settings.IMAGES_DIR, settings.RESULTS_DIR)

    # Startup health checks
    db_ok = await check_db_connection()
    if not db_ok:
        logger.critical(
            "Cannot connect to database! Check DB_HOST/DB_USER/DB_PASSWORD in .env"
        )
    else:
        table_ok = await check_table_exists("keam_cutoff_ranks")
        if not table_ok:
            logger.critical(
                "keam_cutoff_ranks table NOT FOUND. "
                "The Go backend must have initialized this table first."
            )
        else:
            logger.info("keam_cutoff_ranks table: OK")
        # Create pipeline-specific tables
        try:
            await create_pipeline_tables()
        except Exception as exc:
            logger.error("Failed to create pipeline tables: %s", exc)

    logger.info("Server ready at http://%s:%s", settings.APP_HOST, settings.APP_PORT)
    logger.info("=" * 60)

    yield  # Application runs here

    logger.info("Shutting down KEAM OCR Pipeline...")
    await dispose_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="KEAM OCR Pipeline",
        description="Offline OCR-based document processing for KEAM cutoff ranks",
        version="1.0.0",
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Mount static files
    if os.path.exists(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Register all API routes
    app.include_router(api_router)

    # ── Page routes (Jinja2-rendered HTML) ───────────────────────────────────

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/processing/{job_id}", response_class=HTMLResponse, include_in_schema=False)
    async def processing_page(request: Request, job_id: str) -> HTMLResponse:
        return templates.TemplateResponse(
            "processing.html", {"request": request, "job_id": job_id}
        )

    @app.get("/preview/{job_id}", response_class=HTMLResponse, include_in_schema=False)
    async def preview_page(request: Request, job_id: str) -> HTMLResponse:
        return templates.TemplateResponse(
            "preview.html", {"request": request, "job_id": job_id}
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc) -> HTMLResponse:
        return templates.TemplateResponse(
            "base.html",
            {"request": request, "error": "Page not found (404)"},
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc) -> HTMLResponse:
        logger.error("Unhandled server error: %s", exc, exc_info=True)
        return templates.TemplateResponse(
            "base.html",
            {"request": request, "error": f"Server error: {exc}"},
            status_code=500,
        )

    return app


app = create_app()
