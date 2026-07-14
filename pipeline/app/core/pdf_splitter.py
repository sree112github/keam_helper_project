"""
PDF to image conversion using PyMuPDF (fitz).
No external binaries required — pure Python install.
"""
import os
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PageImage:
    page_number: int      # 1-indexed
    image_path: str
    width: int
    height: int


class PdfSplitter:
    """
    Converts PDF pages to PNG images using PyMuPDF.
    Renders at configurable DPI for OCR quality.
    """

    def __init__(self, dpi: int = 200) -> None:
        self.dpi = dpi
        self._scale = dpi / 72.0  # PyMuPDF default is 72 DPI

    def split(self, pdf_path: str, output_dir: str) -> list[PageImage]:
        """
        Convert all pages of a PDF to PNG images.

        Args:
            pdf_path: Path to the source PDF.
            output_dir: Directory to save page images.

        Returns:
            List of PageImage dataclasses, one per page.

        Raises:
            ValueError: If the file is not a valid PDF.
            RuntimeError: If a page cannot be rendered.
        """
        os.makedirs(output_dir, exist_ok=True)

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            raise ValueError(f"Cannot open PDF '{pdf_path}': {exc}") from exc

        pages: list[PageImage] = []
        total = len(doc)
        logger.info("Splitting PDF '%s': %d pages at %d DPI", pdf_path, total, self.dpi)

        for page_num in range(total):
            page = doc[page_num]
            try:
                mat = fitz.Matrix(self._scale, self._scale)
                pixmap = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                filename = f"page_{page_num + 1:03d}.png"
                out_path = os.path.join(output_dir, filename)
                pixmap.save(out_path)

                pages.append(
                    PageImage(
                        page_number=page_num + 1,
                        image_path=out_path,
                        width=pixmap.width,
                        height=pixmap.height,
                    )
                )
                logger.debug(
                    "Rendered page %d/%d → %s (%dx%d px)",
                    page_num + 1, total, filename, pixmap.width, pixmap.height,
                )
            except Exception as exc:
                logger.error(
                    "Failed to render page %d of '%s': %s",
                    page_num + 1, pdf_path, exc,
                )
                # Continue with remaining pages instead of aborting
                pages.append(
                    PageImage(
                        page_number=page_num + 1,
                        image_path="",  # empty signals render failure
                        width=0,
                        height=0,
                    )
                )

        doc.close()
        successful = [p for p in pages if p.image_path]
        logger.info(
            "PDF split complete: %d/%d pages rendered successfully",
            len(successful), total,
        )
        return pages

    def get_page_count(self, pdf_path: str) -> int:
        """
        Return the number of pages in a PDF without rendering.

        Raises:
            ValueError: If the file is not a valid PDF.
        """
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as exc:
            raise ValueError(f"Cannot open PDF '{pdf_path}': {exc}") from exc
