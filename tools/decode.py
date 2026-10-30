"""Decode a saved Tiny World latent to MP4 (redo a slow/failed decode without re-rendering).
python3 tools/decode.py --latent tinyworld/latent_storefront_00001_.latent --out runs/x [--port 8188]"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--latent", required=True, help="path relative to ComfyUI/output, copied into input/")
ap.add_argument("--out", required=True); ap.add_argument("--port", type=int, default=8188); ap.add_argument("--fps", type=float, default=24)
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
g = {
    "vvae": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
    "lat": {"class_type": "LoadLatent", "inputs": {"latent": Path(a.latent).name}},
    "dec": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["lat", 0], "vae": ["vvae", 0], "tile_size": 512, "overlap": 64, "temporal_size": 128, "temporal_overlap": 32}},
    "save": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["dec", 0], "frame_rate": a.fps, "loop_count": 0, "filename_prefix": "tinyworld/decoded",
             "format": "video/h264-mp4", "pingpong": False, "save_output": True, "pix_fmt": "yuv420p", "crf": 17, "save_metadata": False, "trim_to_audio": False}},
}
comfy.run(g, a.out)
