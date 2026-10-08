"""PDF page rasterization helpers."""

from pathlib import Path

import pymupdf


def convert_pdf_to_images(pdf_path: Path, images_dir: Path, dpi: int = 150) -> list[Path]:
    """Rasterize every PDF page to a sequentially named PNG image."""
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")

    images_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    with pymupdf.open(pdf_path) as document:
        if document.page_count == 0:
            raise RuntimeError("The PDF contains no pages.")
        for page_number, page in enumerate(document, start=1):
            image_path = images_dir / f"page_{page_number}.png"
            page.get_pixmap(dpi=dpi, alpha=False).save(image_path)
            image_paths.append(image_path)
    return image_paths
