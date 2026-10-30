"""Glow-up: one Qwen-Image-Edit pass that turns an everyday phone photo of your own place into an aesthetic photo of the
same place (tidy, relit, graded) before Tiny World uses it, so the tiny version and the real reveal both get the upgrade.
Keeps every object: it changes light, mess and grade, never what you own.
python3 tools/glowup.py --photo setup.jpg --look night --out runs/x/glow [--seed 7] [--port 8477]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy
from PIL import Image

root = Path(__file__).resolve().parent.parent
LOOKS = json.loads((root / "templates" / "glowup.json").read_text())
ap = argparse.ArgumentParser()
ap.add_argument("--photo", required=True); ap.add_argument("--look", default="night", choices=list(LOOKS))
ap.add_argument("--out", required=True); ap.add_argument("--port", type=int, default=8477); ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--closeup", action="store_true", help="use the look's close-up prompt")
ap.add_argument("--fast", action="store_true", help="Lightning 4-step LoRA: about 5x faster")
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
w, h = Image.open(a.photo).size
s = (1024 * 1024 / (w * h)) ** 0.5                      # about 1 MP, same aspect as the photo, multiples of 16
W, H = int(w * s) // 16 * 16, int(h * s) // 16 * 16
L = LOOKS[a.look]
if a.closeup: L = {"prompt": L.get("closeup_prompt", L["prompt"]), "negative": L.get("closeup_negative", L["negative"])}
g = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_bf16.safetensors", "weight_dtype": "default"}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
    "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    "lora": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1.0}},
    "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["lora" if a.fast else "unet", 0], "shift": 3.1}},
    "img": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.photo)}},
    "sc": {"class_type": "ImageScale", "inputs": {"image": ["img", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "disabled"}},
    "lat": {"class_type": "VAEEncode", "inputs": {"pixels": ["sc", 0], "vae": ["vae", 0]}},
    "pos": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": L["prompt"], "vae": ["vae", 0], "image1": ["sc", 0]}},
    "neg": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": L["negative"], "vae": ["vae", 0], "image1": ["sc", 0]}},
    "ks": {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
           "seed": a.seed, "steps": 4 if a.fast else 20, "cfg": 1.0 if a.fast else 2.5, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
    "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
    "save": {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": f"tinyworld/glow_{a.look}{'_fast' if a.fast else ''}{'_cu' if a.closeup else ''}_s{a.seed}"}},
}
comfy.run(g, out)
print("glow", sorted(out.glob(f"glow_{a.look}{'_fast' if a.fast else ''}{'_cu' if a.closeup else ''}_s{a.seed}_*.png"))[-1], flush=True)
