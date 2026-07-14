"""
Application configuration using Pydantic Settings.
All values are loaded from .env file or environment variables.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings:
    def __init__(self):
        self.ocr_provider: str = "ollama"


runtime_settings = RuntimeSettings()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Server
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False

    # Database
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "postgres"
    DB_SSLMODE: str = "require"

    # OCR Engine Selection
    OCR_PROVIDER: str = "ollama"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "minicpm-v:8b"
    OLLAMA_TIMEOUT: int = 120

    # Gemini API
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Storage directories (relative to pipeline/ root)
    UPLOAD_DIR: str = "data/uploads"
    IMAGES_DIR: str = "data/images"
    RESULTS_DIR: str = "data/results"

    # OCR settings
    OCR_MAX_IMAGE_WIDTH: int = 1920
    OCR_DPI: int = 200
    OCR_TEMPERATURE: float = 0.1
    OCR_MAX_RETRIES: int = 3
    OCR_INTER_CALL_DELAY_MS: int = 500

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy URL for Supabase (psycopg2)."""
        from urllib.parse import quote_plus
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode={self.DB_SSLMODE}"
        )

    @property
    def async_database_url(self) -> str:
        """Async SQLAlchemy URL for Supabase (asyncpg)."""
        from urllib.parse import quote_plus
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?ssl=require"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for Settings. Use via dependency injection."""
    return Settings()
