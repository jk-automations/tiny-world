"""Fun-layer beats on top of a finished tiny world: collector box / snow globe intro, giant guest (pet / kid / you), tiny-me
figurine. Each beat = one Qwen-Image-Edit composite from the chosen miniature (+ an optional photo) -> one short LTX clip.
The fly-through is not re-rendered.
python3 tools/beats.py --beat box --miniature mini.png --out runs/x/beats [--photo pet.jpg] [--port 8477] [--seed 7]"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

root = Path(__file__).resolve().parent.parent
BEATS = json.loads((root / "templates" / "beats.json").read_text())
ap = argparse.ArgumentParser()
ap.add_argument("--beat", required=True, choices=list(BEATS)); ap.add_argument("--miniature", required=True)
ap.add_argument("--photo"); ap.add_argument("--out", required=True); ap.add_argument("--port", type=int, default=8477)
ap.add_argument("--seed", type=int, default=7); ap.add_argument("--seconds", type=float, default=2.5)
ap.add_argument("--skip-clip", action="store_true")
ap.add_argument("--fast", action="store_true", help="Lightning 4-step LoRA for the still: about 5x faster")
ap.add_argument("--clip-from", help="skip the still: animate this image with the beat's motion")
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
b = BEATS[a.beat]
if b.get("needs_photo") and not a.photo and not a.clip_from:
    sys.exit(f"the {a.beat} beat needs --photo ({b['needs_photo']})")
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
g = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_bf16.safetensors", "weight_dtype": "default"}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
    "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
    "mini": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.miniature)}},
    "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 576, "height": 1024, "batch_size": 1}},
}
imgs = {"image1": ["mini", 0]}
if a.photo:
    g["photo"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.photo)}}; imgs["image2"] = ["photo", 0]
g["pos"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": b["still"], "vae": ["vae", 0], **imgs}}
neg = b.get("negative", "text, letters, logo, watermark, cartoon, blurry, low quality, deformed, extra limbs")
g["neg"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": neg, "vae": ["vae", 0], **imgs}}
g["ks"] = {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
           "seed": a.seed, "steps": 20, "cfg": 2.5, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": f"tinyworld/beat_{a.beat}_s{a.seed}"}}
if a.fast:
    g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1.0}}
    g["ms"]["inputs"]["model"] = ["lora", 0]; g["ks"]["inputs"].update(steps=4, cfg=1.0)
if a.clip_from:
    still = Path(a.clip_from)
else:
    comfy.run(g, out)
    still = sorted(out.glob(f"beat_{a.beat}_s{a.seed}_*.png"))[-1]
print("still", still, flush=True)
if not a.skip_clip:
    subprocess.run([sys.executable, str(root / "tools/reveal.py"), "--photo", str(still), "--prompt", b["motion"], "--seconds", str(a.seconds),
                    "--port", str(a.port), "--prefix", f"tinyworld/beat_{a.beat}", "--out", str(out)], check=True)
