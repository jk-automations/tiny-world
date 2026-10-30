"""Shop reference pack ("shop sheet"): consistent extra views of ONE shop, generated from the owner's hero photo
Each shot has a mode:
  edit  = same viewpoint, new look (evening, relight)      Qwen-Image-Edit-2511
  angle = new camera angle on what the photo shows          Qwen-Image-Edit-2511 + Multiple-Angles LoRA ("<sks> ...")
  t2i   = a space the photo never shows (interior)          Qwen-Image-2512 text-to-image. DEMO ONLY: for a real shop,
          unseen spaces come from the owner's photos, never generated (the ad must match the real shop).
python3 tools/refs.py --hero shop.png --shots templates/storefront/ref_shots.json --out runs/x [--extra a.jpg b.jpg]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--hero", required=True); ap.add_argument("--shots", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--extra", nargs="*", default=[]); ap.add_argument("--only", nargs="*", help="shot ids to run")
ap.add_argument("--steps", type=int, default=20)
a = ap.parse_args()
spec = json.loads(Path(a.shots).read_text())
hero = comfy.upload(a.hero); extras = [comfy.upload(p) for p in a.extra[:2]]
def t2i(shot):
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2512_bf16.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
        "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": shot.get("width", 768), "height": shot.get("height", 1344), "batch_size": 1}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": spec["shop_description"] + " " + shot["prompt"] + " " + spec["shared_suffix"]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": spec["negative"]}},
    }

for shot in spec["shots"]:
    if a.only and shot["id"] not in a.only: continue
    mode = shot.get("mode", "edit")
    if mode == "t2i":
        g = t2i(shot)
        g["ks"] = {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
                   "seed": shot.get("seed", 7), "steps": a.steps, "cfg": 2.5, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
        g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
        g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": f"tinyworld/ref_{shot['id']}"}}
        print(shot["id"], mode, flush=True); comfy.run(g, a.out); continue
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_bf16.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
        "i1": {"class_type": "LoadImage", "inputs": {"image": hero}},
        "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": shot.get("width", 768), "height": shot.get("height", 1344), "batch_size": 1}},
    }
    imgs = {"image1": ["i1", 0]}
    for k, name in enumerate(extras, start=2):
        g[f"i{k}"] = {"class_type": "LoadImage", "inputs": {"image": name}}; imgs[f"image{k}"] = [f"i{k}", 0]
    if mode == "angle":
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "qwen-image-edit-2511-multiple-angles-lora.safetensors", "strength_model": 1.0}}
        g["ms"]["inputs"]["model"] = ["lora", 0]
        text = shot["prompt"]
    else:
        text = spec["shared_prefix"] + " " + shot["prompt"] + " " + spec["shared_suffix"]
    g["pos"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": text, "vae": ["vae", 0], **imgs}}
    g["neg"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": spec["negative"], "vae": ["vae", 0], **imgs}}
    g["ks"] = {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
               "seed": shot.get("seed", 7), "steps": a.steps, "cfg": 2.5, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": f"tinyworld/ref_{shot['id']}"}}
    print(shot["id"], mode, flush=True)
    comfy.run(g, a.out)
