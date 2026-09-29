"""Render static HTML with WeasyPrint, rasterize pages, and optionally verify them with Groq.

Usage:
  python weasyprint_pipeline.py sample.html
  python weasyprint_pipeline.py report.html --dpi 200 --prompt "Check the chart labels."
"""

import argparse
import os
from pathlib import Path

from groq import Groq

from html2pdf import GROQ_VISION_MODEL, pdf_to_page_images, verify_page_with_groq

DEFAULT_PROMPT = (
    "You are verifying a rendered PDF page for layout bugs. Check for overlapping elements, "
    "text overflow or clipping, broken tables, missing backgrounds or colors, and misaligned grids. "
    "Reply with 'OK' if it looks correct; otherwise describe the specific issue and where it is."
)


def render_html_with_weasyprint(html_path: Path, pdf_path: Path) -> None:
    """Render HTML and resolve relative resources from the input file's directory."""
    try:
        from weasyprint import HTML
    except ImportError as error:
        raise RuntimeError(
            "WeasyPrint is not installed. Install project dependencies with "
            "python -m pip install -r requirements.txt."
        ) from error

    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))


def run_pipeline(html_path: Path, dpi: int, prompt: str) -> None:
    html_path = html_path.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")

    pdf_path = html_path.with_name(f"{html_path.stem}_weasyprint.pdf")
    image_dir = html_path.with_name(f"{html_path.stem}_weasyprint_pages")

    print(f"[1/3] Rendering {html_path.name} with WeasyPrint ...")
    render_html_with_weasyprint(html_path, pdf_path)
    print(f"       PDF written to {pdf_path}")

    print(f"[2/3] Rasterizing pages at {dpi} DPI ...")
    image_paths = pdf_to_page_images(pdf_path, image_dir, dpi=dpi)
    print(f"       {len(image_paths)} page image(s) written to {image_dir}")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[3/3] Skipping Groq verification because GROQ_API_KEY is not set.")
        return

    print(f"[3/3] Verifying pages with Groq model ({GROQ_VISION_MODEL}) ...")
    client = Groq(api_key=api_key)
    for image_path in image_paths:
        try:
            verdict = verify_page_with_groq(image_path, prompt, client)
            print(f"\n--- {image_path.name} ---\n{verdict}\n")
        except Exception as error:
            print(f"\n--- {image_path.name} ---\n[Error during verification]: {error}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HTML -> WeasyPrint PDF -> page images -> optional Groq verification"
    )
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    try:
        run_pipeline(args.html_file, args.dpi, args.prompt)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()