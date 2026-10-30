"""Film the fly-through: template clay video + approved keyframe -> LTX-2.5 + Layout-To-Render IC-LoRA.
Mirrors Lightricks' two-stage distilled reference graph (8 + 3 steps, CFG 1, euler_ancestral).
python3 tools/film.py --template storefront --keyframe kf.png --out runs/x [--half]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--template", default="storefront"); ap.add_argument("--keyframe", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--mid", help="mid keyframe image (placed at template mid_keyframe_frame)")
ap.add_argument("--first", help="first-frame image (walk-in: the reveal's last frame)")
ap.add_argument("--port", type=int, default=8477, help="8477 = Tiny World GPU-decode ComfyUI")
ap.add_argument("--seed", type=int); ap.add_argument("--frames", type=int)
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
root = Path(__file__).resolve().parent.parent
tdir = root / "templates" / a.template
tpl = json.loads((tdir / "template.json").read_text())
W, H = tpl["width"], tpl["height"]
frames = a.frames or tpl["frames"]
seed = a.seed if a.seed is not None else tpl["film_seed"]

def guide(pos, neg, latent, image, idx, crop):
    return {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["vvae", 0], "latent": latent, "image": image,
            "frame_idx": idx, "strength": 1.0, "latent_downscale_factor": ["lora", 1], "crop": crop, "use_tiled_encode": False, "tile_size": 256, "tile_overlap": 64}}

def sampler(prefix, guided, sigmas):
    return {
        prefix + "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        prefix + "cfg": {"class_type": "CFGGuider", "inputs": {"model": ["lora", 0], "positive": [guided, 0], "negative": [guided, 1], "cfg": 1.0}},
        prefix + "ksel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        prefix + "sig": {"class_type": "ManualSigmas", "inputs": {"sigmas": sigmas}},
        prefix + "run": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [prefix + "noise", 0], "guider": [prefix + "cfg", 0], "sampler": [prefix + "ksel", 0],
                         "sigmas": [prefix + "sig", 0], "latent_image": [guided, 2]}},
        prefix + "crop": {"class_type": "LTXVCropGuides", "inputs": {"positive": [guided, 0], "negative": [guided, 1], "latent": [prefix + "run", 0]}},
    }

g = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.5-22b-distilled-transformer-bf16.safetensors", "weight_dtype": "default"}},
    "lora": {"class_type": "LTXICLoRALoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "ltx-2.5-22b-ic-lora-layout-to-render-1.0.safetensors", "strength_model": 1.0}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", "type": "ltxv", "device": "default"}},
    "vvae": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
    "ups": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}},
    "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": tpl["film_prompt"]}},
    "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": ""}},
    "cond": {"class_type": "LTXVConditioning", "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(tpl["fps"])}},
    "vid": {"class_type": "LoadVideo", "inputs": {"file": comfy.upload(tdir / "clay.mp4")}},
    "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
    "kf": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.keyframe)}},
    "lat1": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": W // 2, "height": H // 2, "length": frames, "batch_size": 1}},
}
g["g1"] = guide(["cond", 0], ["cond", 1], ["lat1", 0], ["comp", 0], 0, "disabled")
g["g2"] = guide(["g1", 0], ["g1", 1], ["g1", 2], ["kf", 0], -1, "center")
last1, last2 = "g2", "g4"
if a.mid:
    g["mid"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.mid)}}
    g["g2m"] = guide(["g2", 0], ["g2", 1], ["g2", 2], ["mid", 0], tpl["mid_keyframe_frame"], "center"); last1 = "g2m"
if a.first:
    g["first"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.first)}}
    g["g2f"] = guide([last1, 0], [last1, 1], [last1, 2], ["first", 0], 0, "center"); last1 = "g2f"
g.update(sampler("s1_", last1, "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"))
g["up"] = {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["s1_crop", 2], "upscale_model": ["ups", 0], "vae": ["vvae", 0]}}
g["g3"] = guide(["s1_crop", 0], ["s1_crop", 1], ["up", 0], ["comp", 0], 0, "disabled")
g["g4"] = guide(["g3", 0], ["g3", 1], ["g3", 2], ["kf", 0], -1, "center")
if a.mid:
    g["g4m"] = guide(["g4", 0], ["g4", 1], ["g4", 2], ["mid", 0], tpl["mid_keyframe_frame"], "center"); last2 = "g4m"
if a.first:
    g["g4f"] = guide([last2, 0], [last2, 1], [last2, 2], ["first", 0], 0, "center"); last2 = "g4f"
g.update(sampler("s2_", last2, "0.909375, 0.725, 0.421875, 0.0"))
# Save the final latent first so a slow or failed decode can be redone with tools/decode.py.
g["keep"] = {"class_type": "SaveLatent", "inputs": {"samples": ["s2_crop", 2], "filename_prefix": f"tinyworld/latent_{a.template}"}}
g["dec"] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["s2_crop", 2], "vae": ["vvae", 0], "tile_size": 512, "overlap": 64, "temporal_size": 128, "temporal_overlap": 32}}
g["save"] = {"class_type": "VHS_VideoCombine", "inputs": {"images": ["dec", 0], "frame_rate": float(tpl["fps"]), "loop_count": 0,
             "filename_prefix": f"tinyworld/film_{a.template}", "format": "video/h264-mp4", "pingpong": False, "save_output": True,
             "pix_fmt": "yuv420p", "crf": 17, "save_metadata": False, "trim_to_audio": False}}
comfy.run(g, a.out)
