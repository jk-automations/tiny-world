"""Close-ups for the ending: 3 slow-motion hero moments inside the shop (WORKFLOW Stage 6b).
Stills: the owner's own photos (--photos, real shops) or, for demo shops only, text-to-image from templates/closeups/<kind>.json.
Clips: each still -> LTX image-to-video with the shot's motion prompt (tools/reveal.py), needs the :8477 ComfyUI.
Demo close-ups for things you own (car, room, house: "from_photo" in the set) are cut from the main photo with
Qwen-Image-Edit ("an extreme close-up of the wheel of THIS car"), so they show the same car, room or house.
python3 tools/closeups.py --kind boba --out runs/x/closeups [--photos a.jpg b.jpg c.jpg] [--desc "colors of this shop"] [--hero photo.jpg]"""
import argparse, json, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--kind", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--photos", nargs="*", default=[]); ap.add_argument("--desc", default="")
ap.add_argument("--hero", help="the main photo (used by sets with from_photo)")
ap.add_argument("--seconds", type=float, default=1.5)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
spec = json.loads((root / "templates/closeups" / f"{a.kind}.json").read_text())
newest = lambda d, pat: max(Path(d).glob(pat), key=lambda p: p.stat().st_mtime)
for n, shot in enumerate(spec["shots"]):
    if n < len(a.photos):
        still = a.photos[n]                                   # real shop: always the owner's photo
    else:
        if a.photos: sys.exit(f"real shop needs {len(spec['shots'])} owner photos; generated close-ups are demo only")
        s = dict(spec, shop_description=a.desc, shots=[shot])
        hero = root / "templates/storefront/first_frame.png"
        if spec.get("from_photo") and a.hero:
            hero = a.hero
            s = dict(spec, shared_prefix="Image 1 is a real photo. Make a new photo of a detail of the exact same subject from image 1, "
                     "with the same colors, materials and finish:", shots=[dict(shot, mode="edit")])
        (out / f"{shot['id']}.json").write_text(json.dumps(s))
        subprocess.run([sys.executable, "tools/refs.py", "--hero", str(hero),
                        "--shots", str(out / f"{shot['id']}.json"), "--out", str(out / shot["id"])], cwd=root, check=True)
        still = str(newest(out / shot["id"], "*.png"))
    subprocess.run([sys.executable, "tools/reveal.py", "--photo", still, "--prompt", shot["motion"], "--seconds", str(a.seconds),
                    "--prefix", f"tinyworld/closeup_{shot['id']}", "--out", str(out / shot["id"])], cwd=root, check=True)
print("done", [str(newest(out / s["id"], "closeup_*.mp4")) for s in spec["shots"]])
