# Tiny World: licences of everything the workflow uses

Checked 2026-10-22 from Hugging Face model metadata. Re-check before submission.

| Part | Model / tool | Licence | Notes |
|---|---|---|---|
| Our code, workflows, Blender templates, music | Tiny World | Apache-2.0 | This repo |
| Video engine | LTX-2.5 22B distilled (Lightricks) | LTX-2.x Community License | Free for commercial use under $10M annual revenue. Gated on Hugging Face (accept terms) |
| Camera/layout control | LTX-2.5-22b-IC-LoRA-Layout-To-Render (Lightricks) | LTX-2.x Community License (`other`) | Gated on Hugging Face. Built for blockout to final render |
| Miniature keyframe | Qwen-Image-Edit-2511 | Apache-2.0 | ComfyUI repack: Comfy-Org/Qwen-Image-Edit |
| Glow-up (optional) | Qwen-Image-Edit-2511 + Lightning 4-step LoRA | Apache-2.0 | lightx2v/Qwen-Image-Edit-2511-Lightning |
| Real-photo depth (reveal) | Depth Anything V2 Small | Apache-2.0 | Do NOT use Base/Large (CC-BY-NC-4.0) |
| Upscale | SeedVR2 3B | Apache-2.0 | Optional finish step |
| Music | ACE-Step v1 3.5B | Apache-2.0 | Original instrumental tracks made once and shipped as audio (`templates/music/`: per-template beds + `phonk-drop`, `jersey-club`, `lofi-house`); no samples, no vocals |
| Tiny me / giant guest stills | Qwen-Image-Edit-2511 (+ Lightning 4-step LoRA) | Apache-2.0 | From the user's own photos; demo dog and selfie are AI-made fictional references |
| Bobblehead wobble | OpenCV (face detector + GrabCut) | Apache-2.0 | `tools/bobble.py`: classic computer vision, no model download, no GPU |
| Templates | Blender 5.1 | GPL-3.0 (the app) | Our .blend files and renders are ours, Apache-2.0 |

Node pack: Lightricks ComfyUI-LTXVideo (tested at commit 220e1d4). Its GemmaAPITextEncode node calls api.ltx.video only when given an API key; Tiny World uses the local Gemma text encoder instead.

Reference workflow + examples from the gated LoRA repo are kept locally in docs/ref-layout-to-render/ (gitignored, not redistributed).

Not used on purpose: FLUX.1-dev (non-commercial), Depth Anything V2 Large (non-commercial), any chart music, any third-party IP or likeness.
