"""Optional page-by-page visual review using Groq's vision API."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Callable

from groq import Groq

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, str]], None]

DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_PROMPT = (
    "You are checking a rendered PDF page for visual layout issues. Look for overlapping elements, "
    "clipped or overflowing text, broken tables, missing backgrounds or colors, and misaligned grids. "
    "Reply OK if the page looks correct; otherwise describe the issue and where it appears."
)


def review_images_with_groq(
    image_paths: list[Path],
    prompt: str = DEFAULT_PROMPT,
    model: str | None = None,
    api_key: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[str]:
    """Review each page image; return one response (or error message) per image.

    If no API key is provided explicitly or through ``GROQ_API_KEY``, the
    review stage is skipped and an empty list is returned.
    """
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        logger.info("Skipping Groq review because GROQ_API_KEY is not set.")
        if progress_callback:
            progress_callback({"step": "groq", "status": "skipped", "message": "Groq review skipped (GROQ_API_KEY is not set)."})
        return []

    client = Groq(api_key=key)
    selected_model = model or os.environ.get("GROQ_VISION_MODEL") or DEFAULT_MODEL
    reviews: list[str] = []
    for image_path in image_paths:
        if progress_callback:
            progress_callback({"step": "groq", "status": "started", "message": f"Reviewing {image_path.name} with Groq…"})
        try:
            encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
            completion = client.chat.completions.create(
                model=selected_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                        },
                    ],
                }],
                temperature=0.2,
                max_completion_tokens=1024,
                timeout=45.0,
            )
            review = completion.choices[0].message.content or "No review text was returned."
        except Exception as error:  # Keep image packaging available if an individual review fails.
            review = f"Groq review failed: {error}"
            logger.exception("Groq review failed for %s", image_path.name)
        reviews.append(review)
        logger.info("Groq review for %s: %s", image_path.name, review)
        if progress_callback:
            progress_callback({"step": "groq", "status": "complete", "message": f"Groq review complete for {image_path.name}.", "review": review})
    return reviews
