"""
Ollama REST API client.
Handles communication with the local Ollama server, retry logic,
and JSON response parsing with error recovery.
"""
import asyncio
import json
import re
import time
from typing import Any

import httpx
import json_repair

from app.config import get_settings, runtime_settings
from app.core.prompt_templates import EXTRACTION_PROMPT, build_repair_prompt
from app.schemas.ocr import OCRResult
from app.utils.image_utils import preprocess_and_encode
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class OllamaError(Exception):
    """Raised when Ollama communication fails after all retries."""
    pass


class GeminiError(Exception):
    """Raised when Gemini communication fails after all retries."""
    pass



def _extract_json_from_text(text: str) -> str:
    """
    Attempt to extract a JSON array from raw model output.
    The model sometimes wraps output in markdown code fences.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.strip("`").strip()

    # Find first [ to last ] to isolate the array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def _parse_json_response(raw: str) -> list[dict[str, Any]]:
    """
    Parse the raw Ollama text output as a JSON array using json-repair.

    Raises:
        ValueError: If parsing fails after cleanup.
    """
    cleaned = _extract_json_from_text(raw)
    
    # If the model output is completely empty (e.g., no table found)
    if not cleaned:
        return []
        
    try:
        data = json_repair.loads(cleaned)
    except Exception as exc:
        raise ValueError(f"json_repair failed: {exc}")

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array after repair")

    return data


class OcrEngine:
    """
    OCR engine that uses Ollama's vision API.
    Each call processes one image and returns structured records.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def process_image(self, image_path: str) -> OCRResult:
        """
        Process a single image through Ollama minicpm-v:8b.

        Strategy:
        - Attempt 1: Primary extraction prompt
        - Attempt 2: Repair prompt with error context
        - Attempt 3: Second repair attempt
        - On all failures: return OCRResult with error, empty records

        Args:
            image_path: Absolute or relative path to the preprocessed image.

        Returns:
            OCRResult with extracted records (possibly empty on failure).
        """
        start_time = time.monotonic()
        settings = self._settings

        # Preprocess and encode image
        try:
            b64_image = preprocess_and_encode(
                image_path,
                max_width=settings.OCR_MAX_IMAGE_WIDTH,
            )
        except Exception as exc:
            logger.error("Image preprocessing failed for %s: %s", image_path, exc)
            return OCRResult(
                image_path=image_path,
                records=[],
                attempt=0,
                processing_time_ms=0,
                error=f"Image preprocessing failed: {exc}",
            )

        last_error: str = ""
        raw_response: str = ""
        prompt = EXTRACTION_PROMPT

        provider = runtime_settings.ocr_provider
        for attempt in range(1, settings.OCR_MAX_RETRIES + 1):
            logger.info(
                "OCR attempt %d/%d for image: %s using provider: %s",
                attempt, settings.OCR_MAX_RETRIES, image_path, provider,
            )

            try:
                if provider == "gemini":
                    raw_response = await self._call_gemini(prompt, b64_image)
                else:
                    raw_response = await self._call_ollama(prompt, b64_image)

                records = _parse_json_response(raw_response)

                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "OCR success on attempt %d: %d records in %dms",
                    attempt, len(records), elapsed_ms,
                )

                # Inter-call delay to avoid GPU OOM
                if settings.OCR_INTER_CALL_DELAY_MS > 0:
                    await asyncio.sleep(settings.OCR_INTER_CALL_DELAY_MS / 1000)

                return OCRResult(
                    image_path=image_path,
                    records=records,
                    attempt=attempt,
                    processing_time_ms=elapsed_ms,
                )

            except ValueError as exc:
                last_error = str(exc)
                logger.warning(
                    "JSON parse failed on attempt %d for %s: %s",
                    attempt, image_path, exc,
                )
                # Prepare repair prompt for the next attempt
                prompt = build_repair_prompt(last_error, raw_response)
                await asyncio.sleep(0.5)

            except (OllamaError, GeminiError) as exc:
                last_error = str(exc)
                logger.error(
                    "%s call failed on attempt %d for %s: %s",
                    provider.capitalize(), attempt, image_path, exc,
                )
                # API error (like 503) -> retry with the SAME prompt, use exponential backoff
                await asyncio.sleep(2.0 ** attempt)

        # All retries exhausted
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "All %d OCR attempts failed for %s. Last error: %s",
            settings.OCR_MAX_RETRIES, image_path, last_error,
        )
        return OCRResult(
            image_path=image_path,
            records=[],
            attempt=settings.OCR_MAX_RETRIES,
            processing_time_ms=elapsed_ms,
            error=f"All retries failed. Last error: {last_error}. "
                  f"Raw response preview: {raw_response[:200]}",
        )

    async def _call_ollama(self, prompt: str, b64_image: str) -> str:
        """
        Make a single request to the Ollama generate API.

        Returns the response text string.
        Raises OllamaError on connectivity or HTTP errors.
        """
        settings = self._settings
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {
                "temperature": settings.OCR_TEMPERATURE,
                "num_predict": 4096,
                "num_ctx": 4096,
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=settings.OLLAMA_TIMEOUT
            ) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")

        except httpx.TimeoutException as exc:
            raise OllamaError(f"Ollama request timed out after {settings.OLLAMA_TIMEOUT}s") from exc
        except httpx.ConnectError as exc:
            raise OllamaError(
                f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. "
                "Is Ollama running?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama HTTP error: {exc.response.status_code} — {exc.response.text[:200]}"
            ) from exc
        except Exception as exc:
            raise OllamaError(f"Unexpected Ollama error: {exc}") from exc

    async def _call_gemini(self, prompt: str, b64_image: str) -> str:
        """
        Make a single request to the Google Gemini API.

        Returns the response text string.
        Raises GeminiError on connectivity or HTTP errors.
        """
        settings = self._settings
        if not settings.GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY is not set. Please add it to your .env file.")

        model = settings.GEMINI_MODEL or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": settings.OCR_TEMPERATURE,
                "responseMimeType": "application/json"
            }
        }

        try:
            async with httpx.AsyncClient(
                timeout=settings.OLLAMA_TIMEOUT
            ) as client:
                resp = await client.post(
                    url,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                
                candidates = data.get("candidates", [])
                if not candidates:
                    raise GeminiError("Gemini returned empty candidates. No content generated.")
                
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    raise GeminiError("Gemini content parts are empty.")
                
                return parts[0].get("text", "")

        except httpx.TimeoutException as exc:
            raise GeminiError(f"Gemini request timed out after {settings.OLLAMA_TIMEOUT}s") from exc
        except httpx.ConnectError as exc:
            raise GeminiError("Cannot connect to Gemini API. Check your internet connection.") from exc
        except httpx.HTTPStatusError as exc:
            raise GeminiError(
                f"Gemini HTTP error: {exc.response.status_code} — {exc.response.text[:200]}"
            ) from exc
        except Exception as exc:
            raise GeminiError(f"Unexpected Gemini error: {exc}") from exc

