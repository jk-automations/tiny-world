// Screen-record a real Tiny World run in ComfyUI App Mode (for the demo): open the app, fill the inputs, press Run,
// keep recording while it starts. The photos must already be uploaded to ComfyUI's input folder.
// node record_app.mjs <comfy_url> <workflow.json> <out_dir> <photo> <c1> <c2> <c3> <template> "<name>" [seconds]
import { chromium } from "playwright";
import fs from "fs";
const [url, wfPath, outDir, photo, c1, c2, c3, template, name, secs = "75"] = process.argv.slice(2);
const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
// The photos are set before loading (no "missing file" warning on screen); the recording shows the choices and Run.
const imgs = wf.nodes.filter((n) => n.type === "LoadImage").sort((a, b) => a.id - b.id);
[photo, c1, c2, c3].forEach((f, i) => { imgs[i].widgets_values[0] = f; });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2,
                                       recordVideo: { dir: outDir, size: { width: 1280, height: 800 } } });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "tiny-world"); }, wf);
await page.waitForTimeout(2500);
for (const t of ["text=Skip", "text=Close"]) { try { await page.click(t, { timeout: 1500 }); } catch {} }
// Fill like a user would, one field at a time so the recording shows it.
const set = async (pred, widget, value) => page.evaluate(({ pred, widget, value }) => {
  const g = window.app.graph;
  const n = g.nodes.find((x) => (pred.id ? String(x.id) === String(pred.id) : x.type === pred.type));
  const w = n.widgets.find((x) => x.name === widget); w.value = value; w.callback && w.callback(value);
  g.setDirtyCanvas(true, true);
}, { pred, widget, value });
const ids = await page.evaluate(() => window.app.graph.nodes.filter((n) => n.type === "LoadImage").map((n) => String(n.id)));
const steps = [[{ type: "TinyWorldTemplate" }, "template", template], [{ type: "TinyWorldFinish" }, "name", name]];
for (const [pred, widget, value] of steps) { await set(pred, widget, value); await page.waitForTimeout(1400); }
await page.waitForTimeout(1500);
await page.locator('button:visible:has-text("Run")').last().click();
await page.waitForTimeout(Number(secs) * 1000);
await ctx.close(); await browser.close();
console.log("recorded into", outDir);
