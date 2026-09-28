# HTML to PDF AI

This project renders HTML files to PDFs, converts PDF pages into images, and can use a Groq vision model to detect visual layout problems. The Puppeteer pipeline runs JavaScript in a headless browser before exporting the PDF.

## What it does

1. Loads an HTML file in a headless browser.
2. Executes page JavaScript and waits for rendering resources to settle.
3. Saves the rendered page as a PDF.
4. Converts each PDF page into a PNG image.
5. Optionally sends the images to the Groq vision model for layout verification.

This is useful for checking for problems like overlapping elements, clipped text, missing backgrounds, broken tables, misaligned grids, or other rendering defects.

## Project flow

```text
HTML -> JavaScript/browser rendering -> PDF -> PNG page images -> optional Groq verification
```

## Files in this project

- [puppeteer_pipeline.py](puppeteer_pipeline.py): Python pipeline using Puppeteer, PDF rasterization, and optional Groq verification
- [puppeteer_html2pdf.js](puppeteer_html2pdf.js): headless Chromium HTML-to-PDF renderer called by the Python pipeline
- [selenium_html2pdf.py](selenium_html2pdf.py): Selenium + Chrome pipeline
- [html2pdf.py](html2pdf.py): Fulgur-based pipeline and shared PDF image/verification helpers
- [sample.html](sample.html): sample HTML test input
- [requirements.txt](requirements.txt): Python dependencies

## Prerequisites

- Python 3.9+
- Node.js and npm
- Puppeteer (downloads a compatible headless Chrome/Chromium browser)
- Optional: a Groq API key in the `GROQ_API_KEY` environment variable to enable visual verification
- Optional: if you use the Fulgur flow in [html2pdf.py](html2pdf.py), the `fulgur` CLI must be installed and available on your PATH

## Setup

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Install Puppeteer from the project directory:

```bash
npm init -y
npm install puppeteer
```

Set an API key only if you want Groq verification:

```bash
export GROQ_API_KEY="your_api_key_here"
```

## Run the Puppeteer pipeline

```bash
python puppeteer_pipeline.py sample.html
```

The pipeline creates `sample_puppeteer.pdf` and a `sample_puppeteer_pages/` folder beside the HTML file. If `GROQ_API_KEY` is set, it also sends each page image for verification. Otherwise, rendering and image conversion still complete and Groq verification is skipped.

For JavaScript-heavy pages, you can wait for a page-specific element that appears when rendering is complete:

```bash
python puppeteer_pipeline.py report.html --wait-for-selector "#report-ready"
```

Only use a selector that the input page actually creates. For example, `sample.html` does not contain `#report-ready`, so run it without the selector.

Adjust rasterization quality or the Groq prompt with:

```bash
python puppeteer_pipeline.py sample.html --dpi 200 --prompt "Check for layout and spacing issues only."
```

## Other renderers

The Selenium-based pipeline can be run with:

```bash
python selenium_html2pdf.py sample.html
```

The Fulgur-based pipeline can be run with:

```bash
python html2pdf.py sample.html
```
