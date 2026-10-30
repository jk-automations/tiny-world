"""Stage 0 intake checks (Gate A). CPU only, runs in seconds.
~/ComfyUI/venv/bin/python tools/intake.py --hero shop.jpg [--extra a.jpg b.jpg] --out runs/x/intake.json
Exit code 0 = hero passes; 1 = hero fails (reasons are written in plain words for the owner)."""
import argparse, json, sys
from pathlib import Path
import cv2, numpy as np

MIN_SHORT_SIDE = 1080      # px
MIN_SHARPNESS = 60.0       # Laplacian variance at 1024 px long side
MAX_CLIPPED = 0.08         # share of pixels that are pure black or pure white

def check(path):
    img = cv2.imread(str(path))
    if img is None:
        return {"file": str(path), "ok": False, "reasons": ["This file is not an image we can read."]}
    h, w = img.shape[:2]
    s = 1024 / max(h, w)
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    dark, bright = float((gray < 6).mean()), float((gray > 249).mean())
    # TODO: Haar gives false faces on busy shop windows (4 on a blurred bakery photo). Swap to YuNet or Florence2 OD.
    faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(gray, 1.1, 6, minSize=(24, 24))
    reasons = []
    if min(h, w) < MIN_SHORT_SIDE: reasons.append(f"Too small ({w}x{h}). Please send a photo at least {MIN_SHORT_SIDE} px on the short side.")
    if sharp < MIN_SHARPNESS: reasons.append("Looks blurry. Please hold the phone still or tap to focus.")
    if dark > MAX_CLIPPED: reasons.append("Too dark in places. Please shoot in daylight or turn the lights on.")
    if bright > MAX_CLIPPED: reasons.append("Too bright in places (washed out). Please avoid shooting into the sun.")
    return {"file": str(path), "ok": not reasons, "reasons": reasons, "size": [w, h], "sharpness": round(sharp, 1),
            "dark_share": round(dark, 3), "bright_share": round(bright, 3), "faces": len(faces),
            "face_boxes": [[int(v / s) for v in f] for f in faces]}

ap = argparse.ArgumentParser()
ap.add_argument("--hero", required=True); ap.add_argument("--extra", nargs="*", default=[]); ap.add_argument("--out", required=True)
a = ap.parse_args()
report = {"hero": check(a.hero), "extras": [check(p) for p in a.extra]}
report["note"] = "Faces found are blurred in Stage 1 and never sent to a generator." if report["hero"]["faces"] else ""
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(report, indent=2))
print(json.dumps(report["hero"]))
sys.exit(0 if report["hero"]["ok"] else 1)
