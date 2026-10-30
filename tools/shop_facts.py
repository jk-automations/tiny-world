"""Stage 0 shop facts: a local vision model reads the owner's hero photo and returns the visible features as JSON.
The 'copy_sentence' is appended to the keyframe restyle prompt so likeness doesn't depend on the image model noticing details.
python3 tools/shop_facts.py --photo shop.jpg --out runs/x/shop_facts.json [--template storefront]
Default endpoint: a local Ollama with a vision model (ollama pull qwen2.5vl:7b). Any OpenAI-compatible vision endpoint works."""
import argparse, base64, io, json, re, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--photo", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--template", default="storefront"); ap.add_argument("--endpoint", default="http://127.0.0.1:11434/v1/chat/completions")
ap.add_argument("--model", default="default"); ap.add_argument("--timeout", type=int, default=900)
a = ap.parse_args()

try:
    from PIL import Image
    im = Image.open(a.photo).convert("RGB"); im.thumbnail((1024, 1024))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90); data = buf.getvalue()
except ImportError:
    data = Path(a.photo).read_bytes()
img = "data:image/jpeg;base64," + base64.b64encode(data).decode()

FIELDS = {
    "storefront": "shop_type, storeys, facade (color + material), roof (shape, color, chimneys), upper_windows, sign (shape, color, border, lettering color; do NOT repeat the words), awning (color, pattern), shop_windows (what is displayed), door (color, style), pavement_items, neighbours",
    "product-pedestal": "product_type, shape, size_proportions, main_colors, materials_finish, label (layout, colors; do NOT repeat brand words), cap_or_lid, distinctive_details",
    "house": "storeys, walls (color + material), roof (shape, color, chimneys), windows (count, frame color), front_door (color, style), porch, front_garden, fence",
    "car": "body_type, paint_color, finish, wheels (rim color, style), lights, trim, distinctive_details (never the license plate or brand words)",
    "room": "wall_colors, desk, monitors (count, size), keyboard, pc (case, RGB colors), chair, lighting (color, type), bed, decor, plants",
}[json.loads((Path(__file__).resolve().parent.parent / "templates" / a.template / "template.json").read_text()).get("facts", a.template)]
prompt = (f"Look at this photo and list only what is clearly visible. Return JSON with these keys: {FIELDS}, "
          "and copy_sentence: one sentence (max 70 words) listing the visible features an artist must copy to build a "
          "miniature model of it. Describe only the building or product itself: never the surface it sits on, the background, the lighting, the camera or the photo style. Never include any brand name, shop name or written words from signs or labels. Return only JSON.")
body = {"model": a.model, "temperature": 0, "max_tokens": 900,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img}}]}]}
req = urllib.request.Request(a.endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"})
raw = json.load(urllib.request.urlopen(req, timeout=a.timeout))
text = raw["choices"][0]["message"]["content"]
m = re.search(r"\{.*\}", text, re.S)
facts = json.loads(m.group(0)) if m else {"error": "no JSON in reply", "raw": text}
facts["_model"] = raw.get("model"); facts["_photo"] = a.photo
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(facts, indent=2))
print(json.dumps(facts, indent=2))
