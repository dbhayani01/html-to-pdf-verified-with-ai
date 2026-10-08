"""Puppeteer/Chromium HTML-to-PDF renderer."""

import shutil
import subprocess
from pathlib import Path


def render(html_path: Path, pdf_path: Path, wait_for_selector: str | None = None) -> None:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js was not found on PATH. Install the fast-api-pipeline npm dependencies.")

    script_path = Path(__file__).resolve().parents[2] / "puppeteer_html2pdf.js"
    command = [node, str(script_path), str(html_path), str(pdf_path)]
    if wait_for_selector:
        command.extend(["--wait-for-selector", wait_for_selector])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Puppeteer did not finish rendering within 180 seconds.") from error
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip() or "No error output was provided."
        raise RuntimeError(f"Puppeteer rendering failed:\n{details}")
