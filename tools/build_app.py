"""Build the one-graph Tiny World app (ComfyUI API format): photo + 3 close-up photos + name -> finished video.
Same locked settings as the step-by-step tools (tools/keyframe.py, film.py, reveal.py).
python3 tools/build_app.py --out workflows/tiny-world-api.json"""
import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="workflows/tiny-world-api.json")
ap.add_argument("--photo", default="tinyworld_photo.png"); ap.add_argument("--closeups", nargs=3, default=["tinyworld_c1.png", "tinyworld_c2.png", "tinyworld_c3.png"])
ap.add_argument("--template", default="me"); ap.add_argument("--name", default="Your Name Here")
ap.add_argument("--closeup-set", default="match my photos"); ap.add_argument("--hook", default="")
ap.add_argument("--object", action="store_true", help="Any Object app: photo -> 3D clay instead of a fixed template")
ap.add_argument("--scene", default="town square (any object)"); ap.add_argument("--style", default="handmade wood (default)")
ap.add_argument("--look", default="golden hour (default)"); ap.add_argument("--glow-up", default="off")
ap.add_argument("--intro", default="collector box"); ap.add_argument("--guest-photo", default="tinyworld_blank.png"); ap.add_argument("--me-photo", default="tinyworld_blank.png")
ap.add_argument("--giant-guest", action="store_true"); ap.add_argument("--tiny-me", action="store_true")
ap.add_argument("--tiny-to-real", default="morph (seamless)")
ap.add_argument("--figure", default="painted figurine"); ap.add_argument("--motion", default="smooth"); ap.add_argument("--bobble", default="auto")
ap.add_argument("--vision-endpoint", default="http://127.0.0.1:11434/v1/chat/completions"); ap.add_argument("--vision-model", default="qwen2.5vl:7b"); ap.add_argument("--music", default="phonk-drop")
a = ap.parse_args()

g = {}
nid = iter(range(1, 1000))
def node(cls, **inputs):
    i = str(next(nid)); g[i] = {"class_type": cls, "inputs": inputs}; return i
def o(i, k=0): return [i, k]

# ---------- user inputs ----------
photo = node("LoadImage", image=a.photo)
cups = [node("LoadImage", image=c) for c in a.closeups]
guest_img = node("LoadImage", image=a.guest_photo)      # giant guest: a pet, a kid or you (optional)
me_img = node("LoadImage", image=a.me_photo)            # tiny me: your own selfie (optional)
X = node("TinyWorldExtras", intro=a.intro, giant_guest=a.giant_guest, tiny_me=a.tiny_me, tiny_to_real=a.tiny_to_real)
# ---------- read the photo + template ----------
facts = node("TinyWorldFacts", photo=o(photo), template=("car" if "garage" in a.scene else "product-pedestal") if a.object else a.template, enabled=True,
             endpoint=a.vision_endpoint, model=a.vision_model, timeout=900)
if a.object:
    T = node("TinyWorldObjectClay", photo=o(photo), scene=a.scene, style=a.style, look=a.look, extra_details="", endcard_line="",
             copy_sentence=o(facts, 1))
    IDX = dict(clay=0, first=1, mini=2, prompt=3, neg=4, film=5, reveal=6, w=7, h=8, hw=9, hh=10, frames=11, fps=12, m1=13, endcard=16)
else:
    T = node("TinyWorldTemplate", template=a.template, auto_shape=True, closeup_set=a.closeup_set, endcard_line="",
             style=a.style, look=a.look, extra_details="", figure=a.figure,
             facts_json=o(facts, 0), copy_sentence=o(facts, 1))
    IDX = dict(clay=0, kfA=1, prompt=2, neg=3, film=4, reveal=5, w=6, h=7, hw=8, hh=9, frames=10, fps=11, m1=12, endcard=15)
def tt(k, add=0): return [T, IDX[k] + add]
if not a.object: g[X]["inputs"]["template"] = o(T, 16)   # template_used: picks what tiny-me does there
# ---------- step B keyframe: generic miniature (image 1) + photo (image 2) -> their tiny version (Qwen-Image-Edit-2511) ----------
q_unet = node("UNETLoader", unet_name="qwen_image_edit_2511_bf16.safetensors", weight_dtype="default")
q_clip = node("CLIPLoader", clip_name="qwen_2.5_vl_7b.safetensors", type="qwen_image", device="default")
q_vae = node("VAELoader", vae_name="qwen_image_vae.safetensors")
q_ms = node("ModelSamplingAuraFlow", model=o(q_unet), shift=3.1)
# ---------- glow-up (optional): the same place, aesthetic; feeds the miniature and the reveal so they keep matching ----------
GL = node("TinyWorldGlowUp", glow_up=a.glow_up, glow_closeups=True)
# Lightning 4-step LoRA on the glow-ups only: about 5x faster, same look in our tests
g_ms = node("ModelSamplingAuraFlow", model=o(node("LoraLoaderModelOnly", model=o(q_unet), lora_name="Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", strength_model=1.0)), shift=3.1)
def glow(img, on, pi=1, ni=2):
    g_img = node("ImageScaleToTotalPixels", image=o(img), upscale_method="lanczos", megapixels=1.0, resolution_steps=16)
    g_lat = node("VAEEncode", pixels=o(g_img), vae=o(q_vae))
    g_pos = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=o(GL, pi), vae=o(q_vae), image1=o(g_img))
    g_neg = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=o(GL, ni), vae=o(q_vae), image1=o(g_img))
    g_ks = node("KSampler", model=o(g_ms), positive=o(g_pos), negative=o(g_neg), latent_image=o(g_lat), seed=7, steps=4, cfg=1.0,
                sampler_name="euler", scheduler="simple", denoise=1.0)
    return node("TinyWorldGlowSwitch", photo=o(img), glow_up=on, glowed=o(node("VAEDecode", samples=o(g_ks), vae=o(q_vae))))
real = glow(photo, o(GL, 0))
real_cups = [glow(c, o(GL, 3), 4, 5) for c in cups]
if a.object:   # step A (generic miniature of the user's own clay) is made in this run
    a_pos = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=tt("mini"), vae=o(q_vae), image1=tt("first"))
    a_neg = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=tt("neg"), vae=o(q_vae), image1=tt("first"))
    a_ks = node("KSampler", model=o(q_ms), positive=o(a_pos), negative=o(a_neg), latent_image=o(node("VAEEncode", pixels=tt("first"), vae=o(q_vae))),
                seed=7, steps=20, cfg=2.5, sampler_name="euler", scheduler="simple", denoise=1.0)
    kfA = [node("VAEDecode", samples=o(a_ks), vae=o(q_vae)), 0]
else:
    kfA = tt("kfA")
q_lat = node("VAEEncode", pixels=kfA, vae=o(q_vae))
q_pos = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=tt("prompt"), vae=o(q_vae), image1=kfA, image2=o(real))
q_neg = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=tt("neg"), vae=o(q_vae), image1=kfA, image2=o(real))
# 3 candidates, one after another (a batched latent gives NaN images on Apple MPS), then Gate E picks one
decoded = []
for k, seed in enumerate((7, 8, 9)):
    ks = node("KSampler", model=o(q_ms), positive=o(q_pos), negative=o(q_neg), latent_image=o(q_lat), seed=seed, steps=20, cfg=2.5,
              sampler_name="euler", scheduler="simple", denoise=1.0)
    decoded.append(node("VAEDecode", samples=o(ks), vae=o(q_vae)))
cands = node("ImageBatch", image1=o(decoded[0]), image2=o(decoded[1]))
cands = node("ImageBatch", image1=o(cands), image2=o(decoded[2]))
pick = node("TinyWorldPickMiniature", candidates=o(cands), keyframe_A=kfA)
node("PreviewImage", images=o(pick))
# ---------- LTX-2.5 models (shared) ----------
unet = node("UNETLoader", unet_name="ltx-2.5-22b-distilled-transformer-bf16.safetensors", weight_dtype="default")
lora = node("LTXICLoRALoaderModelOnly", model=o(unet), lora_name="ltx-2.5-22b-ic-lora-layout-to-render-1.0.safetensors", strength_model=1.0)
clip = node("CLIPLoader", clip_name="gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", type="ltxv", device="default")
vvae = node("VAELoader", vae_name="ltx-2.5-video-vae-bf16.safetensors")
avae = node("VAELoader", vae_name="ltx-2.5-audio-vae-bf16.safetensors")
ups = node("LatentUpscaleModelLoader", model_name="ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors")
ksel = node("KSamplerSelect", sampler_name="euler_ancestral")
S1 = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
# ---------- fly-through: clay camera video + keyframe at the last frame -> Layout-To-Render IC-LoRA (two stages) ----------
f_pos = node("CLIPTextEncode", clip=o(clip), text=tt("film"))
f_neg = node("CLIPTextEncode", clip=o(clip), text="")
f_cond = node("LTXVConditioning", positive=o(f_pos), negative=o(f_neg), frame_rate=tt("fps"))
comp = node("GetVideoComponents", video=tt("clay"))
f_lat = node("EmptyLTXVLatentVideo", width=tt("hw"), height=tt("hh"), length=tt("frames"), batch_size=1)
def guide(pos, neg, lat, image, idx, crop):
    return node("LTXAddVideoICLoRAGuide", positive=pos, negative=neg, vae=o(vvae), latent=lat, image=image, frame_idx=idx, strength=1.0,
                latent_downscale_factor=o(lora, 1), crop=crop, use_tiled_encode=False, tile_size=256, tile_overlap=64)
def sample(guided, sigmas):
    noise = node("RandomNoise", noise_seed=42)
    cfg = node("CFGGuider", model=o(lora), positive=o(guided, 0), negative=o(guided, 1), cfg=1.0)
    sig = node("ManualSigmas", sigmas=sigmas)
    run = node("SamplerCustomAdvanced", noise=o(noise), guider=o(cfg), sampler=o(ksel), sigmas=o(sig), latent_image=o(guided, 2))
    return node("LTXVCropGuides", positive=o(guided, 0), negative=o(guided, 1), latent=o(run))
g1 = guide(o(f_cond, 0), o(f_cond, 1), o(f_lat), o(comp, 0), 0, "disabled")
g2 = guide(o(g1, 0), o(g1, 1), o(g1, 2), o(pick), -1, "center")
c1 = sample(g2, S1)
up = node("LTXVLatentUpsampler", samples=o(c1, 2), upscale_model=o(ups), vae=o(vvae))
g3 = guide(o(c1, 0), o(c1, 1), o(up), o(comp, 0), 0, "disabled")
g4 = guide(o(g3, 0), o(g3, 1), o(g3, 2), o(pick), -1, "center")
c2 = sample(g4, "0.909375, 0.725, 0.421875, 0.0")
f_dec = node("VAEDecodeTiled", samples=o(c2, 2), vae=o(vvae), tile_size=512, overlap=64, temporal_size=128, temporal_overlap=32)
film = node("CreateVideo", images=o(f_dec), fps=tt("fps"))
# ---------- image -> short realistic clip with sound (reveal + close-ups), LTX-2.5 two stages ----------
def clip_from(image, prompt, frames, seed, last=None, last_strength=0.7):
    pos = node("CLIPTextEncode", clip=o(clip), text=prompt)
    neg = node("CLIPTextEncode", clip=o(clip), text="cartoon, miniature, low quality, warped, text artifacts")
    cond = node("LTXVConditioning", positive=o(pos), negative=o(neg), frame_rate=24.0)
    i1 = node("ImageScale", image=image, upscale_method="lanczos", width=tt("hw"), height=tt("hh"), crop="center")
    i2 = node("ImageScale", image=image, upscale_method="lanczos", width=tt("w"), height=tt("h"), crop="center")
    vl = node("EmptyLTXVLatentVideo", width=tt("hw"), height=tt("hh"), length=frames, batch_size=1)
    vli = node("LTXVImgToVideoInplace", vae=o(vvae), image=o(i1), latent=o(vl), strength=1.0, bypass=False)
    al = node("LTXVEmptyLatentAudio", audio_vae=o(avae), frames_number=frames, frame_rate=24, batch_size=1)
    av1 = node("LTXVConcatAVLatent", video_latent=o(vli), audio_latent=o(al))
    gd1 = node("LTXVDualCFGGuider", model=o(unet), positive=o(cond, 0), negative=o(cond, 1), video_cfg=1, audio_cfg=1)
    s1 = node("SamplerCustomAdvanced", noise=o(node("RandomNoise", noise_seed=seed)), guider=o(gd1), sampler=o(ksel),
              sigmas=o(node("ManualSigmas", sigmas=S1)), latent_image=o(av1))
    sep1 = node("LTXVSeparateAVLatent", av_latent=o(s1))
    upl = node("LTXVLatentUpsampler", samples=o(sep1, 0), upscale_model=o(ups), vae=o(vvae))
    upi = node("LTXVImgToVideoInplace", vae=o(vvae), image=o(i2), latent=o(upl), strength=1.0, bypass=False)
    av2 = node("LTXVConcatAVLatent", video_latent=o(upi), audio_latent=o(sep1, 1))
    gd2 = node("LTXVDualCFGGuider", model=o(unet), positive=o(cond, 0), negative=o(cond, 1), video_cfg=1, audio_cfg=1)
    s2 = node("SamplerCustomAdvanced", noise=o(node("RandomNoise", noise_seed=seed)), guider=o(gd2), sampler=o(ksel),
              sigmas=o(node("ManualSigmas", sigmas="0.85, 0.7250, 0.4219, 0.0")), latent_image=o(av2))
    sep2 = node("LTXVSeparateAVLatent", av_latent=o(s2))
    if last is not None:   # last-frame guide in both stages (the morph), cropped off after each sampler, as in reveal.py --last
        l1 = node("LTXVAddGuide", positive=o(cond, 0), negative=o(cond, 1), vae=o(vvae), latent=o(vli),
                  image=o(node("ImageScale", image=last, upscale_method="lanczos", width=tt("hw"), height=tt("hh"), crop="center")), frame_idx=-1, strength=last_strength)
        g[av1]["inputs"]["video_latent"] = o(l1, 2); g[gd1]["inputs"].update(positive=o(l1, 0), negative=o(l1, 1))
        c1 = node("LTXVCropGuides", positive=o(l1, 0), negative=o(l1, 1), latent=o(sep1, 0)); g[upl]["inputs"]["samples"] = o(c1, 2)
        l2 = node("LTXVAddGuide", positive=o(c1, 0), negative=o(c1, 1), vae=o(vvae), latent=o(upi),
                  image=o(node("ImageScale", image=last, upscale_method="lanczos", width=tt("w"), height=tt("h"), crop="center")), frame_idx=-1, strength=last_strength)
        g[av2]["inputs"]["video_latent"] = o(l2, 2); g[gd2]["inputs"].update(positive=o(l2, 0), negative=o(l2, 1))
        sep2 = node("LTXVCropGuides", positive=o(l2, 0), negative=o(l2, 1), latent=o(sep2, 0))
        vd = node("VAEDecodeTiled", samples=o(sep2, 2), vae=o(vvae), tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16)
        return node("CreateVideo", images=o(vd), fps=24.0, audio=o(node("LTXVAudioVAEDecode", samples=o(g[sep2]["inputs"]["latent"][0], 1), audio_vae=o(avae))))
    vd = node("VAEDecodeTiled", samples=o(sep2, 0), vae=o(vvae), tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16)
    ad = node("LTXVAudioVAEDecode", samples=o(sep2, 1), audio_vae=o(avae))
    return node("CreateVideo", images=o(vd), fps=24.0, audio=o(ad))
reveal = clip_from(o(real), tt("reveal"), 57, 42)                       # 2.4 s
cvids = [clip_from(o(c), tt("m1", k), 33, 42) for k, c in enumerate(real_cups)]   # 1.4 s each
# ---------- fun layer: each beat = one Qwen composite from the picked miniature -> one short LTX clip (only built when on) ----------
def beat(prompt, second=None, seed=7, first=None, fast=False, neg="text, letters, logo, watermark, blurry, low quality, deformed, extra limbs"):
    imgs = {"image1": o(first or pick)}
    if second: imgs["image2"] = o(second)
    pos = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=prompt, vae=o(q_vae), **imgs)
    neg = node("TextEncodeQwenImageEditPlus", clip=o(q_clip), prompt=neg,
               vae=o(q_vae), **imgs)
    ks = node("KSampler", model=o(g_ms if fast else q_ms), positive=o(pos), negative=o(neg), latent_image=o(node("EmptySD3LatentImage", width=576, height=1024, batch_size=1)),
              seed=seed, steps=4 if fast else 20, cfg=1.0 if fast else 2.5, sampler_name="euler", scheduler="simple", denoise=1.0)
    return node("VAEDecode", samples=o(ks), vae=o(q_vae))
guest_clip = clip_from(o(beat(o(X, 3), guest_img, seed=11)), o(X, 4), 57, 42)   # seed 11: cleanest guest in our tests
# tiny me: one figurine still, then the same figurine edited into its action, so it stays the same figure
me_still = beat(o(X, 5), me_img)
me_clip = clip_from(o(me_still), o(X, 6), 57, 42)                                    # turns and waves
me_walk_clip = clip_from(o(me_still), o(X, 11), 57, 42)                              # walks in
me_act_clip = clip_from(o(beat(o(X, 12), first=me_still, fast=True)), o(X, 13), 57, 42)         # games at the PC / runs the shop
morph_clip = clip_from(o(pick), o(X, 14), 97, 42, last=o(real))   # tiny -> real in one 4 s LTX shot; a soft (0.7) last-frame guide lets the camera fly in first
# ---------- final cut ----------
fin = node("TinyWorldFinish", fly_through=o(film), reveal=o(reveal), name=a.name, endcard_line=tt("endcard"), ending="closeups", template=o(T, 16),
           music=a.music, hook_text=a.hook, credit=True, motion=a.motion, bobble=a.bobble, closeup_1=o(cvids[0]), closeup_2=o(cvids[1]), closeup_3=o(cvids[2]),
           intro_kind=o(X, 0), use_intro=o(X, 7), use_guest=o(X, 8), use_me=o(X, 9), guest_clip=o(guest_clip), me_clip=o(me_clip),
           me_walk_clip=o(me_walk_clip), me_act_clip=o(me_act_clip), use_morph=o(X, 15), morph_clip=o(morph_clip))
save = node("SaveVideo", video=o(fin), filename_prefix="tinyworld/final", format="mp4", **{"format.codec": "auto"})
a.out = a.out.replace("tiny-world-api", "tiny-world-any-object-api") if a.object else a.out
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(g, indent=1))
print(f"{len(g)} nodes -> {a.out}; inputs: photo {photo}, close-ups {cups}, template {T}, finish {fin}, save {save}")
