"""Composable HTML -> PDF -> page images -> optional Groq review pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .groq_review import DEFAULT_PROMPT, review_images_with_groq
from .pdf_to_images import convert_pdf_to_images
from .renderers import render_html

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, str]], None]


@dataclass(frozen=True)
class PipelineResult:
    pdf_path: Path
    image_paths: list[Path]
    reviews: list[str]


def run_pipeline(
    html_path: Path,
    pdf_path: Path,
    images_dir: Path,
    renderer: str = "puppeteer",
    dpi: int = 150,
    wait_for_selector: str | None = None,
    groq_prompt: str = DEFAULT_PROMPT,
    groq_model: str | None = None,
    groq_api_key: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineResult:
    """Run PDF rendering, page rasterization, then optional Groq review."""
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Step 1/3: rendering %s with %s", html_path.name, renderer)
    if progress_callback:
        progress_callback({"step": "render", "status": "started", "message": f"Rendering HTML with {renderer}…"})
    render_html(html_path, pdf_path, renderer, wait_for_selector)
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"{renderer} completed without producing a PDF.")
    if progress_callback:
        progress_callback({"step": "render", "status": "complete", "message": "PDF rendering complete."})

    logger.info("Step 2/3: rasterizing PDF pages at %s DPI", dpi)
    if progress_callback:
        progress_callback({"step": "images", "status": "started", "message": f"Converting PDF pages to images at {dpi} DPI…"})
    image_paths = convert_pdf_to_images(pdf_path, images_dir, dpi)
    logger.info("Created %s page image(s)", len(image_paths))
    if progress_callback:
        progress_callback({"step": "images", "status": "complete", "message": f"Created {len(image_paths)} page image(s)."})

    logger.info("Step 3/3: optional Groq page review")
    reviews = review_images_with_groq(
        image_paths,
        prompt=groq_prompt,
        model=groq_model,
        api_key=groq_api_key,
        progress_callback=progress_callback,
    )
    return PipelineResult(pdf_path=pdf_path, image_paths=image_paths, reviews=reviews)
