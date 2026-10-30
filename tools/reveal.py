"""Reveal clip: the real (or demo) shop photo -> short realistic clip with ambient sound (LTX-2.5 image-to-video).
Used when the user gives only a photo; a user's own video clip can replace this step.
With --last it is the walk-in: first frame = --photo, last frame = --last (an interior photo), camera walks in through the door.
python3 tools/reveal.py --photo shop.png --out runs/x [--seconds 2.5] [--port 8477] [--last interior.png --prompt-key walkin_prompt]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--photo", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--template", default="storefront"); ap.add_argument("--seconds", type=float, default=2.5)
ap.add_argument("--port", type=int, default=8477); ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--last", help="last-frame image (walk-in)"); ap.add_argument("--prompt-key", default="reveal_prompt")
ap.add_argument("--prefix", default="tinyworld/reveal"); ap.add_argument("--last-strength", type=float, default=1.0)
ap.add_argument("--prompt", help="literal prompt (close-ups); overrides --prompt-key")
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
root = Path(__file__).resolve().parent.parent
tpl = json.loads((root / "templates" / a.template / "template.json").read_text())
W, H, FPS = tpl["width"], tpl["height"], tpl["fps"]
n = int(a.seconds * FPS)
frames = (n // 8) * 8 + 1
prompt = a.prompt or tpl.get(a.prompt_key, "Realistic handheld smartphone video of this exact storefront in daylight. The camera slowly pushes in toward the front door. A couple of people walk past on the sidewalk. Quiet morning street sounds, birds, distant traffic.")

g = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.5-22b-distilled-transformer-bf16.safetensors", "weight_dtype": "default"}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", "type": "ltxv", "device": "default"}},
    "vvae": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
    "avae": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
    "ups": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}},
    "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt}},
    "neg": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": "cartoon, miniature, low quality, warped, text artifacts"}},
    "cond": {"class_type": "LTXVConditioning", "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(FPS)}},
    "img": {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.photo)}},
    "img1": {"class_type": "ImageScale", "inputs": {"image": ["img", 0], "upscale_method": "lanczos", "width": W // 2, "height": H // 2, "crop": "center"}},
    "img2": {"class_type": "ImageScale", "inputs": {"image": ["img", 0], "upscale_method": "lanczos", "width": W, "height": H, "crop": "center"}},
    "vlat": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": W // 2, "height": H // 2, "length": frames, "batch_size": 1}},
    "vlat_i": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["vvae", 0], "image": ["img1", 0], "latent": ["vlat", 0], "strength": 1.0, "bypass": False}},
    "alat": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"audio_vae": ["avae", 0], "frames_number": frames, "frame_rate": FPS, "batch_size": 1}},
    "av1": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["vlat_i", 0], "audio_latent": ["alat", 0]}},
    "noise1": {"class_type": "RandomNoise", "inputs": {"noise_seed": a.seed}},
    "ksel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "sig1": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"}},
    "gd1": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["unet", 0], "positive": ["cond", 0], "negative": ["cond", 1], "video_cfg": 1, "audio_cfg": 1}},
    "s1": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise1", 0], "guider": ["gd1", 0], "sampler": ["ksel", 0], "sigmas": ["sig1", 0], "latent_image": ["av1", 0]}},
    "sep1": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["s1", 0]}},
    "up": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["sep1", 0], "upscale_model": ["ups", 0], "vae": ["vvae", 0]}},
    "up_i": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["vvae", 0], "image": ["img2", 0], "latent": ["up", 0], "strength": 1.0, "bypass": False}},
    "av2": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["up_i", 0], "audio_latent": ["sep1", 1]}},
    "noise2": {"class_type": "RandomNoise", "inputs": {"noise_seed": a.seed}},
    "sig2": {"class_type": "ManualSigmas", "inputs": {"sigmas": "0.85, 0.7250, 0.4219, 0.0"}},
    "gd2": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["unet", 0], "positive": ["cond", 0], "negative": ["cond", 1], "video_cfg": 1, "audio_cfg": 1}},
    "s2": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["noise2", 0], "guider": ["gd2", 0], "sampler": ["ksel", 0], "sigmas": ["sig2", 0], "latent_image": ["av2", 0]}},
    "sep2": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["s2", 0]}},
    "vdec": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["sep2", 0], "vae": ["vvae", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 16}},
    "adec": {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["sep2", 1], "audio_vae": ["avae", 0]}},
    "save": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["vdec", 0], "audio": ["adec", 0], "frame_rate": float(FPS), "loop_count": 0,
             "filename_prefix": a.prefix, "format": "video/h264-mp4", "pingpong": False, "save_output": True,
             "pix_fmt": "yuv420p", "crf": 17, "save_metadata": False, "trim_to_audio": False}},
}
if a.last:
    # Last-frame guide on the video latent in both stages; guides are cropped off after each sampler.
    g["last"] = {"class_type": "LoadImage", "inputs": {"image": comfy.upload(a.last)}}
    for k, w, h in (("1", W // 2, H // 2), ("2", W, H)):
        g["last" + k] = {"class_type": "ImageScale", "inputs": {"image": ["last", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}}
    g["lg1"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": ["cond", 0], "negative": ["cond", 1], "vae": ["vvae", 0], "latent": ["vlat_i", 0],
                "image": ["last1", 0], "frame_idx": -1, "strength": a.last_strength}}
    g["av1"]["inputs"]["video_latent"] = ["lg1", 2]
    g["gd1"]["inputs"].update(positive=["lg1", 0], negative=["lg1", 1])
    g["cr1"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": ["lg1", 0], "negative": ["lg1", 1], "latent": ["sep1", 0]}}
    g["up"]["inputs"]["samples"] = ["cr1", 2]
    g["lg2"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": ["cr1", 0], "negative": ["cr1", 1], "vae": ["vvae", 0], "latent": ["up_i", 0],
                "image": ["last2", 0], "frame_idx": -1, "strength": a.last_strength}}
    g["av2"]["inputs"]["video_latent"] = ["lg2", 2]
    g["gd2"]["inputs"].update(positive=["lg2", 0], negative=["lg2", 1])
    g["cr2"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": ["lg2", 0], "negative": ["lg2", 1], "latent": ["sep2", 0]}}
    g["vdec"]["inputs"]["samples"] = ["cr2", 2]
comfy.run(g, a.out)
