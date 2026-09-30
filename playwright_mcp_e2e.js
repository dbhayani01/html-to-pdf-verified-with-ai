// End-to-end exercise of the local fixture through Microsoft's Playwright MCP server.
// Usage: npm run e2e:playwright-mcp
// Firefox is the default; --browser selects the Playwright browser/channel.

import assert from "node:assert/strict";
import { access } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const projectDir = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.join(projectDir, "playwright_mcp_test.html");
const mcpCliPath = path.join(projectDir, "node_modules", "@playwright", "mcp", "cli.js");
const supportedBrowsers = ["chromium", "firefox", "webkit", "chrome", "msedge"];

function parseBrowser(args) {
  if (args.length === 0) return "firefox";
  if (args.length !== 2 || args[0] !== "--browser") {
    throw new Error("Usage: node playwright_mcp_e2e.js [--browser <engine>]");
  }
  const browserIndex = args.indexOf("--browser");
  const browser = args[browserIndex + 1];
  if (!browser || !supportedBrowsers.includes(browser)) {
    throw new Error(`Choose --browser ${supportedBrowsers.join("|")}.`);
  }
  return browser;
}

function resultText(result) {
  assert.notEqual(result.isError, true, "MCP tool call returned an error");
  return (result.content ?? [])
    .filter((item) => item.type === "text")
    .map((item) => item.text)
    .join("\n");
}

async function main() {
  const browser = parseBrowser(process.argv.slice(2));
  await access(mcpCliPath).catch(() => {
    throw new Error("Install npm dependencies first with `npm install`.");
  });

  const client = new Client({ name: "html-to-pdf-playwright-mcp-e2e", version: "1.0.0" });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [mcpCliPath, "--browser", browser, "--headless", "--isolated"],
    cwd: projectDir,
  });

  try {
    await client.connect(transport);

    const navigation = await client.callTool({
      name: "browser_navigate",
      arguments: { url: pathToFileURL(fixturePath).href },
    });
    resultText(navigation);
    console.log("PASS: navigated to the local Playwright MCP fixture");

    const initialPage = resultText(await client.callTool({ name: "browser_snapshot", arguments: {} }));
    assert.match(initialPage, /Count:\s*0/, "counter should start at zero");
    assert.match(initialPage, /No greeting submitted\./, "greeting should start empty");
    console.log("PASS: initial counter and form state");

    resultText(await client.callTool({
      name: "browser_click",
      arguments: { target: "#increment", element: "Increment button" },
    }));
    const counterPage = resultText(await client.callTool({ name: "browser_snapshot", arguments: {} }));
    assert.match(counterPage, /Count:\s*1/, "counter should increment to one");
    console.log("PASS: counter interaction");

    resultText(await client.callTool({
      name: "browser_type",
      arguments: { target: "#name", element: "Name input", text: "Ada Lovelace" },
    }));
    resultText(await client.callTool({
      name: "browser_click",
      arguments: { target: "button[type=submit]", element: "Submit greeting button" },
    }));
    const greetingPage = resultText(await client.callTool({ name: "browser_snapshot", arguments: {} }));
    assert.match(greetingPage, /Hello, Ada Lovelace!/, "form should render the submitted greeting");
    console.log("PASS: form submission");

    resultText(await client.callTool({
      name: "browser_click",
      arguments: { target: "#updates", element: "Receive updates checkbox" },
    }));
    const preferencePage = resultText(await client.callTool({ name: "browser_snapshot", arguments: {} }));
    assert.match(preferencePage, /Updates are on\./, "checkbox should update preference text");
    console.log("PASS: checkbox preference");

    resultText(await client.callTool({
      name: "browser_wait_for",
      arguments: { text: "Delayed result is ready." },
    }));
    const completedPage = resultText(await client.callTool({ name: "browser_snapshot", arguments: {} }));
    assert.match(completedPage, /Delayed result is ready\./, "delayed content should appear");
    console.log("PASS: delayed content");
    console.log(`Playwright MCP end-to-end flow passed with ${browser}.`);
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  console.error(`Playwright MCP end-to-end flow failed: ${error.message}`);
  process.exitCode = 1;
});
