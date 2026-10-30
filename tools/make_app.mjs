// Turn the API-format graph into a normal ComfyUI workflow with App Mode set up, using ComfyUI's own frontend
// (so the saved file is exactly what the editor writes). Then reload it and screenshot the app view as proof.
// node tools/make_app.mjs <comfy_url> <api.json> <out_workflow.json> <screenshot_prefix>
import { chromium } from "playwright";
import fs from "fs";

const [url, apiPath, outPath, shot] = process.argv.slice(2);
const api = JSON.parse(fs.readFileSync(apiPath, "utf8"));
const id = (cls, nth = 0) => Object.entries(api).filter(([, n]) => n.class_type === cls)[nth][0];
// What a user sees in App Mode: their photos, the choices and the name. Everything else stays locked in the graph.
const INPUTS = [
  [id("LoadImage", 0), "image"], [id("TinyWorldTemplate"), "template"], [id("TinyWorldFinish"), "name"],
  [id("LoadImage", 1), "image"], [id("LoadImage", 2), "image"], [id("LoadImage", 3), "image"],
  [id("TinyWorldExtras"), "intro"], [id("TinyWorldExtras"), "giant_guest"], [id("LoadImage", 4), "image"],
  [id("TinyWorldExtras"), "tiny_me"], [id("LoadImage", 5), "image"], [id("TinyWorldExtras"), "tiny_to_real"], [id("TinyWorldTemplate"), "figure"], [id("TinyWorldFinish"), "motion"], [id("TinyWorldFinish"), "bobble"], [id("TinyWorldGlowUp"), "glow_up"], [id("TinyWorldGlowUp"), "glow_closeups"],
  [id("TinyWorldTemplate"), "look"], [id("TinyWorldTemplate"), "extra_details"],
  [id("TinyWorldTemplate"), "closeup_set"], [id("TinyWorldTemplate"), "endcard_line"],
  [id("TinyWorldFinish"), "hook_text"], [id("TinyWorldFinish"), "ending"], [id("TinyWorldFinish"), "music"],
  [id("TinyWorldFinish"), "credit"], [id("TinyWorldTemplate"), "auto_shape"], [id("TinyWorldFacts"), "enabled"], [id("KSampler", 4), "seed"],   // KSamplers 0-3 are the glow-ups
];
const OUTPUTS = [id("SaveVideo"), id("PreviewImage")];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
page.on("pageerror", (e) => console.log("pageerror:", e.message));
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
const wf = await page.evaluate(async ({ api, INPUTS, OUTPUTS }) => {
  await window.app.loadApiJson(api, "tiny-world");
  const g = window.app.graph;
  if (g.arrange) g.arrange(80);
  // Friendly names: App Mode shows the widget label, the graph shows the node title.
  const LABELS = {
    [INPUTS[0][0]]: ["Your photo", { image: "Your photo (a selfie, or the front of your place)" }],
    [INPUTS[3][0]]: ["Close-up photo 1", { image: "Close-up photo 1 (places only; skip for a selfie)" }],
    [INPUTS[4][0]]: ["Close-up photo 2", { image: "Close-up photo 2 (places only)" }],
    [INPUTS[5][0]]: ["Close-up photo 3", { image: "Close-up photo 3 (places only)" }],
    [INPUTS[8][0]]: ["Giant guest photo", { image: "Giant guest photo (your pet, kid or you)" }],
    [INPUTS[10][0]]: ["Your selfie", { image: "Your selfie (tiny me: your own face only)" }],
  };
  const WIDGET_LABELS = { template: "Template", name: "Name on screen", closeup_set: "Close-up style",
    endcard_line: "End card line (empty = template default)", ending: "Ending", music: "Music",
    auto_shape: "Auto-pick building / product shape", hook_text: "Hook text (optional, first second)", style: "Miniature style", intro: "Intro", giant_guest: "Giant guest (places only)", tiny_me: "Tiny me (your selfie as a figurine)", tiny_to_real: "Tiny to real (morph or zoom cut)", figure: "Figure style (selfie: painted figurine or plushie)", motion: "Motion (stop-motion = handmade feel)", bobble: "Bobblehead wobble (selfie)", look: "Look", glow_up: "Glow-up (make the real part aesthetic)", glow_closeups: "Glow-up the close-ups too", extra_details: "Extra details (optional)", credit: "Credit on end card", enabled: "Read the photo (better likeness)", seed: "Miniature seed (change to re-roll)" };
  for (const node of g.nodes) {
    const l = LABELS[String(node.id)];
    if (l) node.title = l[0];
    for (const w of node.widgets || []) {
      const lab = (l && l[1][w.name]) || (INPUTS.some(([n, name]) => String(n) === String(node.id) && name === w.name) && WIDGET_LABELS[w.name]);
      if (lab) { w.label = lab; for (const inp of node.inputs || []) if (inp.widget && inp.widget.name === w.name) inp.label = lab; }
    }
  }
  const w = g.serialize();
  w.extra = w.extra || {};
  w.extra.linearMode = true;
  w.extra.linearData = { inputs: INPUTS.map(([n, name]) => [Number(n), name]), outputs: OUTPUTS.map(Number) };
  return w;
}, { api, INPUTS, OUTPUTS });
const missing = INPUTS.filter(([n, name]) => {
  const node = wf.nodes.find((x) => x.id === Number(n));
  return !node;
});
console.log(`nodes ${wf.nodes.length}, links ${wf.links.length}, missing app inputs ${JSON.stringify(missing)}`);
fs.writeFileSync(outPath, JSON.stringify(wf, null, 1));
// Reload the saved file the way a user would open it, then screenshot graph + app view.
await page.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "tiny-world"); }, wf);
await page.waitForTimeout(4000);
await page.screenshot({ path: `${shot}-1.png` });
const nodesNow = await page.evaluate(() => window.app.graph.nodes.length);
console.log("reloaded nodes", nodesNow);
await browser.close();
