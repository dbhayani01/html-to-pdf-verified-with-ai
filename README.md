# HTML to PDF AI

This project renders an HTML page to a PDF, converts the result into page images, and then uses a Groq vision model to detect visual problems in the rendered result.

## What it does

1. Loads an HTML file.
2. Renders it in a headless browser using Selenium and Chrome.
3. Saves the page as a PDF.
4. Converts each PDF page into PNG images.
5. Sends those images to the Groq vision model.
6. Prints a verdict describing whether the layout looks correct or points out issues.

This is useful for checking for problems like overlapping elements, clipped text, missing backgrounds, broken tables, misaligned grids, or other rendering defects.

## Project flow

```text
HTML -> browser rendering -> PDF -> PNG page images -> Groq vision verification
```

## Files in this project

- [selenium_html2pdf.py](selenium_html2pdf.py): main pipeline using Selenium + headless Chrome
- [html2pdf.py](html2pdf.py): alternative Fulgur-based renderer
- [sample.html](sample.html): sample HTML test input
- [requirements.txt](requirements.txt): Python dependencies

## Prerequisites

- Python 3.9+
- Google Chrome or Chromium installed on the machine
- A Groq API key saved in the environment variable `GROQ_API_KEY`
- Optional: if you use the Fulgur version in [html2pdf.py](html2pdf.py), the `fulgur` CLI must also be installed and available on your PATH

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Then set your API key:

```bash
export GROQ_API_KEY="your_api_key_here"
```

## Run the main pipeline

```bash
python selenium_html2pdf.py sample.html
```

You can also adjust the output quality and the checker prompt:

```bash
python selenium_html2pdf.py sample.html --dpi 200 --prompt "Check for layout and spacing issues only."
```

## Output

The script writes:

- a PDF file next to the source HTML file
- a folder of PNG page images for each page
- console output with the Groq verification result

## Notes

- The Selenium version is designed for pages that rely on JavaScript rendering.
- The script pauses briefly to allow charts, animations, and frontend scripts to finish loading before exporting the PDF.
- If `GROQ_API_KEY` is not set, the script still renders the PDF and page images, but skips AI verification.

## Main script

The active workflow is implemented in [selenium_html2pdf.py](selenium_html2pdf.py).
