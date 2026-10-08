"""WeasyPrint HTML-to-PDF renderer."""

from pathlib import Path


def render(html_path: Path, pdf_path: Path) -> None:
    try:
        from weasyprint import HTML
    except ImportError as error:
        raise RuntimeError("Install the fast-api-pipeline requirements to use WeasyPrint.") from error

    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))
