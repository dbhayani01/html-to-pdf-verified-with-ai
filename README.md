# HTML to PDF rendering and visual checks

This repository contains several small command-line pipelines for rendering a local HTML file to PDF, converting the PDF pages to PNG images, and optionally asking a Groq vision model to inspect those images for layout issues. It is a collection of alternative renderers rather than one application with a single backend.

## How the pipelines work

```text
HTML file -> PDF (selected renderer) -> PNG images (PyMuPDF) -> optional Groq page review
```

The Groq review is optional. Without `GROQ_API_KEY`, each pipeline still writes its PDF and page images, then reports that review was skipped.

## Choose a renderer

| Command | Renderer | Useful when |
| --- | --- | --- |
| `python puppeteer_pipeline.py <file.html>` | Puppeteer with headless Chromium | The page runs JavaScript or needs browser rendering. |
| `python selenium_html2pdf.py <file.html>` | Selenium with headless Chrome | You want to use a locally managed Chrome/ChromeDriver flow. |
| `python weasyprint_pipeline.py <file.html>` | WeasyPrint | The page is mostly static and you want a Python renderer. |
| `python xhtml2pdf_pipeline.py <file.html>` | xhtml2pdf / ReportLab | You want a pure-Python renderer without a browser engine. |
| `python html2pdf.py <file.html>` | Fulgur CLI | You have the Fulgur command-line renderer installed. |

The browser renderers execute page JavaScript. WeasyPrint and xhtml2pdf do not execute JavaScript. xhtml2pdf is implemented in Python using ReportLab, HTML5 parsing, and PDF libraries; it does not launch Chrome or Chromium. Its CSS support is narrower than a browser renderer, so it is best for documents using straightforward layouts, text, tables, and images. WeasyPrint is another non-Chrome option with broader CSS support. `puppeteer_html2pdf.js` can also be called directly to render HTML to PDF without the Python rasterization or Groq steps.

## Project files

- [`puppeteer_pipeline.py`](puppeteer_pipeline.py): Runs the Puppeteer renderer, rasterizes the resulting PDF, and optionally submits each page image for Groq review. Supports a CSS selector to wait for page-specific rendering to finish.
- [`puppeteer_html2pdf.js`](puppeteer_html2pdf.js): Node.js/Puppeteer renderer used by `puppeteer_pipeline.py`. Waits for network activity, fonts, and images before printing to A4 PDF with backgrounds.
- [`selenium_html2pdf.py`](selenium_html2pdf.py): Selenium/Chrome version of the render, rasterize, and optional Groq review pipeline. It waits three seconds after navigation before printing.
- [`weasyprint_pipeline.py`](weasyprint_pipeline.py): WeasyPrint version of the pipeline. Resolves relative assets from the HTML file's directory.
- [`xhtml2pdf_pipeline.py`](xhtml2pdf_pipeline.py): Pure-Python xhtml2pdf/ReportLab version of the pipeline; it rasterizes output and optionally submits pages for Groq review.
- [`html2pdf.py`](html2pdf.py): Fulgur CLI version of the pipeline, plus shared PyMuPDF page-rasterization and Groq verification helpers imported by the Puppeteer and WeasyPrint pipelines.
- [`sample.html`](sample.html): Static report-style HTML sample with a styled header, CSS grid cards, and a table; useful for checking CSS-to-PDF output.
- [`js_sample.html`](js_sample.html): Interactive sales report sample. JavaScript populates metrics and table rows and filters rows by region, making it useful for checking browser-based rendering.
- [`playwright_mcp_test.html`](playwright_mcp_test.html): Small browser automation fixture with a counter, form, checkbox, and delayed content. It is not used by the PDF pipelines.
- [`playwright_mcp_e2e.js`](playwright_mcp_e2e.js): End-to-end MCP client that launches the Playwright MCP server, exercises the fixture controls, and asserts their accessible page state. Defaults to Firefox; supports Chromium, Firefox, WebKit, Chrome, or Edge selection.
- [`package.json`](package.json): Node dependencies and setup/run commands for the Playwright MCP end-to-end flow.
- [`requirements.txt`](requirements.txt): Python dependencies declared for the Fulgur, Puppeteer, and WeasyPrint flows.
- [`.gitignore`](.gitignore): Ignores generated PDFs, JPG/PNG files, and Python bytecode directories.

## Requirements and setup

Use Python 3.9 or newer. Install the declared Python dependencies:

```bash
python -m pip install -r requirements.txt
```

For the Puppeteer pipeline, install Node.js/npm and Puppeteer in this directory:

```bash
npm install puppeteer
```

For the Selenium pipeline, install Chrome and its Python packages:

```bash
python -m pip install selenium webdriver-manager
```

### Playwright MCP end-to-end flow

This is a browser automation check, separate from the HTML-to-PDF pipelines. It verifies that an MCP client can connect to the Playwright MCP server, navigate to the local fixture, interact with it, and observe the expected accessible page state. It does not create a PDF and does not need `GROQ_API_KEY`.

The flow has three parts:

1. [`playwright_mcp_e2e.js`](playwright_mcp_e2e.js) is the MCP client and test runner.
2. The runner launches Microsoft's `@playwright/mcp` server as a child process and connects over MCP stdio. You do not need to add a separate MCP server configuration to Codex or another client.
3. The server controls the selected Playwright browser and opens [`playwright_mcp_test.html`](playwright_mcp_test.html) from this project.

The runner verifies the initial counter and greeting, increments the counter, submits a name and checks the greeting, toggles the updates checkbox, and waits for the delayed result. It prints a `PASS` line for each completed step and exits with a nonzero status if an MCP action or assertion fails.

#### Install and run

Use Node.js 18 or newer. Install the npm dependencies and the browser build you want to use. Firefox is the default:

```bash
npm install
npm run install:firefox
npm run e2e:playwright-mcp
```

The browser installation is separate from `npm install`: the packages install the MCP client/server, while `npm run install:firefox` downloads Playwright's Firefox browser build. Select another engine with `--browser`:

```bash
npm run install:browsers # installs bundled Chromium, Firefox, and WebKit engines
npm run e2e:playwright-mcp -- --browser chromium
npm run e2e:playwright-mcp -- --browser webkit
```

The `install:browsers` command downloads Playwright's bundled Chromium, Firefox, and WebKit engines. WebKit is Playwright's Safari-like engine; it is not the Safari application. If you want to use the branded Chrome or Edge channel, install the corresponding browser and select it explicitly:

```bash
npm run install:chrome
npm run e2e:playwright-mcp -- --browser chrome
npm run install:edge
npm run e2e:playwright-mcp -- --browser msedge
```

For the runner, valid values are `chromium`, `firefox`, `webkit`, `chrome`, and `msedge`; omitting the option selects Firefox. The browser must be installed and supported on the current machine. The first setup requires network access to download npm packages and browser builds. See the [Playwright MCP configuration](https://github.com/microsoft/playwright-mcp#configuration) for its browser options.

#### Troubleshooting

- If the run says to install npm dependencies, run `npm install` from the repository root.
- If the selected browser is missing, run its matching install command above. Chrome and Edge channels may also require the branded browser to be installed on the machine.
- If browser installation fails on Linux due to missing system libraries, install the operating-system dependencies required by Playwright, then retry the browser installation.
- To switch browsers for one run, pass the option after `--`, for example `npm run e2e:playwright-mcp -- --browser webkit`.

`webdriver-manager` downloads/manages a compatible ChromeDriver. WeasyPrint also has platform-specific native library requirements; see the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) if its Python package cannot load. xhtml2pdf is installed from `requirements.txt`. The Fulgur pipeline requires the `fulgur` executable on `PATH`.

Set a Groq API key only when you want vision review:

```bash
export GROQ_API_KEY="your_api_key_here"
```

## Run a pipeline

Render and rasterize the JavaScript sales report with Puppeteer:

```bash
python puppeteer_pipeline.py js_sample.html
```

The output is written beside the input HTML file. For `js_sample.html`, the names are `js_sample_puppeteer.pdf` and `js_sample_puppeteer_pages/` (with one PNG per page). The other Python pipelines use the same naming pattern with `_selenium`, `_weasyprint`, or `_fulgur`.

For a page that signals readiness by adding an element, wait for that selector:

```bash
python puppeteer_pipeline.py report.html --wait-for-selector "#report-ready"
```

The selector must exist in the page. To change image resolution or the visual review prompt:

```bash
python puppeteer_pipeline.py report.html --dpi 200 --prompt "Check the chart labels and table alignment."
```

Run another backend by changing the script name:

```bash
python selenium_html2pdf.py js_sample.html
python weasyprint_pipeline.py sample.html
python xhtml2pdf_pipeline.py sample.html
python html2pdf.py sample.html
```

The xhtml2pdf command creates `<name>_xhtml2pdf.pdf` and `<name>_xhtml2pdf_pages/` beside the source HTML. Its API is based on `pisa.CreatePDF()`; relative asset resolution uses the source file path.

Call the Puppeteer renderer directly when only a PDF is needed:

```bash
node puppeteer_html2pdf.js sample.html [output.pdf] [--wait-for-selector "#report-ready"]
```

## Notes

- PDF and image outputs are written alongside the input HTML file; `.gitignore` excludes these generated files.
- Groq verification uses the `qwen/qwen3.8-27b` model configured in the Python code and sends each page image to the API.
- The Selenium script currently uses a fixed three-second delay for JavaScript rendering. For pages with variable render times, Puppeteer's `--wait-for-selector` option provides a page-specific readiness check.
