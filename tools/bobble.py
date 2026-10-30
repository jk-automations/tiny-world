"""Bobblehead wobble: the figurine's head springs on its neck like a tapped toy; the body and the world stay still.
Deterministic (OpenCV), no GPU: cut the head out (GrabCut in a box), fill the background behind it, then rock the head
around its neck with a damped spring while the camera pushes in a little.
python3 tools/bobble.py --still keyframe.png --box 0.28,0.015,0.67,0.25 --out bobble.mp4 [--seconds 2.5]
--box = head x0,y0,x1,y1 as fractions of the image (the neck is the bottom middle). Without --box OpenCV's face detector finds
it; if that fails and TINYWORLD_VISION_ENDPOINT is set (an OpenAI-style vision chat URL), the vision model is asked."""
import argparse, base64, json, math, os, re, shutil, subprocess, sys, urllib.request
import cv2, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--still", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--box"); ap.add_argument("--seconds", type=float, default=2.5); ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--angle", type=float, default=11.0, help="first swing, degrees")
ap.add_argument("--hz", type=float, default=2.6, help="wobbles per second")
ap.add_argument("--settle", type=float, default=1.1, help="seconds for the wobble to die down to about a third")
ap.add_argument("--push", type=float, default=0.05, help="camera push-in over the clip")
a = ap.parse_args()


img = cv2.imread(a.still)
H, W = img.shape[:2]


def find_head(path):
    """Ask the local vision model for the figurine's head box."""
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    q = ("This is a photo of a toy figurine on a pedestal. Give the bounding box of the figurine's HEAD including all of its "
         "hair (stop at the chin/neck, not the shoulders) as integers from 0 to 1000 relative to the image width and height. "
         'Answer only JSON: {"x0":..,"y0":..,"x1":..,"y1":..}')
    body = {"model": os.environ.get("TINYWORLD_VISION_MODEL", "default"), "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]}
    url = os.environ.get("TINYWORLD_VISION_ENDPOINT")
    if not url:
        sys.exit("no face found in the still (set TINYWORLD_VISION_ENDPOINT to ask a vision model, or pass --box)")
    r = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    txt = json.load(urllib.request.urlopen(r, timeout=300))["choices"][0]["message"]["content"]
    bb = re.search(r'bbox_2d"?\s*:\s*\[([^\]]+)\]', txt)  # Qwen-VL answers in its own grounding format
    if bb:
        v = [float(x) for x in bb.group(1).split(",")]
    else:
        d = {k: float(x) for k, x in re.findall(r'"?(x0|y0|x1|y1)"?\s*:\s*(-?[\d.]+)', txt)}
        v = [d[k] for k in ("x0", "y0", "x1", "y1")]
    print("vision head box", v, flush=True)
    if max(v) > 1.5:  # asked for 0..1000
        v = [x / 1000 for x in v]
    px, py = 0.3 * (v[2] - v[0]), 0.03 * (v[3] - v[1])  # its boxes run narrow; GrabCut trims the extra
    v = [v[0] - px, v[1] - py, v[2] + px, v[3] + py]
    return [min(1.0, max(0.0, x)) for x in v]


face = None


def face_head():
    """Find the figurine's face with OpenCV's face detector, then grow the box to take in the hair. None if no face."""
    if not hasattr(cv2, "CascadeClassifier"):   # OpenCV 5 moved the classic face detector out
        print("[bobble] this OpenCV has no face detector: pip install \"opencv-python-headless<5\"", flush=True); return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fs = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(g, 1.1, 4, minSize=(W // 12, W // 12))
    fs = [f for f in fs if f[1] < H * 0.6]
    if not len(fs):
        return None
    global face
    face = fx, fy, fw, fh = max(fs, key=lambda f: f[2] * f[3])
    return [(fx - 0.6 * fw) / W, (fy - 0.6 * fh) / H, (fx + 1.35 * fw) / W, (fy + 1.12 * fh) / H]


box = [float(v) for v in a.box.split(",")] if a.box else (face_head() or find_head(a.still))
x0, y0, x1, y1 = [min(1.0, max(0.0, v)) for v in box]
bx = [int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)]
print("head box px", bx, flush=True)

# head mask: GrabCut from a slightly bigger rect, then keep the biggest blob, feather the edge
pad = 6
rect = (max(0, bx[0] - pad), max(0, bx[1] - pad), min(W, bx[2] + pad) - max(0, bx[0] - pad), min(H, bx[3] + pad) - max(0, bx[1] - pad))
gc = np.zeros((H, W), np.uint8)
cv2.grabCut(img, gc, rect, np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_RECT)
m = np.where((gc == 1) | (gc == 3), 255, 0).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
if n > 1:
    m = np.where(lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
# GrabCut loses dark hair against a dark background: fill in its convex hull, and always keep the whole face
cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if cs:
    cv2.fillPoly(m, [cv2.convexHull(np.vstack(cs))], 255)
if face is not None:
    fx, fy, fw, fh = face
    cv2.ellipse(m, (int(fx + fw / 2), int(fy + 0.42 * fh)), (int(0.55 * fw), int(0.62 * fh)), 0, 0, 360, 255, -1)
cv2.imwrite(a.out.rsplit(".", 1)[0] + "_mask.png", m)

# background plate: fill where the head was, so the swing never shows a second head
plate = cv2.inpaint(img, cv2.dilate(m, np.ones((15, 15), np.uint8)), 9, cv2.INPAINT_TELEA)
plate = np.where(cv2.dilate(m, np.ones((15, 15), np.uint8))[..., None] > 0, cv2.GaussianBlur(plate, (31, 31), 0), img)
alpha = cv2.GaussianBlur(m, (5, 5), 0).astype(np.float32)[..., None] / 255
pivot = ((bx[0] + bx[2]) / 2, bx[3] - 0.04 * (bx[3] - bx[1]))  # the spring sits at the bottom middle of the head

ff = subprocess.Popen([os.environ.get("TINYWORLD_FFMPEG") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                       "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
N = int(a.seconds * a.fps)
for i in range(N):
    t = i / a.fps
    k = math.exp(-t / a.settle)
    ang = a.angle * k * math.sin(2 * math.pi * a.hz * t + 0.6)                  # side-to-side rock
    dy = 0.035 * (bx[3] - bx[1]) * k * math.sin(2 * math.pi * a.hz * 2 * t)     # little up-down bounce, twice as fast
    R = cv2.getRotationMatrix2D(pivot, ang, 1.0); R[1, 2] += dy
    head = cv2.warpAffine(img, R, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    al = cv2.warpAffine(alpha, R, (W, H), flags=cv2.INTER_LINEAR)[..., None]
    f = (head * al + plate * (1 - al)).astype(np.uint8)
    s = 1 + a.push * (t / a.seconds)                                          # slow push-in so the frame is alive
    f = cv2.warpAffine(f, cv2.getRotationMatrix2D((W / 2, H * 0.4), 0, s), (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    ff.stdin.write(f.tobytes())
ff.stdin.close(); ff.wait()
print("bobble", a.out, flush=True)
