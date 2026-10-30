"""Make the miniature keyframe with Qwen-Image-Edit-2511. Two steps (2026-10-22 lesson: photo + clay in one pass lets the
photo overpower the layout):
  A. clay first frame -> generic diorama keyframe (layout locked)            keyframe.py --template t --out A
  B. diorama keyframe + owner photo -> same diorama, shop restyled to match  keyframe.py --template t --base A.png --photo shop.jpg --out B
python3 tools/keyframe.py --template storefront --out runs/x [--photo shop.jpg] [--seed 42]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--template", default="storefront"); ap.add_argument("--out", required=True)
ap.add_argument("--photo"); ap.add_argument("--seed", type=int); ap.add_argument("--steps", type=int, default=20)
ap.add_argument("--denoise", type=float, default=1.0)
ap.add_argument("--clay-frame", type=int, help="use this clay frame (1-based) instead of first_frame.png")
ap.add_argument("--base", help="step B: approved generic diorama keyframe used as image 1")
ap.add_argument("--ref", help="approved keyframe to copy the look from (mid keyframes)")
ap.add_argument("--extra", default="", help="text appended to the locked prompt (for tests)")
ap.add_argument("--prompt-key", help="template.json prompt to use instead of the automatic choice")
a = ap.parse_args()
root = Path(__file__).resolve().parent.parent
tpl = json.loads((root / "templates" / a.template / "template.json").read_text())
if a.seed is None: a.seed = tpl.get("keyframe_seed", 42)

g = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_bf16.safetensors", "weight_dtype": "default"}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
    "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    "clay": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.base or (root / "templates" / a.template / (f"clay_frames/f_{a.clay_frame:04d}.png" if a.clay_frame else "first_frame.png")))}},
    "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
    "lat": {"class_type": "VAEEncode", "inputs": {"pixels": ["clay", 0], "vae": ["vae", 0]}},
    "neg": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": tpl["keyframe_negative"], "vae": ["vae", 0], "image1": ["clay", 0]}},
}
prompt = (tpl[a.prompt_key] if a.prompt_key else tpl["keyframe_restyle_prompt"] if a.base and a.photo else tpl["mid_keyframe_prompt"] if a.ref else tpl["keyframe_prompt_photo"] if a.photo else tpl["keyframe_prompt"]) + (" " + a.extra if a.extra else "")
pos = {"clip": ["clip", 0], "prompt": prompt, "vae": ["vae", 0], "image1": ["clay", 0]}
second = a.ref or a.photo
if second:
    g["photo"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(second)}}
    pos["image2"] = ["photo", 0]; g["neg"]["inputs"]["image2"] = ["photo", 0]
g["pos"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": pos}
g["ks"] = {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
           "seed": a.seed, "steps": a.steps, "cfg": 2.5, "sampler_name": "euler", "scheduler": "simple", "denoise": a.denoise}}
g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": f"tinyworld/keyframe_{a.template}_{'B' if a.base else 'A'}_f{a.clay_frame or 1}_s{a.seed}"}}
comfy.run(g, a.out)
