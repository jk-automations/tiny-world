// Open the saved Tiny World workflow in ComfyUI, switch to App Mode, screenshot it (README + demo proof).
import { chromium } from "playwright";
import fs from "fs";
const [url, wfPath, out] = process.argv.slice(2);
const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "tiny-world"); }, wf);
await page.waitForTimeout(3000);
await page.screenshot({ path: out.replace(".png", "-graph.png") });
// Breadcrumb dropdown (top left) -> "Enter app mode"; fall back to any button/menu item mentioning app mode.
for (const sel of ['text=Graph', 'button:has-text("Graph")']) {
  try { await page.click(sel, { timeout: 3000 }); break; } catch {}
}
await page.waitForTimeout(800);
let ok = false;
for (const sel of ['text=/enter app mode/i', 'text=/app mode/i', 'text=/^App$/']) {
  try { await page.click(sel, { timeout: 3000 }); ok = true; break; } catch {}
}
await page.waitForTimeout(3000);
try { await page.click("text=Skip", { timeout: 3000 }); } catch {}
await page.waitForTimeout(1000);
await page.screenshot({ path: out });
const texts = await page.evaluate(() => document.body.innerText.slice(0, 1500));
console.log("clicked app mode:", ok); console.log(texts.replace(/\n+/g, " | ").slice(0, 900));
await browser.close();
