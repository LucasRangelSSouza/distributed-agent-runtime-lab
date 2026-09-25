// Unauthenticated browser check for the public-demo edge (local profile).
// Opens the chat page, the RAG page, and the approved public dashboard in a
// fresh context (no cookies, like an incognito window), records every request
// status, and saves screenshots. Usage, from the repository root:
//   node scripts/public_demo_browser_check.mjs <dashboard-uuid> <output-dir>
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const require = createRequire(resolve("frontend/package.json"));
const { chromium } = require("@playwright/test");
const [uuid, outDir = "artifacts/public-demo"] = process.argv.slice(2);
if (!uuid) throw new Error("dashboard uuid required");
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
const pages = [
  ["chat", "https://localhost/"],
  ["rag", "https://localhost/rag/"],
  ["dashboard", `https://localhost/public/dashboard/${uuid}`],
];
const report = {};
for (const [name, url] of pages) {
  const page = await context.newPage();
  const seen = [];
  page.on("response", (r) => {
    const u = new URL(r.url());
    seen.push(`${r.status()} ${r.request().method()} ${u.pathname.replace(uuid, "<uuid>")}`);
  });
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  if (name === "dashboard") {
    await page.getByText("Average investment per basic education student by year").first().waitFor({ timeout: 90000 });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(5000);
  }
  if (name === "rag") {
    await page.fill("#question", "Which share of tax revenue goes to education maintenance and development?");
    await page.click("button[type=submit]");
    await page.waitForSelector(".citation", { timeout: 10000 });
  }
  await page.screenshot({ path: join(outDir, `public-demo-${name}.png`), fullPage: false });
  const statuses = seen.map((line) => line.split(" ")[0]);
  report[name] = { requests: seen.length, non2xx3xx: seen.filter((line) => !/^[23]/.test(line)), unique: [...new Set(seen.map((l) => l.replace(/\/[0-9a-f]{8,}[^ ]*\.(js|css|woff2?)$/, "/<asset>")))].slice(0, 40), statuses: [...new Set(statuses)] };
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 2));
