"""Tiny World: one owner photo -> finished 9:16 video, every stage in order, with a receipt.
python3 tools/run.py --template storefront --photo shop.jpg --name "Shop Name" --vibe lofi --out runs/<date>/<slug>
Stages: 0 intake + shop facts -> 4 keyframe (step B on the template's step-A keyframe) -> 5 fly-through -> 6 reveal
-> 7 ending (close-ups + end card, default) -> 8 final cut.
Ending close-ups: --closeup-photos a b c (real subjects: always the owner's photos) or --demo (generated, fictional subjects only).
Film/reveal run on a GPU-decode ComfyUI at :8477 (started here if not running; Mac only, see docs/LESSONS.md).
8477 is Tiny World's own port: other Studio jobs use 8477, and we only ever stop the server process we started."""
import argparse, hashlib, json, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
VENV_PY = str(Path.home() / "ComfyUI/venv/bin/python")
ap = argparse.ArgumentParser()
TEMPLATES = sorted(d.name for d in (ROOT / "templates").iterdir() if (d / "template.json").exists() and (d / "keyframe_A.png").exists())
ap.add_argument("--template", required=True, choices=TEMPLATES)
ap.add_argument("--photo", required=True); ap.add_argument("--name", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--vibe", required=True, choices=["cozy-acoustic", "lofi", "music-box"])
ap.add_argument("--allow-small", action="store_true", help="demo only: continue when intake fails on size alone")
ap.add_argument("--no-facts", action="store_true")
ap.add_argument("--ending", choices=["closeups", "short"], default="closeups", help="short = end on the reveal")
ap.add_argument("--closeups", help="close-up set in templates/closeups (default: the template's own)")
ap.add_argument("--closeup-photos", nargs="*", default=[]); ap.add_argument("--demo", action="store_true")
ap.add_argument("--line", help="end card line (default: the template's endcard_line)")
ap.add_argument("--auto-shape", action="store_true", help="pick the closest clay shape in the template's family from the photo facts")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
tdir = ROOT / "templates" / a.template
tpl = json.loads((tdir / "template.json").read_text())
cu_kind = a.closeups or tpl.get("closeups")
if a.ending == "closeups":
    if not cu_kind: sys.exit("this template has no close-up set: pass --closeups <kind> or --ending short")
    if not a.closeup_photos and not a.demo: sys.exit("close-ups need the owner's photos (--closeup-photos a b c); --demo only for fictional subjects")
receipt = {"template": a.template, "photo": a.photo, "name": a.name, "vibe": a.vibe, "stages": {}, "started": time.strftime("%Y-%m-%d %H:%M:%S")}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
def stage(name, cmd, **kw):
    t0 = time.time(); print(f"[{time.strftime('%H:%M:%S')}] {name}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
    receipt["stages"][name] = {"seconds": round(time.time() - t0), "exit": r.returncode, "tail": (r.stdout + r.stderr)[-600:]}
    save(); return r
def save(): (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
def newest(d, pat): return sorted(Path(d).glob(pat), key=lambda p: p.stat().st_mtime)[-1]
def up(port):
    try: urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=3); return True
    except Exception: return False

receipt["inputs"] = {"photo_sha": sha(a.photo), "template_json_sha": sha(tdir / "template.json"),
                     "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}
# Stage 0: intake (Gate A) + shop facts
r = stage("0_intake", [VENV_PY, "tools/intake.py", "--hero", a.photo, "--out", str(out / "intake.json")])
if r.returncode != 0:
    rep = json.loads((out / "intake.json").read_text())["hero"]
    only_size = all(x.startswith("Too small") for x in rep["reasons"])
    if not (a.allow_small and only_size):
        receipt["result"] = "STOPPED at Gate A: " + " ".join(rep["reasons"]); save(); sys.exit(receipt["result"])
extra = ""
if not a.no_facts:
    r = stage("0_facts", [VENV_PY, "tools/shop_facts.py", "--photo", a.photo, "--template", a.template, "--out", str(out / "shop_facts.json")])
    if r.returncode == 0:
        extra = "Features to copy from image 2: " + json.loads((out / "shop_facts.json").read_text()).get("copy_sentence", "")
receipt["facts_used"] = extra; save()
# Auto-pick: the vision model's facts choose the closest clay in the same family (same camera move, different building/product).
# Plain rules on the facts so the pick is explainable: storeys + roof for buildings, proportions for products.
def pick_shape(t, facts):
    txt = lambda k: json.dumps(facts.get(k, "")).lower()
    if t in ("storefront", "storefront-pitched2", "storefront-wide1"):
        if "1" in txt("storeys") or "one" in txt("storeys") or "single" in txt("storeys"): return "storefront-wide1"
        if any(w in txt("roof") for w in ("gable", "pitched", "hipped", "slope", "tile")): return "storefront-pitched2"
        return "storefront"
    if t in ("product-pedestal", "product-jar"):
        p = txt("shape") + txt("size_proportions")
        return "product-jar" if any(w in p for w in ("wider than", "short", "squat", "jar", "tin", "round and low")) else "product-pedestal"
    return t
if a.auto_shape and (out / "shop_facts.json").exists():
    picked = pick_shape(a.template, json.loads((out / "shop_facts.json").read_text()))
    receipt["shape_pick"] = {"asked": a.template, "picked": picked}; save()
    if picked != a.template:
        a.template = picked; tdir = ROOT / "templates" / picked; tpl = json.loads((tdir / "template.json").read_text())
        cu_kind = a.closeups or tpl.get("closeups"); receipt["template"] = picked
        receipt["inputs"]["template_json_sha"] = sha(tdir / "template.json"); save()
# Stage 4: keyframe step B
# Gate E (auto): keyframe B must keep step A's layout (edge correlation >= 0.6), else re-roll seed 8, then 9.
best = None
for seed in (7, 8, 9):
    r = stage(f"4_keyframe_s{seed}", [PY, "tools/keyframe.py", "--template", a.template, "--base", str(tdir / "keyframe_A.png"),
              "--photo", a.photo, "--seed", str(seed), "--out", str(out / "keyframe")] + (["--extra", extra] if extra else []))
    if r.returncode != 0: receipt["result"] = "FAILED at keyframe"; save(); sys.exit(1)
    cand = newest(out / "keyframe", "*.png")
    g = subprocess.run([VENV_PY, "tools/layout_check.py", str(tdir / "keyframe_A.png"), str(cand), "--min", "0.6"], cwd=ROOT,
                       capture_output=True, text=True)
    score = float(g.stdout.split()[-1]); receipt.setdefault("gate_e", []).append({"seed": seed, "file": cand.name, "layout": score}); save()
    if best is None or score > best[1]: best = (cand, score)
    if g.returncode == 0: break
kf = best[0]
if best[1] < 0.6: receipt["flag"] = f"Gate E: best layout {best[1]:.2f} < 0.6, needs a person to look"
# Stages 5-6 on the GPU-decode ComfyUI
started = False
if not up(8477):
    t = ROOT / "runs/gpu-vae-test"
    server = subprocess.Popen(["venv/bin/python", "main.py", "--listen", "127.0.0.1", "--port", "8477", "--disable-auto-launch", "--bf16-unet",
                      "--user-directory", str(t / "user"), "--output-directory", str(t / "out"), "--temp-directory", str(t / "tmp")],
                     cwd=Path.home() / "ComfyUI", stdout=open(t / "server.log", "a"), stderr=subprocess.STDOUT)
    started = True
    for _ in range(60):
        time.sleep(5)
        if up(8477): break
try:
    r = stage("5_film", [PY, "tools/film.py", "--template", a.template, "--keyframe", str(kf), "--port", "8477", "--out", str(out / "film")])
    if r.returncode != 0: receipt["result"] = "FAILED at film"; save(); sys.exit(1)
    r = stage("6_reveal", [PY, "tools/reveal.py", "--template", a.template, "--photo", a.photo, "--port", "8477", "--out", str(out / "reveal")])
    if r.returncode != 0: receipt["result"] = "FAILED at reveal"; save(); sys.exit(1)
    if a.ending == "closeups":
        r = stage("7_closeups", [PY, "tools/closeups.py", "--kind", cu_kind, "--out", str(out / "closeups"), "--hero", a.photo] +
                  (["--photos"] + a.closeup_photos if a.closeup_photos else []))
        if r.returncode != 0: receipt["result"] = "FAILED at close-ups"; save(); sys.exit(1)
finally:
    if started: server.terminate(); server.wait(timeout=60)
# Stage 8: final cut
final = out / "final.mp4"
rev = newest(out / "reveal", "reveal_*.mp4"); extra = []
if a.ending == "closeups":
    shots = [x["id"] for x in json.loads((ROOT / "templates/closeups" / f"{cu_kind}.json").read_text())["shots"]]
    r = stage("7_tail", ["tools/tail.sh", str(rev)] + [str(newest(out / "closeups" / i, "closeup_*.mp4")) for i in shots] +
              [a.name, a.line or tpl.get("endcard_line", "Visit us today"), str(out / "tail.mp4")])
    if r.returncode != 0: receipt["result"] = "FAILED at ending"; save(); sys.exit(1)
    rd = float(subprocess.run(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(rev)],
                              capture_output=True, text=True).stdout)
    rev, extra = out / "tail.mp4", [str(round(rd - 0.8, 2))]          # the title fades out before the close-ups
r = stage("8_assemble", ["tools/assemble.sh", str(newest(out / "film", "film_*.mp4")), str(rev),
                          a.name, str(final), str(ROOT / "templates/music" / f"{a.vibe}.mp3")] + extra)
receipt["result"] = "DONE" if r.returncode == 0 and final.exists() else "FAILED at assemble"
receipt["final"] = str(final); receipt["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); save()
print(receipt["result"], final)
