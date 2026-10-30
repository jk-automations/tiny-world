"""Tiny World ComfyUI nodes. The model steps use stock ComfyUI + Lightricks LTXVideo nodes; these three nodes add what a
template app needs: pick a template (and its clay camera video), read the photo, and cut the finished video."""
import json, tempfile
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from . import tinyworld_core as core

try:
    from comfy_api.input_impl import VideoFromFile
except ImportError:  # older ComfyUI
    from comfy_api.latest._input_impl import VideoFromFile

DEFAULT_SET = "template default"
# Variety without new Blender work: each style / look is a sentence added to the miniature and film prompts. The
# 3-candidate layout check keeps the camera layout exact whatever the style.
STYLES = {   # material styles tested 2026-10-27: the restyle step kept the wood look for every one, so only wood ships
    "handmade wood (default)": "",
}
LOOKS = {    # tested 2026-10-27: night and rain read clearly; snow and spring barely changed the miniature, so they are out
    "golden hour (default)": "",
    "night, glowing windows": "Change the time to night: dark blue sky, every window and light glowing warm, tiny street lamps on.",
    "rainy evening": "Make it a rainy evening: wet shiny ground with reflections, soft rain, glowing windows.",
}
MATCH_PHOTOS = "match my photos"   # default: any close-up photo; motion never changes what the object is
NEUTRAL_MOTION = ("Cinematic slow motion close-up of exactly this object. The camera slowly pushes in, soft light shimmers "
                  "across its surfaces. Nothing changes shape, nothing new appears, it stays exactly the same object. Soft ambient sound.")


def _to_tensor(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(a)[None]


def _to_pil(image):
    return Image.fromarray((image[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8))


class TinyWorldFacts:
    """A vision model lists what the photo shows (colors, door, windows, roof...). The list is added to the miniature
    prompt so the tiny version copies the real details. Any OpenAI-compatible endpoint with image input works."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("facts_json", "copy_sentence")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "photo": ("IMAGE",),
            "template": (core.templates(),),
            "enabled": ("BOOLEAN", {"default": True, "tooltip": "Off = skip; likeness drops (tested 2026-10-25)."}),
            "endpoint": ("STRING", {"default": "http://127.0.0.1:11434/v1/chat/completions"}),
            "model": ("STRING", {"default": "qwen2.5vl:7b"}),
            "timeout": ("INT", {"default": 900, "min": 30, "max": 3600}),
        }}

    def run(self, photo, template, enabled, endpoint, model, timeout):
        if not enabled:
            return ("{}", "")
        try:
            facts = core.read_facts(core.jpeg_bytes(_to_pil(photo)), template, endpoint, model, timeout)
        except Exception as e:  # no vision model reachable: keep going without the list (less likeness), never stop the app
            print(f"[Tiny World] Read Photo skipped: {e}")
            return ("{}", "")
        return (json.dumps(facts, indent=2), facts.get("copy_sentence", ""))


class TinyWorldTemplate:
    """Loads a template: the Blender clay camera video, the approved generic miniature (step A) and every locked prompt.
    With auto_shape on, the photo facts pick the closest clay in the same family (e.g. flat / pitched roof / one storey)."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("VIDEO", "IMAGE", "STRING", "STRING", "STRING", "STRING", "INT", "INT", "INT", "INT", "INT", "FLOAT",
                    "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("clay_video", "keyframe_A", "keyframe_prompt", "keyframe_negative", "film_prompt", "reveal_prompt",
                    "width", "height", "half_width", "half_height", "frames", "fps", "closeup_motion_1", "closeup_motion_2", "closeup_motion_3",
                    "endcard_line", "template_used")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
                    "template": (core.templates(),),
                    "auto_shape": ("BOOLEAN", {"default": True}),
                    "closeup_set": ([MATCH_PHOTOS, DEFAULT_SET] + core.closeup_sets(),),
                    "endcard_line": ("STRING", {"default": "", "tooltip": "Empty = the template's line (e.g. Visit us today)."}),
                    "style": (list(STYLES),),
                    "look": (list(LOOKS),),
                    "extra_details": ("STRING", {"default": "", "tooltip": "Your own touch, e.g. a tiny cat on the windowsill"}),
                    "figure": (["painted figurine", "plushie"], {"tooltip": "Selfie mode (template me): you as a painted collectible figurine or a soft knitted plushie"}),
                },
                "optional": {
                    "facts_json": ("STRING", {"forceInput": True}),
                    "copy_sentence": ("STRING", {"forceInput": True}),
                }}

    def run(self, template, auto_shape, closeup_set, endcard_line, style=None, look=None, extra_details="", figure="painted figurine",
            facts_json="{}", copy_sentence=""):
        if auto_shape and facts_json:
            try: template = core.pick_shape(template, json.loads(facts_json))
            except json.JSONDecodeError: pass
        t = core.load_template(template)
        d = core.TEMPLATES_DIR / template
        plush = figure == "plushie" and "keyframe_restyle_prompt_plush" in t
        prompt = t["keyframe_restyle_prompt_plush" if plush else "keyframe_restyle_prompt"] + (" Features to copy from image 2: " + copy_sentence if copy_sentence else "")
        if plush: t["film_prompt"] = t["film_prompt"].replace("a hand-painted collectible bobblehead figurine", "a soft handmade knitted plushie").replace("The bobblehead's big head bobs gently up and down on its spring; its body", "The plushie")
        flavour = " ".join(x for x in (STYLES.get(style or "", ""), LOOKS.get(look or "", ""),
                                       ("Add: " + extra_details.strip()) if extra_details.strip() else "") if x)
        film = t["film_prompt"] + (" " + flavour if flavour else "")
        if flavour: prompt += " " + flavour + " Keep the same layout, camera angle and framing as image 1."
        kind = t.get("closeups") if closeup_set == DEFAULT_SET else closeup_set
        motions = [NEUTRAL_MOTION] * 3
        if closeup_set != MATCH_PHOTOS and kind:
            shots = json.loads((core.TEMPLATES_DIR / "closeups" / f"{kind}.json").read_text())["shots"]
            motions = [s["motion"] for s in shots[:3]]
        return (VideoFromFile(str(d / "clay.mp4")), _to_tensor(d / "keyframe_A.png"), prompt, t["keyframe_negative"],
                film, t.get("reveal_prompt", ""), t["width"], t["height"], t["width"] // 2, t["height"] // 2,
                t["frames"], float(t["fps"]),
                *motions, endcard_line or t.get("endcard_line", "Visit us today"), template)


class TinyWorldObjectClay:
    """Any Object: your photo -> a 3D mesh (TripoSR) -> your object's own shape in the Blender scene -> clay camera video.
    Needs TripoSR (env TINYWORLD_TRIPOSR, default ~/tools/TripoSR) and Blender (env TINYWORLD_BLENDER). Outputs the
    same things as Template, plus the clay first frame for the step-A miniature (made in this run)."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("VIDEO", "IMAGE", "STRING", "STRING", "STRING", "STRING", "STRING", "INT", "INT", "INT", "INT", "INT", "FLOAT",
                    "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("clay_video", "clay_first_frame", "miniature_prompt", "keyframe_prompt", "keyframe_negative", "film_prompt",
                    "reveal_prompt", "width", "height", "half_width", "half_height", "frames", "fps",
                    "closeup_motion_1", "closeup_motion_2", "closeup_motion_3", "endcard_line")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"photo": ("IMAGE",), "scene": (list(core.OBJECT_SCENES),),
                             "style": (list(STYLES),), "look": (list(LOOKS),),
                             "extra_details": ("STRING", {"default": ""}), "endcard_line": ("STRING", {"default": ""})},
                "optional": {"copy_sentence": ("STRING", {"forceInput": True})}}

    def run(self, photo, scene, style, look, extra_details, endcard_line, copy_sentence=""):
        tmp = Path(tempfile.mkdtemp(prefix="tinyworld_obj_"))
        _to_pil(photo).save(tmp / "photo.png")
        clay, first, template = core.object_clay(tmp / "photo.png", scene, tmp)
        t = core.load_template(template)
        flavour = " ".join(x for x in (STYLES.get(style, ""), LOOKS.get(look, ""),
                                       ("Add: " + extra_details.strip()) if extra_details.strip() else "") if x)
        prompt = t["keyframe_restyle_prompt"] + (" Features to copy from image 2: " + copy_sentence if copy_sentence else "")
        if flavour: prompt += " " + flavour + " Keep the same layout, camera angle and framing as image 1."
        return (VideoFromFile(str(clay)), _to_tensor(first), t["keyframe_prompt"], prompt, t["keyframe_negative"],
                t["film_prompt"] + (" " + flavour if flavour else ""), t.get("reveal_prompt", ""),
                t["width"], t["height"], t["width"] // 2, t["height"] // 2, t["frames"], float(t["fps"]),
                NEUTRAL_MOTION, NEUTRAL_MOTION, NEUTRAL_MOTION, endcard_line or t.get("endcard_line", "@yourname"))


class TinyWorldPickMiniature:
    """Gate E inside the app: several miniature candidates in, the one that best keeps the template layout out.
    (A strong photo can pull a candidate into a realistic close-up that is no longer tiny.)"""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("miniature", "scores")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"candidates": ("IMAGE",), "keyframe_A": ("IMAGE",)}}

    def run(self, candidates, keyframe_A):
        ref = _to_pil(keyframe_A)
        scores = []
        for c in candidates:
            a = c.cpu().numpy()
            if not np.isfinite(a).all() or a.max() < 0.02:   # blank or broken candidate never wins
                scores.append(-1.0); continue
            scores.append(core.layout_score(ref, Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))))
        best = int(np.argmax(scores))
        return (candidates[best:best + 1], json.dumps({"scores": [round(x, 3) for x in scores], "picked": best}))


class TinyWorldExtras:
    """The fun layer: an intro (collector box / snow globe) and cutaways (a giant guest: your pet, kid or you; tiny-me: your
    selfie as a painted figurine). Outputs the prompts for each beat and which beats are on; Final Cut only asks for the
    beats that are on, so switched-off beats cost nothing."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "BOOLEAN", "BOOLEAN", "BOOLEAN", "STRING",
                    "STRING", "STRING", "STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("intro_kind", "intro_still", "intro_motion", "guest_still", "guest_motion", "me_still", "me_motion",
                    "use_intro", "use_guest", "use_me", "intro_negative", "me_walk_motion", "me_act_still", "me_act_motion", "morph_motion", "use_morph")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"intro": (["none", "collector box", "snow globe"],),
                             "giant_guest": ("BOOLEAN", {"default": False, "tooltip": "Places only: upload a pet / kid / you photo as the guest (ignored in selfie mode)"}),
                             "tiny_me": ("BOOLEAN", {"default": False, "tooltip": "Upload your own selfie: you become a painted figurine that walks in, does its thing (games at the PC, runs the shop...) and waves"}),
                             "tiny_to_real": (["morph (seamless)", "zoom cut"], {"tooltip": "morph: one LTX shot where the miniature grows into the real place"})},
                "optional": {"template": ("STRING", {"forceInput": True})}}

    def run(self, intro, giant_guest, tiny_me, tiny_to_real="zoom cut", template=""):
        b = json.loads((core.TEMPLATES_DIR / "beats.json").read_text())
        ik = {"collector box": "box", "snow globe": "globe"}.get(intro, "")
        ib = b.get(ik, {"still": "", "motion": "", "negative": "text"})
        kind = "room" if "room" in template else "storefront" if "storefront" in template else "default"
        act = b[b["me_actions"][kind]]   # what tiny-me does in its world: games at the PC, runs the shop, looks around
        selfie = template == "me"         # the photo already is you: the figurine on the pedestal is tiny-me
        return (ik, ib["still"], ib["motion"], b["guest"]["still"], b["guest"]["motion"], b["figurine"]["still"], b["figurine"]["motion"],
                bool(ik), bool(giant_guest) and not selfie, bool(tiny_me) and not selfie, ib.get("negative", "text"),
                b["me_walk"]["motion"], act["still"], act["motion"], b["morph_me" if selfie else "morph"]["motion"], tiny_to_real.startswith("morph"))


class TinyWorldGlowUp:
    """Glow-up: turns an everyday phone photo of your own place into an aesthetic photo of the same place (relit, tidy,
    graded) before the tiny version and the reveal are made, so both get the upgrade and still match. Keeps every object.
    Outputs the edit prompt; Glow-Up Switch only asks for the edited photo when the glow-up is on."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("glow_up", "prompt", "negative", "closeups_glow", "closeup_prompt", "closeup_negative")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        looks = list(json.loads((core.TEMPLATES_DIR / "glowup.json").read_text()))
        return {"required": {"glow_up": (["off"] + looks, {"tooltip": "Make the real part aesthetic: same things, better light"}),
                             "glow_closeups": ("BOOLEAN", {"default": True, "tooltip": "Also glow up the 3 close-up photos (about 15 min more)"})}}

    def run(self, glow_up, glow_closeups=True):
        L = json.loads((core.TEMPLATES_DIR / "glowup.json").read_text()).get(glow_up, {"prompt": "", "negative": ""})
        # close-ups keep their framing: a look that adds things to the room only relights its close-ups
        return (glow_up, L["prompt"], L["negative"], glow_up if glow_closeups else "off",
                L.get("closeup_prompt", L["prompt"]), L.get("closeup_negative", L["negative"]))


class TinyWorldGlowSwitch:
    """Your photo, or its glow-up when the glow-up is on (the edit only runs when it is on)."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("photo",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"photo": ("IMAGE",), "glow_up": ("STRING", {"forceInput": True})},
                "optional": {"glowed": ("IMAGE", {"lazy": True})}}

    def check_lazy_status(self, photo, glow_up, glowed=None):
        return ["glowed"] if glow_up != "off" and glowed is None else []

    def run(self, photo, glow_up, glowed=None):
        return (glowed if glow_up != "off" and glowed is not None else photo,)


def _ending(ending, template):
    """A template can force its ending (selfie mode has no close-ups: ending short)."""
    try: return core.load_template(template).get("ending", ending) if template else ending
    except FileNotFoundError: return ending


class TinyWorldFinish:
    """The final cut: tiny fly-through -> zoom into the real place -> name title; with the close-up ending:
    door zoom -> 3 close-ups on the beat -> end card. Music under everything, -14 LUFS."""
    CATEGORY = "Tiny World"
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        music = sorted(p.stem for p in (core.TEMPLATES_DIR / "music").glob("*.mp3"))
        return {"required": {
                    "fly_through": ("VIDEO",),
                    "reveal": ("VIDEO",),
                    "name": ("STRING", {"default": "Your Name Here"}),
                    "endcard_line": ("STRING", {"forceInput": True}),
                    "ending": (["closeups", "short"],),
                    "music": (music + ["none"], {"tooltip": "none: post it and add a trending sound in TikTok / Instagram"}),
                    "hook_text": ("STRING", {"default": "", "tooltip": "Optional opening caption, e.g. POV: my setup was tiny the whole time"}),
                    "credit": ("BOOLEAN", {"default": True, "tooltip": "Small 'made with Tiny World' on the end card"}),
                    "motion": (["smooth", "stop-motion"], {"tooltip": "stop-motion: the tiny part moves like a handmade stop-motion film (12 fps); the real part stays smooth"}),
                    "bobble": (["auto", "off"], {"tooltip": "auto: in selfie mode the camera pauses and the figurine's big head wobbles on its spring like a bobblehead toy"}),
                },
                "optional": {"closeup_1": ("VIDEO", {"lazy": True}), "closeup_2": ("VIDEO", {"lazy": True}), "closeup_3": ("VIDEO", {"lazy": True}),
                             "template": ("STRING", {"forceInput": True}),
                             "intro_kind": ("STRING", {"forceInput": True}), "use_intro": ("BOOLEAN", {"forceInput": True}),
                             "use_guest": ("BOOLEAN", {"forceInput": True}), "use_me": ("BOOLEAN", {"forceInput": True}),
                             "intro_still": ("IMAGE", {"tooltip": "Optional: your own intro still with a flat pure-green window"}), "guest_clip": ("VIDEO", {"lazy": True}), "me_clip": ("VIDEO", {"lazy": True}),
                             "me_walk_clip": ("VIDEO", {"lazy": True}), "me_act_clip": ("VIDEO", {"lazy": True}),
                             "use_morph": ("BOOLEAN", {"forceInput": True}), "morph_clip": ("VIDEO", {"lazy": True})}}

    def check_lazy_status(self, use_intro=False, use_guest=False, use_me=False, intro_still=None, guest_clip=None, me_clip=None,
                          me_walk_clip=None, me_act_clip=None, use_morph=False, morph_clip=None, ending="closeups", template="",
                          closeup_1=None, closeup_2=None, closeup_3=None, **_):
        need = []
        if _ending(ending, template) == "closeups":
            need += [k for k, v in (("closeup_1", closeup_1), ("closeup_2", closeup_2), ("closeup_3", closeup_3)) if v is None]
        if use_guest and guest_clip is None: need.append("guest_clip")
        if use_me: need += [k for k, v in (("me_walk_clip", me_walk_clip), ("me_act_clip", me_act_clip), ("me_clip", me_clip)) if v is None]
        if use_morph and morph_clip is None: need.append("morph_clip")
        return need

    def run(self, fly_through, reveal, name, endcard_line, ending, music, hook_text="", credit=True, motion="smooth", bobble="auto", closeup_1=None, closeup_2=None,
            closeup_3=None, intro_kind="", use_intro=False, use_guest=False, use_me=False, intro_still=None, guest_clip=None, me_clip=None,
            me_walk_clip=None, me_act_clip=None, use_morph=False, morph_clip=None, template=""):
        import folder_paths
        ending = _ending(ending, template)
        tmp = Path(tempfile.mkdtemp(prefix="tinyworld_"))
        def save(v, n):
            p = tmp / f"{n}.mp4"; v.save_to(str(p)); return p
        film, rev = save(fly_through, "film"), save(reveal, "reveal")
        title_out = None
        if ending == "closeups":
            cs = [c for c in (closeup_1, closeup_2, closeup_3) if c is not None]
            if len(cs) != 3:
                raise ValueError("The close-up ending needs 3 close-up clips (or pick ending = short).")
            rd = core.ending(rev, [save(c, f"c{i}") for i, c in enumerate(cs)], name, endcard_line, tmp / "tail.mp4", tmp=tmp, credit=credit)
            rev, title_out = tmp / "tail.mp4", round(rd - 0.8, 2)   # the title fades out before the close-ups
        out_dir = Path(folder_paths.get_temp_directory()); out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"tinyworld_{next(tempfile._get_candidate_names())}.mp4"
        mus = None if music == "none" else core.TEMPLATES_DIR / "music" / f"{music}.mp3"
        intro = None
        if use_intro:   # the fly-through's first frame goes into the green window: one tiny world
            still = core.TEMPLATES_DIR / "intros" / f"{intro_kind or 'box'}.png"   # shipped stills: a generated one can copy the diorama
            if intro_still is not None:
                still = tmp / "intro_still.png"
                Image.fromarray((intro_still[0].cpu().numpy() * 255).clip(0, 255).astype("uint8")).save(still)
            intro = tmp / "intro.mp4"
            if not core.intro_window(still, film, intro, intro_kind or "box", title=name if intro_kind == "box" else ""):
                print("[Tiny World] intro skipped: no green window found in the intro still (try another seed)"); intro = None
        # the story in the tiny world: tiny-me walks in, does its thing, the giant guest drops by, tiny-me waves
        beats = ((use_me, me_walk_clip), (use_me, me_act_clip), (use_guest, guest_clip), (use_me, me_clip))
        cuts = [save(c, f"cut{i}") for i, (on, c) in enumerate(beats) if on and c is not None]
        morph = save(morph_clip, "morph") if use_morph and morph_clip is not None else None
        tj = core.TEMPLATES_DIR / "music" / "tracks.json"
        tr = json.loads(tj.read_text()).get(music, {}) if tj.exists() else {}
        drop, beat = tr.get("drop"), 60 / tr.get("bpm", 120)
        core.final_cut(film, rev, name, out, mus, title_out, tmp=tmp, hook=hook_text.strip(), intro=intro, cutaways=cuts,
                       seamless=True, morph=morph, music_drop=drop, music_beat=beat, stopmo=motion == "stop-motion",
                       bobble=bobble == "auto" and template == "me")
        return (VideoFromFile(str(out)),)


NODE_CLASS_MAPPINGS = {"TinyWorldFacts": TinyWorldFacts, "TinyWorldTemplate": TinyWorldTemplate,
                       "TinyWorldPickMiniature": TinyWorldPickMiniature, "TinyWorldObjectClay": TinyWorldObjectClay,
                       "TinyWorldExtras": TinyWorldExtras,
                       "TinyWorldGlowUp": TinyWorldGlowUp, "TinyWorldGlowSwitch": TinyWorldGlowSwitch,
                       "TinyWorldFinish": TinyWorldFinish}
NODE_DISPLAY_NAME_MAPPINGS = {"TinyWorldFacts": "Tiny World: Read Photo", "TinyWorldTemplate": "Tiny World: Template",
                              "TinyWorldPickMiniature": "Tiny World: Pick Best Miniature",
                              "TinyWorldObjectClay": "Tiny World: Photo to 3D Clay",
                              "TinyWorldExtras": "Tiny World: Fun Layer",
                              "TinyWorldGlowUp": "Tiny World: Glow-Up", "TinyWorldGlowSwitch": "Tiny World: Glow-Up Switch",
                              "TinyWorldFinish": "Tiny World: Final Cut"}
