# FastAPI HTML-to-PDF pipeline

This folder contains the FastAPI service and all code and dependency manifests it needs. It supports four rendering backends, PDF page rasterization, and optional Groq vision review.

## Install and run

From this folder:

```bash
python -m pip install -r requirements.txt
npm install
uvicorn fast_api_pipeline.api:app --app-dir . --host 127.0.0.1 --port 8000
```

For Selenium, install Chrome or Chromium. If the machine cannot download a driver, set `CHROMEDRIVER_PATH` to an installed ChromeDriver and `CHROME_BINARY` if the browser is not discoverable. WeasyPrint may need platform-specific system libraries.

Set `GROQ_API_KEY` in the service environment to enable image review. `GROQ_VISION_MODEL` optionally overrides the default model.

## Build and run with Docker Compose

The folder includes a [`Dockerfile`](Dockerfile) with all four renderer runtimes and a [`docker-compose.yml`](docker-compose.yml) for local use:

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000/`. To enable Groq review, export `GROQ_API_KEY` before starting Compose. Stop the service with `docker compose down`.

The image build downloads Debian packages, Python packages, npm packages, and Puppeteer's Chrome for Testing. The running container already contains its renderers; Selenium uses the packaged Chromium and ChromeDriver, so it does not need to download a browser at runtime.

Open `http://127.0.0.1:8000/` to use the homepage upload form. It streams progress for PDF rendering, image conversion, optional Groq review, and ZIP packaging, then reveals a download button when the ZIP is ready. The form and download both use the homepage path `/`. You can also submit to `POST /` from `http://127.0.0.1:8000/docs`. The form fields are:

- `file`: the HTML report to render.
- `renderer`: `puppeteer`, `selenium`, `xhtml2pdf`, or `weasyprint` (default `puppeteer`).
- `dpi`: PNG resolution from 36 to 600 (default `150`).
- `wait_for_selector`: optional Puppeteer readiness selector.
- `groq_prompt`: optional page-review prompt.

The returned ZIP contains `pdf/<report>.pdf` and `images/page_<n>.png`. Groq results are written to service logs and do not change the ZIP layout.

Example:

```bash
curl -X POST http://127.0.0.1:8000/ \
  -F "file=@../sample.html" \
  -F "renderer=puppeteer" \
  -F "dpi=150" \
  -o report.zip
```

## Package modules

- `fast_api_pipeline.renderers.puppeteer`: Puppeteer/Chromium renderer.
- `fast_api_pipeline.renderers.selenium_chromium`: Selenium/Chromium renderer.
- `fast_api_pipeline.renderers.xhtml2pdf`: xhtml2pdf/ReportLab renderer.
- `fast_api_pipeline.renderers.weasyprint`: WeasyPrint renderer.
- `fast_api_pipeline.renderers`: dispatches the four backend choices used in the dropdown.
- `fast_api_pipeline.pdf_to_images`: PDF page rasterization.
- `fast_api_pipeline.groq_review`: optional Groq page review.
- `fast_api_pipeline.pipeline`: orchestration and `PipelineResult`.
- `fast_api_pipeline.api`: FastAPI app and ZIP response.

Import the reusable orchestrator from this folder with `from fast_api_pipeline import run_pipeline`.

The service accepts one HTML file; it does not upload companion files from the report's directory. Bundle CSS, fonts, images, and scripts in the HTML or make them accessible through the service environment. Puppeteer and Selenium execute JavaScript. Keep the unauthenticated development service on a trusted host; add authentication and upload limits before exposing it to untrusted clients.

## Deploy on ECS Fargate

The [`ecs-task-definition.example.json`](ecs-task-definition.example.json) defines a Fargate task for the API container. Build and push the image to ECR from this folder:

```bash
aws ecr create-repository --repository-name html-to-pdf-fastapi --region <region>
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker build -t html-to-pdf-fastapi:latest .
docker tag html-to-pdf-fastapi:latest <account-id>.dkr.ecr.<region>.amazonaws.com/html-to-pdf-fastapi:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/html-to-pdf-fastapi:latest
```

Create the `/ecs/html-to-pdf-fastapi` CloudWatch log group. Replace the account, region, execution-role, and ECR image placeholders in the task definition, then register it:

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.example.json \
  --region <region>
```

The ECS task execution role needs ECR image-pull and CloudWatch Logs permissions (the AWS managed `AmazonECSTaskExecutionRolePolicy` is a common starting point). To enable Groq review, add a Secrets Manager value to the container definition's `secrets` list for `GROQ_API_KEY`; grant the execution role permission to read the secret. Groq review also needs outbound HTTPS access to the Groq API.

Run the task as a long-lived ECS service so the API remains available. The in-memory download handoff is designed for one running task; keep `desired-count` at `1` unless you add shared download storage or session affinity. Allow inbound TCP port `8000` only from trusted clients or a load balancer:

```bash
aws ecs create-service \
  --cluster <cluster-name> \
  --service-name html-to-pdf-fastapi \
  --task-definition html-to-pdf-fastapi \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration 'awsvpcConfiguration={subnets=[<private-subnet-id>],securityGroups=[<task-security-group-id>],assignPublicIp=DISABLED}' \
  --region <region>
```

For private subnets without NAT, provide the ECR API and Docker interface endpoints plus a CloudWatch Logs endpoint so ECS can pull the image and send logs. The container doesn't need public internet for rendering; allow external egress only if you enable Groq. Build the image in an environment that can access package registries and Puppeteer's browser download.
