"""Render HTML with Puppeteer, then rasterize and optionally verify each PDF page.

Usage:
  python puppeteer_pipeline.py sample.html
  python puppeteer_pipeline.py sample.html --wait-for-selector "#report-ready"
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from groq import Groq

from html2pdf import GROQ_VISION_MODEL, pdf_to_page_images, verify_page_with_groq

DEFAULT_PROMPT = (
    "You are verifying a rendered PDF page for layout bugs. Check for: overlapping elements, "
    "text overflow/clipping, broken tables, missing backgrounds/colors, or misaligned grids. "
    "Reply with 'OK' if it looks correct, otherwise describe the specific issue and where it is."
)
PUPPETEER_SCRIPT = Path(__file__).with_name("puppeteer_html2pdf.js")


def render_html_with_puppeteer(
    html_path: Path,
    pdf_path: Path,
    wait_for_selector: str | None = None,
) -> None:
    """Run the JavaScript Puppeteer renderer and report subprocess failures clearly."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js was not found on PATH. Install Node.js to run Puppeteer.")
    if not PUPPETEER_SCRIPT.is_file():
        raise RuntimeError(f"Puppeteer renderer was not found: {PUPPETEER_SCRIPT}")

    command = [node, str(PUPPETEER_SCRIPT), str(html_path), str(pdf_path)]
    if wait_for_selector:
        command.extend(["--wait-for-selector", wait_for_selector])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Puppeteer did not finish rendering within 180 seconds.") from error

    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "No error output was provided."
        raise RuntimeError(f"Puppeteer rendering failed:\n{details}")

    if not pdf_path.is_file():
        raise RuntimeError(f"Puppeteer completed without creating the PDF: {pdf_path}")

    if result.stdout.strip():
        print(result.stdout.strip())


def run_pipeline(
    html_path: Path,
    dpi: int,
    prompt: str,
    wait_for_selector: str | None = None,
) -> None:
    html_path = html_path.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")

    pdf_path = html_path.with_name(f"{html_path.stem}_puppeteer.pdf")
    image_dir = html_path.with_name(f"{html_path.stem}_puppeteer_pages")

    print(f"[1/3] Rendering {html_path.name} with Puppeteer ...")
    render_html_with_puppeteer(html_path, pdf_path, wait_for_selector)

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
        description="Puppeteer HTML -> PDF -> page images -> optional Groq verification"
    )
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--wait-for-selector", help="CSS selector that appears when page rendering is ready")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    try:
        run_pipeline(args.html_file, args.dpi, args.prompt, args.wait_for_selector)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
