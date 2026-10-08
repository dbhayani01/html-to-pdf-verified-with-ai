"""FastAPI service that renders uploaded HTML with a selected backend."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from starlette.background import BackgroundTask

from fast_api_pipeline import RENDERERS, run_pipeline
from fast_api_pipeline.groq_review import DEFAULT_PROMPT

app = FastAPI(
    title="HTML to PDF API",
    description="Render an HTML report to PDF and page images using one of four backends.",
    version="1.0.0",
)

_DOWNLOAD_TTL_SECONDS = 60 * 60
_completed_downloads: dict[str, dict[str, Any]] = {}
_downloads_lock = threading.Lock()


def _safe_stem(filename: str | None) -> str:
    stem = Path(filename or "report.html").stem
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return safe or "report"


def _cleanup_expired_downloads() -> None:
    now = time.time()
    expired: list[dict[str, Any]] = []
    with _downloads_lock:
        for download_id, entry in list(_completed_downloads.items()):
            if now - entry["created_at"] > _DOWNLOAD_TTL_SECONDS:
                expired.append(_completed_downloads.pop(download_id))
    for entry in expired:
        shutil.rmtree(entry["work_dir"], ignore_errors=True)


def _cleanup_download(download_id: str) -> None:
    with _downloads_lock:
        entry = _completed_downloads.pop(download_id, None)
    if entry:
        shutil.rmtree(entry["work_dir"], ignore_errors=True)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home_page(download: str | None = Query(None)) -> Any:
    """Serve the upload form or a completed ZIP download from the homepage."""
    _cleanup_expired_downloads()
    if download:
        with _downloads_lock:
            entry = _completed_downloads.get(download)
        if not entry:
            raise HTTPException(status_code=404, detail="This download has expired or was already downloaded.")
        return FileResponse(
            entry["zip_path"],
            media_type="application/zip",
            filename=entry["filename"],
            background=BackgroundTask(_cleanup_download, download),
        )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTML to PDF pipeline</title>
  <style>
    body { font: 16px/1.5 system-ui, sans-serif; max-width: 760px; margin: 8vh auto; padding: 0 1rem; color: #182230; background: #f5f7fa; }
    main { background: white; border: 1px solid #dce2ea; border-radius: 12px; padding: 2rem; box-shadow: 0 8px 24px #18223012; }
    h1 { margin-top: 0; } p { color: #526174; }
    label { display: block; margin: 1rem 0 .35rem; font-weight: 600; }
    input, select, button { box-sizing: border-box; width: 100%; padding: .7rem; border: 1px solid #bdc7d4; border-radius: 7px; font: inherit; }
    button { margin-top: 1.5rem; border: 0; color: white; background: #175cd3; font-weight: 700; cursor: pointer; }
    button:hover { background: #1849a9; }
    button:disabled { opacity: .65; cursor: wait; }
    .docs { margin-top: 1rem; font-size: .9rem; }
    #progress { margin-top: 1.5rem; padding: 0; list-style: none; }
    #progress li { margin: .5rem 0; padding: .65rem .8rem; border-radius: 7px; background: #f2f4f7; }
    #progress li.complete { color: #05603a; background: #ecfdf3; }
    #progress li.error { color: #b42318; background: #fef3f2; }
    #download { display: inline-block; margin-top: 1rem; padding: .7rem 1rem; border-radius: 7px; color: white; background: #067647; text-decoration: none; font-weight: 700; }
    #download[hidden] { display: none; }
  </style>
</head>
<body>
  <main>
    <h1>HTML to PDF pipeline</h1>
    <p>Upload an HTML report to render a PDF and page images. Follow progress here, then download the completed ZIP.</p>
    <form action="/" method="post" enctype="multipart/form-data">
      <label for="file">HTML report</label>
      <input id="file" name="file" type="file" accept=".html,.htm,text/html" required>
      <label for="renderer">Renderer</label>
      <select id="renderer" name="renderer">
        <option value="puppeteer">Puppeteer</option>
        <option value="selenium">Selenium / Chromium</option>
        <option value="xhtml2pdf">xhtml2pdf</option>
        <option value="weasyprint">WeasyPrint</option>
      </select>
      <label for="dpi">Image resolution (DPI)</label>
      <input id="dpi" name="dpi" type="number" min="36" max="600" value="150" required>
      <label for="wait_for_selector">Puppeteer readiness selector (optional)</label>
      <input id="wait_for_selector" name="wait_for_selector" type="text" placeholder="#report-ready">
      <button id="submit" type="submit">Render report</button>
    </form>
    <ol id="progress" aria-live="polite"></ol>
    <a id="download" href="#" hidden>Download result ZIP</a>
    <p class="docs">API schema: <a href="/docs">/docs</a></p>
  </main>
  <script>
    const form = document.querySelector("form");
    const button = document.querySelector("#submit");
    const progress = document.querySelector("#progress");
    const download = document.querySelector("#download");
    function addProgress(event) {
      const item = document.createElement("li");
      item.textContent = event.message || event.error || "Processing update";
      if (event.status === "complete" || event.status === "skipped") item.className = "complete";
      if (event.status === "error") item.className = "error";
      progress.append(item);
      if (event.review) {
        const review = document.createElement("p");
        review.textContent = event.review;
        item.append(review);
      }
      if (event.status === "ready" && event.download_url) {
        download.href = event.download_url;
        download.hidden = false;
      }
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      progress.replaceChildren();
      download.hidden = true;
      button.disabled = true;
      button.textContent = "Processing…";
      try {
        const response = await fetch("/", { method: "POST", body: new FormData(form) });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.detail || `Request failed (${response.status})`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = "";
        while (true) {
          const { value, done } = await reader.read();
          pending += decoder.decode(value || new Uint8Array(), { stream: !done });
          const lines = pending.split("\\n");
          pending = lines.pop() || "";
          for (const line of lines) if (line.trim()) addProgress(JSON.parse(line));
          if (done) break;
        }
        if (pending.trim()) addProgress(JSON.parse(pending));
      } catch (error) {
        addProgress({ status: "error", message: error.message });
      } finally {
        button.disabled = false;
        button.textContent = "Render report";
      }
    });
  </script>
</body>
</html>"""


@app.post("/", summary="Stream report processing progress")
async def render_report(
    file: UploadFile = File(..., description="HTML report file"),
    renderer: str = Form("puppeteer", description="puppeteer, selenium, xhtml2pdf, or weasyprint"),
    dpi: int = Form(150, ge=36, le=600, description="Resolution used for page PNGs"),
    wait_for_selector: str | None = Form(
        None,
        description="Optional readiness selector; supported by Puppeteer",
    ),
    groq_prompt: str = Form(DEFAULT_PROMPT, description="Optional prompt for Groq page review"),
) -> StreamingResponse:
    renderer = renderer.strip().lower()
    if renderer not in RENDERERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported renderer '{renderer}'. Choose one of: {', '.join(sorted(RENDERERS))}.",
        )
    _cleanup_expired_downloads()

    work_dir = Path(tempfile.mkdtemp(prefix="html-to-pdf-api-"))
    stem = _safe_stem(file.filename)
    html_path = work_dir / f"{stem}.html"
    pdf_dir = work_dir / "pdf"
    images_dir = work_dir / "images"
    pdf_path = pdf_dir / f"{stem}.pdf"
    zip_path = work_dir / f"{stem}.zip"

    try:
        pdf_dir.mkdir(parents=True)
        with html_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                destination.write(chunk)
        if html_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="The uploaded HTML file is empty.")
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception as error:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to receive HTML upload: {error}") from error
    finally:
        await file.close()

    loop = asyncio.get_running_loop()
    progress_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    download_id = uuid.uuid4().hex
    download_filename = f"{stem}_{renderer}.zip"

    def publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, event)

    def process_job() -> None:
        try:
            result = run_pipeline(
                html_path=html_path,
                pdf_path=pdf_path,
                images_dir=images_dir,
                renderer=renderer,
                dpi=dpi,
                wait_for_selector=wait_for_selector,
                groq_prompt=groq_prompt,
                progress_callback=publish,
            )
            publish({"step": "zip", "status": "started", "message": "Packaging the PDF and page images…"})
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("pdf/", "")
                archive.writestr("images/", "")
                archive.write(pdf_path, arcname=f"pdf/{pdf_path.name}")
                for image_path in result.image_paths:
                    archive.write(image_path, arcname=f"images/{image_path.name}")

            with _downloads_lock:
                _completed_downloads[download_id] = {
                    "zip_path": zip_path,
                    "work_dir": work_dir,
                    "filename": download_filename,
                    "created_at": time.time(),
                }
            publish({"step": "zip", "status": "complete", "message": "ZIP package is ready."})
            publish({
                "step": "done",
                "status": "ready",
                "message": "All processing is complete. Download your ZIP.",
                "download_url": f"/?download={download_id}",
            })
        except Exception as error:
            shutil.rmtree(work_dir, ignore_errors=True)
            publish({"step": "error", "status": "error", "message": f"{renderer} rendering failed: {error}"})
        finally:
            loop.call_soon_threadsafe(progress_queue.put_nowait, None)

    async def stream_progress():
        asyncio.create_task(asyncio.to_thread(process_job))
        while True:
            event = await progress_queue.get()
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream_progress(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
