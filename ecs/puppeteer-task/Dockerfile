FROM node:22-bookworm-slim

ENV PUPPETEER_CACHE_DIR=/home/node/.cache/puppeteer \
    NODE_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
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
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
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
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app /home/node/.cache/puppeteer /work/input /work/output \
    && chown -R node:node /app /home/node/.cache /work

WORKDIR /app
USER node

COPY --chown=node:node ecs/puppeteer-task/package.json ecs/puppeteer-task/package-lock.json ./
RUN npm ci --omit=dev

COPY --chown=node:node ecs/puppeteer-task/task.js ./
COPY --chown=node:node sample.html /work/input/report.html

ENV INPUT_HTML_PATH=/work/input/report.html OUTPUT_DIR=/work/output

ENTRYPOINT ["node", "task.js"]
