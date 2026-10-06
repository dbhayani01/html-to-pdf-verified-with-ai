import { createReadStream, createWriteStream } from "node:fs";
import { access, mkdir, readdir, rename, stat, readFile } from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { pipeline } from "node:stream/promises";
import { promisify } from "node:util";
import { pathToFileURL } from "node:url";

import { GetObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import puppeteer from "puppeteer";

const execFileAsync = promisify(execFile);
const DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b";
const DEFAULT_GROQ_PROMPT =
  "Check this rendered PDF page for overlapping elements, clipped or overflowing text, " +
  "broken tables, missing backgrounds or colors, and misaligned grids. Reply OK if correct; " +
  "otherwise describe the issue and where it appears.";

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Required environment variable ${name} is not set.`);
  return value;
}

function orderedPngFiles(directory) {
  return readdir(directory).then((names) => names
    .filter((name) => /^page_\d+\.png$/.test(name))
    .sort((left, right) => Number(left.match(/\d+/)[0]) - Number(right.match(/\d+/)[0]))
    .map((name) => ({ path: path.join(directory, name), pageNumber: Number(name.match(/\d+/)[0]) })));
}

async function waitForDocumentAssets(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    await Promise.all(Array.from(document.images, (image) => {
      if (image.complete) return Promise.resolve();
      return new Promise((resolve) => {
        image.addEventListener("load", resolve, { once: true });
        image.addEventListener("error", resolve, { once: true });
      });
    }));
  });
}

async function rasterizePdf(pdfPath, pagesDir, dpi) {
  await mkdir(pagesDir, { recursive: true });
  await execFileAsync("pdftoppm", ["-png", "-r", String(dpi), pdfPath, path.join(pagesDir, "page")]);
  const generatedNames = (await readdir(pagesDir)).filter((name) => /^page-\d+\.png$/.test(name));
  for (const name of generatedNames) {
    await rename(path.join(pagesDir, name), path.join(pagesDir, name.replace(/^page-(\d+)\.png$/, "page_$1.png")));
  }
  const pages = await orderedPngFiles(pagesDir);
  if (pages.length === 0) throw new Error("PDF rasterization produced no page images.");
  return pages;
}

async function reviewPagesWithGroq(pages) {
  const apiKey = process.env.GROQ_API_KEY?.trim();
  if (!apiKey) {
    console.log("Step 3/3: Skipping Groq visual review because GROQ_API_KEY is not set.");
    return;
  }

  const model = process.env.GROQ_VISION_MODEL?.trim() || DEFAULT_GROQ_MODEL;
  const prompt = process.env.GROQ_PROMPT?.trim() || DEFAULT_GROQ_PROMPT;
  console.log(`Step 3/3: Reviewing ${pages.length} page(s) with Groq model ${model}...`);
  for (const page of pages) {
    try {
      const imageBase64 = (await readFile(page.path)).toString("base64");
      const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          messages: [{
            role: "user",
            content: [
              { type: "text", text: prompt },
              { type: "image_url", image_url: { url: `data:image/png;base64,${imageBase64}` } },
            ],
          }],
          temperature: 0.2,
          max_completion_tokens: 1024,
        }),
        signal: AbortSignal.timeout(45000),
      });
      if (!response.ok) {
        throw new Error(`Groq API returned HTTP ${response.status}: ${(await response.text()).slice(0, 500)}`);
      }
      const result = await response.json();
      console.log(`\n--- page_${page.pageNumber}.png ---\n${result.choices?.[0]?.message?.content ?? "No review text was returned."}\n`);
    } catch (error) {
      console.error(`Groq review failed for page ${page.pageNumber}: ${error.message}`);
    }
  }
}

function getS3Input() {
  const bucket = process.env.INPUT_BUCKET?.trim();
  const key = process.env.INPUT_KEY?.trim();
  if (!bucket && !key) return null;
  if (!bucket || !key) throw new Error("Set both INPUT_BUCKET and INPUT_KEY to enable S3 input.");
  return { bucket, key };
}

async function downloadHtmlFromS3(s3Input, inputDirectory) {
  const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION;
  if (!region) throw new Error("Set AWS_REGION when INPUT_BUCKET is configured.");
  const fileName = path.posix.basename(s3Input.key);
  if (!fileName) throw new Error("INPUT_KEY must identify an HTML object, not a bucket prefix.");
  const localPath = path.join(inputDirectory, fileName);
  await mkdir(inputDirectory, { recursive: true });
  const client = new S3Client({ region });
  console.log(`Downloading HTML from s3://${s3Input.bucket}/${s3Input.key}...`);
  const response = await client.send(new GetObjectCommand({ Bucket: s3Input.bucket, Key: s3Input.key }));
  if (!response.Body) throw new Error(`S3 returned an empty body for s3://${s3Input.bucket}/${s3Input.key}.`);
  await pipeline(response.Body, createWriteStream(localPath));
  return localPath;
}

function pdfKeyForHtmlKey(inputKey) {
  const parsed = path.posix.parse(inputKey);
  return path.posix.join(parsed.dir, `${parsed.name || "report"}.pdf`);
}

async function storeArtifactsInS3(pdfPath, pages, inputStem, s3Input) {
  const bucket = process.env.OUTPUT_BUCKET?.trim() || s3Input?.bucket;
  if (!bucket) {
    console.log("Optional final export: keeping artifacts in task-local storage; OUTPUT_BUCKET is not set.");
    return;
  }

  const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION;
  if (!region) throw new Error("Set AWS_REGION when OUTPUT_BUCKET is configured.");
  const prefix = (process.env.OUTPUT_PREFIX?.trim() || "").replace(/^\/+|\/+$/g, "");
  const configuredKey = process.env.OUTPUT_KEY?.trim();
  const pdfKey = configuredKey || (s3Input
    ? pdfKeyForHtmlKey(s3Input.key)
    : path.posix.join(prefix, `${inputStem}.pdf`));
  const pdfParsed = path.posix.parse(pdfKey);
  const pagesPrefix = path.posix.join(pdfParsed.dir, `${pdfParsed.name}_pages`);
  const client = new S3Client({ region });

  console.log(`Storing completed artifacts in s3://${bucket}/...`);
  await client.send(new PutObjectCommand({
    Bucket: bucket,
    Key: pdfKey,
    Body: createReadStream(pdfPath),
    ContentLength: (await stat(pdfPath)).size,
    ContentType: "application/pdf",
  }));
  for (const page of pages) {
    const key = path.posix.join(pagesPrefix, `page_${page.pageNumber}.png`);
    await client.send(new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: createReadStream(page.path),
      ContentLength: (await stat(page.path)).size,
      ContentType: "image/png",
    }));
    console.log(`Stored s3://${bucket}/${key}`);
  }
  console.log(`Stored s3://${bucket}/${pdfKey}`);
}

async function main() {
  const s3Input = getS3Input();
  const outputDir = path.resolve(process.env.OUTPUT_DIR?.trim() || "/work/output");
  const inputPath = s3Input
    ? await downloadHtmlFromS3(s3Input, path.resolve(process.env.INPUT_DIR?.trim() || "/work/input"))
    : path.resolve(requiredEnv("INPUT_HTML_PATH"));
  const inputStem = path.parse(inputPath).name || "report";
  const pdfPath = path.resolve(process.env.OUTPUT_PDF_PATH?.trim() || path.join(outputDir, `${inputStem}.pdf`));
  const pagesDir = path.join(path.dirname(pdfPath), `${path.parse(pdfPath).name}_pages`);
  const dpi = Number(process.env.PDF_DPI || "150");
  if (!Number.isInteger(dpi) || dpi <= 0) throw new Error("PDF_DPI must be a positive integer.");
  const selector = process.env.WAIT_FOR_SELECTOR?.trim();

  await access(inputPath);
  await mkdir(path.dirname(pdfPath), { recursive: true });
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(inputPath).href, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForNetworkIdle({ idleTime: 500, timeout: 15000 }).catch(() => {});
    if (selector) await page.waitForSelector(selector, { timeout: 30000 });
    await waitForDocumentAssets(page);
    await page.pdf({
      path: pdfPath,
      format: process.env.PDF_FORMAT?.trim() || "A4",
      printBackground: true,
      preferCSSPageSize: true,
    });
  } finally {
    await browser.close();
  }

  console.log(`Step 1/3: PDF written to ${pdfPath}`);
  console.log(`Step 2/3: Rasterizing PDF pages at ${dpi} DPI...`);
  const pages = await rasterizePdf(pdfPath, pagesDir, dpi);
  console.log(`          ${pages.length} PNG page image(s) written to ${pagesDir}`);
  await reviewPagesWithGroq(pages);
  await storeArtifactsInS3(pdfPath, pages, inputStem, s3Input);
}

main().catch((error) => {
  console.error(`Puppeteer ECS task failed: ${error.message}`);
  process.exitCode = 1;
});
