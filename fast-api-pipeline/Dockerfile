FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:${PATH}" \
    PUPPETEER_CACHE_DIR=/opt/puppeteer \
    CHROME_BINARY=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-core \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libffi8 \
    libgbm1 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libharfbuzz0b \
    libjpeg62-turbo \
    libnspr4 \
    libnss3 \
    libopenjp2-7 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    python3 \
    python3-venv \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && mkdir -p /opt/puppeteer

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json puppeteer_html2pdf.js ./
RUN npm ci --omit=dev --no-audit --no-fund \
    && chmod -R a+rX /opt/puppeteer

COPY fast_api_pipeline ./fast_api_pipeline

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app /home/app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/', timeout=3)" || exit 1

CMD ["uvicorn", "fast_api_pipeline.api:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
