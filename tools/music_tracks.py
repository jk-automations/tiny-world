"""Trend-style music candidates: original instrumental tracks with ACE-Step v1 3.5B (Apache-2.0), one batch per style.
A human picks the keepers; they ship as templates/music/<id>.mp3 with their drop time in templates/music/tracks.json.
python3 tools/music_tracks.py --styles templates/music/candidates.json --out runs/x [--seconds 30] [--port 8477]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--styles", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=30.0); ap.add_argument("--port", type=int, default=8477)
ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
for st in json.loads(Path(a.styles).read_text()):
    for seed in a.seeds:
        g = {
            "ck": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ace_step_v1_3.5b.safetensors"}},
            "ms": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["ck", 0], "shift": 5.0}},
            "pos": {"class_type": "TextEncodeAceStepAudio", "inputs": {"clip": ["ck", 1], "tags": st["tags"], "lyrics": "[instrumental]", "lyrics_strength": 0.99}},
            "neg": {"class_type": "TextEncodeAceStepAudio", "inputs": {"clip": ["ck", 1], "tags": st.get("negative", "vocals, singing, speech, rap, distortion, noise, muddy mix"), "lyrics": "", "lyrics_strength": 0.99}},
            "lat": {"class_type": "EmptyAceStepLatentAudio", "inputs": {"seconds": a.seconds, "batch_size": 1}},
            "ks": {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
                   "seed": seed, "steps": 50, "cfg": 5.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
            "dec": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["ks", 0], "vae": ["ck", 2]}},
            "save": {"class_type": "SaveAudioMP3", "inputs": {"audio": ["dec", 0], "filename_prefix": f"tinyworld/track_{st['id']}_s{seed}", "quality": "V0"}},
        }
        print(st["id"], seed, flush=True)
        comfy.run(g, a.out)
