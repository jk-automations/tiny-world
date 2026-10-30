"""Run the one-graph app end to end through the ComfyUI API (proof that the published workflow really works).
python3 tools/test_app.py --photo shop.png --closeups a.png b.png c.png --name "Fern & Petal" --out runs/x [--template storefront]"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--photo", required=True); ap.add_argument("--closeups", nargs=3, required=True)
ap.add_argument("--name", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--template", default="storefront"); ap.add_argument("--closeup-set", default="match my photos")
ap.add_argument("--music", default="cozy-acoustic"); ap.add_argument("--hook", default=""); ap.add_argument("--object", action="store_true"); ap.add_argument("--intro", default="none"); ap.add_argument("--glow-up", default="off"); ap.add_argument("--scene", default="town square (any object)")
ap.add_argument("--vision-endpoint", default="http://127.0.0.1:11434/v1/chat/completions"); ap.add_argument("--vision-model", default="qwen2.5vl:7b"); ap.add_argument("--port", type=int, default=8477)
ap.add_argument("--guest-photo"); ap.add_argument("--me-photo")
ap.add_argument("--figure", default="painted figurine"); ap.add_argument("--motion", default="smooth"); ap.add_argument("--bobble", default="auto")
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
root = Path(__file__).resolve().parent.parent
up = [comfy.upload(p) for p in [a.photo, *a.closeups]]
extras = (["--giant-guest", "--guest-photo", comfy.upload(a.guest_photo)] if a.guest_photo else []) + (["--tiny-me", "--me-photo", comfy.upload(a.me_photo)] if a.me_photo else [])
api = root / "runs" / "app_test_api.json"
subprocess.run([sys.executable, str(root / "tools/build_app.py"), "--out", str(api), "--photo", up[0], "--closeups", *up[1:],
                "--template", a.template, "--name", a.name, "--closeup-set", a.closeup_set, "--music", a.music, "--hook", a.hook, "--vision-endpoint", a.vision_endpoint, "--vision-model", a.vision_model] + ["--intro", a.intro, "--glow-up", a.glow_up, "--figure", a.figure, "--motion", a.motion, "--bobble", a.bobble] + (["--object", "--scene", a.scene] if a.object else []) + extras, check=True)
comfy.run(json.loads(api.read_text()), a.out)
