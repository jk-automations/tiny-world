"""Template music: original instrumental tracks with ACE-Step v1 3.5B (Apache-2.0).
Generated ONCE per template, a human picks one, it ships as templates/<t>/music.mp3.
python3 tools/music.py --template storefront --out runs/x [--seconds 15]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comfy

ap = argparse.ArgumentParser()
ap.add_argument("--template", default="storefront"); ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=15.0); ap.add_argument("--port", type=int, default=8188)
a = ap.parse_args()
comfy.BASE = f"http://127.0.0.1:{a.port}"
root = Path(__file__).resolve().parent.parent
tpl = json.loads((root / "templates" / a.template / "template.json").read_text())
for c in tpl["music_candidates"]:
    g = {
        "ck": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ace_step_v1_3.5b.safetensors"}},
        "ms": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["ck", 0], "shift": 5.0}},
        "pos": {"class_type": "TextEncodeAceStepAudio", "inputs": {"clip": ["ck", 1], "tags": c["tags"], "lyrics": "[instrumental]", "lyrics_strength": 0.99}},
        "neg": {"class_type": "TextEncodeAceStepAudio", "inputs": {"clip": ["ck", 1], "tags": "vocals, singing, speech, distortion, noise", "lyrics": "", "lyrics_strength": 0.99}},
        "lat": {"class_type": "EmptyAceStepLatentAudio", "inputs": {"seconds": a.seconds, "batch_size": 1}},
        "ks": {"class_type": "KSampler", "inputs": {"model": ["ms", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
               "seed": c["seed"], "steps": 50, "cfg": 5.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "dec": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["ks", 0], "vae": ["ck", 2]}},
        "save": {"class_type": "SaveAudioMP3", "inputs": {"audio": ["dec", 0], "filename_prefix": f"tinyworld/music_{a.template}_{c['id']}", "quality": "V0"}},
    }
    print(c["id"], flush=True)
    comfy.run(g, a.out)
