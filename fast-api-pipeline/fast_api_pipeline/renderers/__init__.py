"""Renderer dispatch and public renderer choices."""

from pathlib import Path

from . import puppeteer, selenium_chromium, weasyprint, xhtml2pdf

RENDERERS = frozenset({"puppeteer", "selenium", "xhtml2pdf", "weasyprint"})


def render_html(
    html_path: Path,
    pdf_path: Path,
    renderer: str,
    wait_for_selector: str | None = None,
) -> None:
    """Render HTML to PDF using the selected implementation module."""
    selected = renderer.strip().lower()
    if selected == "puppeteer":
        puppeteer.render(html_path, pdf_path, wait_for_selector)
    elif selected == "selenium":
        selenium_chromium.render(html_path, pdf_path)
    elif selected == "xhtml2pdf":
        xhtml2pdf.render(html_path, pdf_path)
    elif selected == "weasyprint":
        weasyprint.render(html_path, pdf_path)
    else:
        choices = ", ".join(sorted(RENDERERS))
        raise ValueError(f"Unsupported renderer '{selected}'. Choose one of: {choices}.")
