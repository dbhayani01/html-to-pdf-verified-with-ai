"""xhtml2pdf/ReportLab HTML-to-PDF renderer."""

from pathlib import Path


def render(html_path: Path, pdf_path: Path) -> None:
    try:
        from xhtml2pdf import pisa
    except ImportError as error:
        raise RuntimeError("Install the fast-api-pipeline requirements to use xhtml2pdf.") from error

    with html_path.open("r", encoding="utf-8") as source, pdf_path.open("wb") as output:
        result = pisa.CreatePDF(source, dest=output, path=str(html_path))
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} error(s) while rendering {html_path.name}.")
