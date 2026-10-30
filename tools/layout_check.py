"""Gate E layout check: does keyframe B keep step A's layout? Edge-map correlation at 72x128 after blur.
Prints the score; exit 1 if below --min."""
import argparse, sys
import numpy as np
from PIL import Image, ImageFilter
p = argparse.ArgumentParser(); p.add_argument("a"); p.add_argument("b"); p.add_argument("--min", type=float, default=0.5)
a = p.parse_args()
def edges(f):
    g = Image.open(f).convert("L").resize((144, 256)).filter(ImageFilter.GaussianBlur(2))
    x = np.asarray(g, float); gx = np.abs(np.diff(x, axis=1))[:-1]; gy = np.abs(np.diff(x, axis=0))[:, :-1]
    e = np.asarray(Image.fromarray((gx + gy).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), float)
    return (e - e.mean()) / (e.std() + 1e-6)
s = float((edges(a.a) * edges(a.b)).mean())
print(f"layout {s:.3f}")
sys.exit(0 if s >= a.min else 1)
