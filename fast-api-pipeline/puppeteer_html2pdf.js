import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer";

function parseArgs(args) {
  const positional = [];
  let waitForSelector;

  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--wait-for-selector") {
      waitForSelector = args[index + 1];
      if (!waitForSelector) {
        throw new Error("--wait-for-selector requires a CSS selector.");
      }
      index += 1;
    } else if (args[index].startsWith("--")) {
      throw new Error(`Unknown option: ${args[index]}`);
    } else {
      positional.push(args[index]);
    }
  }

  if (positional.length < 1 || positional.length > 2) {
    throw new Error(
      "Usage: node puppeteer_html2pdf.js <input.html> [output.pdf] [--wait-for-selector <selector>]",
    );
  }

  const inputPath = path.resolve(positional[0]);
  const outputPath = path.resolve(
    positional[1] ??
      path.join(
        path.dirname(inputPath),
        `${path.basename(inputPath, path.extname(inputPath))}.pdf`,
      ),
  );

  return { inputPath, outputPath, waitForSelector };
}

async function htmlToPdf(inputPath, outputPath, waitForSelector) {
  await fs.access(inputPath);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(pathToFileURL(inputPath).href, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    await page.waitForNetworkIdle({ idleTime: 500, timeout: 15000 }).catch(() => {});

    if (waitForSelector) {
      await page.waitForSelector(waitForSelector, { timeout: 30000 });
    }

    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        Array.from(document.images, (image) => {
          if (image.complete) return Promise.resolve();
          return new Promise((resolve) => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });
          });
        }),
      );
    });

    await page.pdf({
      path: outputPath,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
    });
  } finally {
    await browser.close();
  }
}

async function main() {
  const { inputPath, outputPath, waitForSelector } = parseArgs(process.argv.slice(2));
  await htmlToPdf(inputPath, outputPath, waitForSelector);
  console.log(`PDF written to ${outputPath}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
