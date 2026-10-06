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
- [`sample.html`](sample.html): Three-page, CSS-heavy sales report sample with responsive and print media rules, dashboards, decorative elements, and a JavaScript region filter; useful for testing browser PDF pagination and layout fidelity.
- [`playwright_mcp_test.html`](playwright_mcp_test.html): Small browser automation fixture with a counter, form, checkbox, and delayed content. It is not used by the PDF pipelines.
- [`playwright_mcp_e2e.js`](playwright_mcp_e2e.js): End-to-end MCP client that launches the Playwright MCP server, exercises the fixture controls, and asserts their accessible page state. Defaults to Firefox; supports Chromium, Firefox, WebKit, Chrome, or Edge selection.
- [`package.json`](package.json): Root Node dependencies and setup/run commands for the Playwright MCP and local Puppeteer flows.
- [`ecs/puppeteer-task/`](ecs/puppeteer-task/): Standalone ECS Fargate task package with a Puppeteer/Chrome container, local PDF and page-image generation, optional Groq review and final S3 export, task definition, IAM examples, and an offline Docker test pipeline.
- [`requirements.txt`](requirements.txt): Python dependencies for PDF rasterization, optional Groq review, WeasyPrint, and xhtml2pdf. Selenium has separate optional dependencies listed below.
- [`.gitignore`](.gitignore): Ignores generated PDFs, JPG/PNG files, and Python bytecode directories.

The Selenium flow has extra optional Python dependencies (`selenium` and `webdriver-manager`) installed separately below. The repository does not include generated PDFs or page images.

## Requirements and setup

Use Python 3.10 or newer. Python 3.10 is required for the union type annotations used by the command-line scripts. Install the declared Python dependencies:

```bash
python -m pip install -r requirements.txt
```

For the local Puppeteer pipeline, install Node.js/npm and its browser automation dependency in this directory:

```bash
npm install puppeteer
```

The project uses Node.js ES modules (`"type": "module"` in `package.json`); both JavaScript scripts follow that module format.

The Playwright MCP end-to-end flow uses the dependencies declared in `package.json`; see its dedicated setup steps below. The ECS task has its own isolated Node package and container image.

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
python puppeteer_pipeline.py sample.html
```

The output is written beside the input HTML file. For `sample.html`, the names are `sample_puppeteer.pdf` and `sample_puppeteer_pages/` (with one PNG per page). The other Python pipelines use the same naming pattern with `_selenium`, `_weasyprint`, `_xhtml2pdf`, or `_fulgur`.

Each Python pipeline accepts `--dpi` (default `150`) and `--prompt` (default layout-review prompt). All require an input HTML path. A missing input file or a DPI of zero or less is reported as a command-line error.

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
python selenium_html2pdf.py sample.html
python weasyprint_pipeline.py sample.html
python xhtml2pdf_pipeline.py sample.html
python html2pdf.py sample.html
```

The xhtml2pdf command creates `<name>_xhtml2pdf.pdf` and `<name>_xhtml2pdf_pages/` beside the source HTML. Its API is based on `pisa.CreatePDF()`; relative asset resolution uses the source file path.

The Puppeteer pipeline also accepts `--wait-for-selector <css-selector>` to wait for an element that signals JavaScript-rendered content is ready. The direct Node.js renderer accepts an optional output path and the same selector option; without an output path it writes `<input-name>.pdf` beside the input.

Call the Puppeteer renderer directly when only a PDF is needed:

```bash
node puppeteer_html2pdf.js sample.html [output.pdf] [--wait-for-selector "#report-ready"]
```

## Run Puppeteer as an ECS task

The [`ecs/puppeteer-task/`](ecs/puppeteer-task/) package runs a complete HTML report pipeline in one ECS Fargate task. Local HTML is the default; S3 input is optional:

1. By default, Puppeteer renders the local HTML file to a PDF in `/work/output`. If both `INPUT_BUCKET` and `INPUT_KEY` are provided, the task first downloads that HTML object from S3 into task-local storage and renders it instead.
2. Poppler rasterizes each PDF page to `/work/output/<pdf-name>_pages/page_<n>.png` at `PDF_DPI` (default `150`).
3. If `GROQ_API_KEY` is configured, each page PNG is sent to Groq for a layout review and the response is logged. Without a key, the API step is skipped.
4. After those steps, S3 input mode uploads the PDF back to the same bucket and prefix, with the `.html` extension replaced by `.pdf`, and uploads page images under a sibling `<pdf-name>_pages/` folder. If `OUTPUT_BUCKET` or `OUTPUT_KEY` is set, those values override the output location. For local input, final S3 upload is optional and only happens when `OUTPUT_BUCKET` is set.

By default, the image contains `sample.html` at `/work/input/report.html`, and results are written under `/work/output`. ECS task storage is temporary: files disappear when the task stops unless the optional final S3 export is enabled. The worker uses the ECS task role for S3 credentials; do not put AWS access keys in the task definition.

The image includes Node.js, Puppeteer, Chrome, Poppler, and the required Linux libraries. The HTML should bundle its CSS, fonts, images, and scripts locally. Keep relative assets beside the HTML file in local mode; S3 input mode downloads the HTML object only, so external relative assets must be embedded or otherwise available locally. A Groq API call requires outbound HTTPS access to `api.groq.com`; leave `GROQ_API_KEY` unset to skip it. S3 input/output requires an S3 VPC endpoint or other S3 connectivity and an ECS task role with `s3:GetObject` on the input prefix and `s3:PutObject` on the output prefix.

### Build and push the image

Create an ECR repository and replace the account and region placeholders with your values:

```bash
aws ecr create-repository --repository-name html-to-pdf-puppeteer --region <region>
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker build -f ecs/puppeteer-task/Dockerfile -t html-to-pdf-puppeteer:latest .
docker tag html-to-pdf-puppeteer:latest <account-id>.dkr.ecr.<region>.amazonaws.com/html-to-pdf-puppeteer:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/html-to-pdf-puppeteer:latest
```

The Docker build downloads npm packages and Puppeteer's Chrome for Testing, so perform the build where those downloads are available. The finished image contains them for offline task execution.

### Configure and run a task

1. Create the `/ecs/html-to-pdf-puppeteer` CloudWatch log group.
2. If using S3 input or output, create an ECS task role trusted by `ecs-tasks.amazonaws.com` using [`task-role-trust-policy.example.json`](ecs/puppeteer-task/task-role-trust-policy.example.json), grant the `s3:GetObject` and `s3:PutObject` permissions in [`task-role-policy.example.json`](ecs/puppeteer-task/task-role-policy.example.json) narrowed to the input and output prefixes, and set `taskRoleArn` in the task definition. If the buckets use customer-managed KMS keys, add the required KMS permissions and key policy access. Local-only processing does not need a task role.
3. Copy [`task-definition.example.json`](ecs/puppeteer-task/task-definition.example.json), replace the account, region, execution role, and ECR image values, then register it. Set `taskRoleArn` when enabling S3 input or output. The execution role needs ECR image-pull and CloudWatch Logs permissions (the AWS managed `AmazonECSTaskExecutionRolePolicy` is a common starting point).
4. The default task processes the HTML baked into the image. Use [`run-task-overrides.example.json`](ecs/puppeteer-task/run-task-overrides.example.json) for local-path input, or copy [`run-task-overrides.s3-input.example.json`](ecs/puppeteer-task/run-task-overrides.s3-input.example.json), replace `INPUT_BUCKET` and `INPUT_KEY`, and use it for S3 input. In S3 input mode, the PDF and page images are automatically written to the same bucket and prefix. Set `OUTPUT_BUCKET` and optionally `OUTPUT_KEY` in the override only to choose a different destination. Run the task in private subnets with `assignPublicIp=DISABLED`:

```bash
aws ecs run-task \
  --cluster <cluster-name> \
  --launch-type FARGATE \
  --task-definition html-to-pdf-puppeteer \
  --network-configuration 'awsvpcConfiguration={subnets=[<private-subnet-id>],securityGroups=[<task-security-group-id>],assignPublicIp=DISABLED}' \
  --overrides file://ecs/puppeteer-task/run-task-overrides.example.json \
  --region <region>
```

For a private task with no NAT, configure the ECR API and Docker interface endpoints for image pulls and a CloudWatch Logs interface endpoint for `awslogs`. Add an S3 endpoint when S3 input or output is enabled. Groq requires internet egress or an approved network path to its API. Rendering and rasterization need no public internet. See the [AWS ECS private connectivity guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/networking-connecting-vpc.html) and [ECR VPC endpoint requirements](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html).

`INPUT_BUCKET` and `INPUT_KEY` must both be set to enable S3 input; otherwise `INPUT_HTML_PATH` defaults to `/work/input/report.html`. `OUTPUT_DIR` defaults to `/work/output`. `PDF_FORMAT` defaults to A4, and `PDF_DPI` controls PNG resolution. `WAIT_FOR_SELECTOR` can be supplied when JavaScript adds a known ready element. Set `GROQ_VISION_MODEL` or `GROQ_PROMPT` to override the visual-review defaults. Store `GROQ_API_KEY` in Secrets Manager and add it to the container's `secrets` list; grant the execution role permission to read that secret. For S3 input, the output bucket defaults to the input bucket and the output PDF key defaults to the input key with its extension replaced by `.pdf`. `OUTPUT_BUCKET` and `OUTPUT_KEY` override the output location.

### Test the task locally with Docker

[`test-local.sh`](ecs/puppeteer-task/test-local.sh) checks that Docker Engine is available, builds the same renderer image, mounts the selected HTML and output directories, then runs the full PDF and page-image pipeline with Docker networking disabled (`--network none`). It verifies the PDF signature and that at least one PNG was produced. Groq review is skipped unless you explicitly provide `GROQ_API_KEY`; the script does not enable it by default. This checks local-file processing but does not emulate ECS task roles, Fargate networking, S3 input/output, or CloudWatch Logs.

Run it from the repository root (or any directory):

```bash
bash ecs/puppeteer-task/test-local.sh
```

Pass a different HTML file and output path as optional arguments:

```bash
bash ecs/puppeteer-task/test-local.sh sample.html /tmp/my-report.pdf
```

It writes `sample_ecs_local.pdf` and `sample_ecs_local_pages/` in the repository by default. The custom HTML's containing directory is mounted read-only, so relative assets in that directory are available to Chromium. Image build dependencies (base image, apt packages, npm packages, and Chrome) must be available during `docker build`; the test container itself runs with no network.

## Notes

- PDF and image outputs are written alongside the input HTML file; `.gitignore` excludes these generated files.
- Local Python pipelines use `qwen/qwen3.8-27b` for Groq verification by default. The ECS task uses the same default model and accepts `GROQ_VISION_MODEL` as an override.
- The Selenium script currently uses a fixed three-second delay for JavaScript rendering. For pages with variable render times, Puppeteer's `--wait-for-selector` option provides a page-specific readiness check.
