"""
Image preprocessing utilities.
Resize, normalize, and base64-encode images for Ollama.
"""
import base64
import io

from PIL import Image, ImageEnhance, ImageOps

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def preprocess_image(
    image_path: str,
    max_width: int = 1920,
    enhance_contrast: bool = False,
) -> tuple[bytes, tuple[int, int]]:
    """
    Load, resize (if needed), and return PNG bytes + final dimensions.

    Args:
        image_path: Path to the source image.
        max_width: Maximum pixel width. Image is scaled down proportionally.
        enhance_contrast: Apply mild contrast enhancement for OCR.

    Returns:
        (png_bytes, (width, height))
    """
    img = Image.open(image_path).convert("RGB")
    original_size = img.size

    # Resize if wider than max_width
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)
        logger.debug(
            "Resized image %s from %s to %s",
            image_path, original_size, img.size,
        )

    if enhance_contrast:
        img = ImageEnhance.Contrast(img).enhance(1.2)

    # Convert to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    png_bytes = buffer.getvalue()

    logger.debug(
        "Preprocessed %s → %d×%d, %d bytes",
        image_path, img.width, img.height, len(png_bytes),
    )
    return png_bytes, img.size


def image_to_base64(image_bytes: bytes) -> str:
    """Base64-encode raw image bytes for inclusion in Ollama requests."""
    return base64.b64encode(image_bytes).decode("utf-8")


def preprocess_and_encode(
    image_path: str,
    max_width: int = 1920,
    enhance_contrast: bool = False,
) -> str:
    """
    Convenience function: preprocess image and return base64 string.
    Used directly by the OCR engine.
    """
    png_bytes, _ = preprocess_image(image_path, max_width, enhance_contrast)
    return image_to_base64(png_bytes)
