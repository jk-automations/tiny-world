"""Tiny World shared logic for the ComfyUI nodes and the command-line tools: templates, photo facts, shape pick, final cut.
Only needs Python, Pillow and an ffmpeg binary on PATH (or TINYWORLD_FFMPEG)."""
import base64, io, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
FONT = ROOT / "fonts" / "Inter.ttf"          # SIL Open Font License, fonts/OFL.txt
W, H = 576, 1024


def templates():
    """Templates a user can pick: a folder with template.json and an approved step-A keyframe."""
    return sorted(d.name for d in TEMPLATES_DIR.iterdir() if (d / "template.json").exists() and (d / "keyframe_A.png").exists())


def closeup_sets():
    return sorted(p.stem for p in (TEMPLATES_DIR / "closeups").glob("*.json"))


def load_template(name):
    return json.loads((TEMPLATES_DIR / name / "template.json").read_text())


# ---------- photo facts (a local or cloud vision model reads the photo) ----------
FIELDS = {
    "storefront": "shop_type, storeys, facade (color + material), roof (shape, color, chimneys), upper_windows, sign (shape, color, border, lettering color; do NOT repeat the words), awning (color, pattern), shop_windows (what is displayed), door (color, style), pavement_items, neighbours",
    "product-pedestal": "product_type, shape, size_proportions, main_colors, materials_finish, label (layout, colors; do NOT repeat brand words), cap_or_lid, distinctive_details",
    "house": "storeys, walls (color + material), roof (shape, color, chimneys), windows (count, frame color), front_door (color, style), porch, front_garden, fence",
    "car": "body_type, paint_color, finish, wheels (rim color, style), lights, trim, distinctive_details (never the license plate or brand words)",
    "me": "hair (color, length, style), skin_tone, glasses, facial_hair, top (type, color, print), bottom (if visible), accessories (hat, earrings, chain, headphones)",
    "room": "wall_colors, desk, monitors (count, size), keyboard, pc (case, RGB colors), chair, lighting (color, type), bed, decor, plants",
}


def facts_prompt(template):
    kind = load_template(template).get("facts", template)
    return (f"Look at this photo and list only what is clearly visible. Return JSON with these keys: {FIELDS[kind]}, "
            "and copy_sentence: one sentence (max 70 words) listing the visible features an artist must copy to build a "
            "miniature model of it. " + ("Describe only the person's look: hair, glasses and clothes, never who they are or their name. Never the background, "
            if kind == "me" else "Describe only the building or product itself: never the surface it sits on, the background, ") +
            
            "the lighting, the camera or the photo style. Never include any brand name, shop name or written words from signs or labels. "
            "Return only JSON.")


def read_facts(jpeg_bytes, template, endpoint, model, timeout=900):
    """OpenAI-compatible chat endpoint with image input. Returns the facts dict (copy_sentence inside)."""
    img = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()
    body = {"model": model, "temperature": 0, "max_tokens": 900,
            "messages": [{"role": "user", "content": [{"type": "text", "text": facts_prompt(template)},
                                                      {"type": "image_url", "image_url": {"url": img}}]}]}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("TINYWORLD_VISION_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["TINYWORLD_VISION_KEY"]
    raw = json.load(urllib.request.urlopen(urllib.request.Request(endpoint, json.dumps(body).encode(), headers), timeout=timeout))
    text = raw["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", text, re.S)
    facts = json.loads(m.group(0)) if m else {"error": "no JSON in reply", "raw": text}
    facts["_model"] = raw.get("model")
    return facts


def pick_shape(template, facts):
    """Closest clay in the same family. Plain rules on the facts, so every pick can be explained."""
    txt = lambda k: json.dumps(facts.get(k, "")).lower()
    if template in ("storefront", "storefront-pitched2", "storefront-wide1"):
        if any(w in txt("storeys") for w in ("1", "one", "single")): return "storefront-wide1"
        if any(w in txt("roof") for w in ("gable", "pitched", "hipped", "slope", "tile")): return "storefront-pitched2"
        return "storefront"
    if template in ("product-pedestal", "product-jar"):
        p = txt("shape") + txt("size_proportions")
        return "product-jar" if any(w in p for w in ("wider than", "short", "squat", "jar", "tin", "round and low")) else "product-pedestal"
    return template


# ---------- final cut ----------
def ffmpeg():
    return os.environ.get("TINYWORLD_FFMPEG") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def _run(*args):
    subprocess.run([ffmpeg(), "-v", "error", "-y", *map(str, args)], check=True)


def duration(path):
    probe = shutil.which("ffprobe") or str(Path(ffmpeg()).with_name("ffprobe"))
    return float(subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True, check=True).stdout)


def has_audio(path):
    probe = shutil.which("ffprobe") or str(Path(ffmpeg()).with_name("ffprobe"))
    return "audio" in subprocess.run([probe, "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                                     capture_output=True, text=True).stdout


def _font(size):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name("Bold")
    return f


def title_png(name, out):
    """Shop name on a soft dark gradient band in the lower third (reads over busy footage)."""
    from PIL import Image, ImageDraw, ImageFilter
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    size = 54
    while d0.textlength(name, font=_font(size)) > W - 64 and size > 30: size -= 2
    font = _font(size)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("L", (1, 256))
    for i in range(256): band.putpixel((0, i), int(140 * (i / 255) ** 1.6))
    band = band.resize((W, int(H * 0.36)))
    img.paste((0, 0, 0, 255), (0, H - band.height), band)
    x, y = (W - d0.textlength(name, font=font)) / 2, H * 0.80
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x, y + 3), name, font=font, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(4)))
    ImageDraw.Draw(img).text((x, y), name, font=font, fill=(255, 255, 255, 255))
    img.save(out)


def endcard_png(name, line, background, out, credit=True):
    """Name + one call-to-action line over a blurred, darkened frame."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    img = ImageEnhance.Brightness(Image.open(background).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(18))).enhance(0.45)
    d = ImageDraw.Draw(img)
    def fit(text, size, maxw):
        while d.textlength(text, font=_font(size)) > maxw and size > 24: size -= 2
        return _font(size)
    fn, fl = fit(name, 64, W - 64), fit(line, 30, W - 96)
    d.text(((W - d.textlength(name, font=fn)) / 2, H * 0.43), name, font=fn, fill=(255, 255, 255))
    d.text(((W - d.textlength(line, font=fl)) / 2, H * 0.43 + fn.size + 28), line, font=fl, fill=(235, 225, 210))
    if credit:   # every shared video points back to the free app
        fc = _font(20); t = "made with Tiny World"
        d.text(((W - d.textlength(t, font=fc)) / 2, H - 70), t, font=fc, fill=(200, 192, 180))
    img.save(out)


def hook_png(text, out):
    """Big opening caption for the first second and a half (TikTok decides in the first second)."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    words, lines, size = text.split(), [], 46
    font = _font(size)
    for w in words:   # wrap to the frame width
        if lines and d.textlength(lines[-1] + " " + w, font=font) <= W - 80: lines[-1] += " " + w
        else: lines.append(w)
    y = H * 0.14
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for i, l in enumerate(lines):
        x = (W - d.textlength(l, font=font)) / 2
        ds.text((x, y + i * 56 + 4), l, font=font, fill=(0, 0, 0, 200)); d.text((x, y + i * 56), l, font=font, fill=(255, 255, 255, 255))
    Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), img).save(out)


V = f"fps=24,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p,settb=AVTB"


def ending(reveal, closeups, name, line, out, bpm=105, tmp=None, credit=True):
    """Reveal -> zoom through the door (0.5 s) -> 3 close-ups, 2 beats each -> end card (2.3 s).
    Two passes: one graph with both xfades dropped the end card."""
    tmp = Path(tmp or tempfile.mkdtemp())
    beat2 = round(120 / bpm, 3); rd = duration(reveal)
    _run("-sseof", "-0.1", "-i", closeups[2], "-frames:v", "1", "-update", "1", tmp / "last.png")
    endcard_png(name, line, tmp / "last.png", tmp / "card.png", credit)
    _run("-loop", "1", "-framerate", "24", "-t", "2.3", "-i", tmp / "card.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", tmp / "card.mp4")
    fc = (f"[0:v]{V}[r];[1:v]{V},trim=0:{beat2 + 0.5},setpts=PTS-STARTPTS[c1];[2:v]{V},trim=0:{beat2},setpts=PTS-STARTPTS[c2];"
          f"[3:v]{V},trim=0:{beat2 + 0.3},setpts=PTS-STARTPTS[c3];"
          f"[r][c1]xfade=transition=zoomin:duration=0.5:offset={round(rd - 0.5, 3)}[x1];[x1][c2][c3]concat=n=3:v=1:a=0[v]")
    _run("-i", reveal, "-i", closeups[0], "-i", closeups[1], "-i", closeups[2], "-filter_complex", fc, "-map", "[v]",
         "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", tmp / "body.mp4")
    bd = duration(tmp / "body.mp4")
    fc = f"[0:v]{V}[b];[1:v]{V}[e];[b][e]xfade=transition=fade:duration=0.3:offset={round(bd - 0.3, 3)}[v];"
    fc += f"[2:a]aresample=48000,apad=whole_dur={round(bd + 2.0, 3)}[a]" if has_audio(reveal) else f"anullsrc=r=48000:cl=stereo,atrim=0:{round(bd + 2.0, 3)}[a]"
    _run("-i", tmp / "body.mp4", "-i", tmp / "card.mp4", "-i", reveal, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", out)
    return rd


def box_title_png(name, out, window_bottom=None):
    """The collector-box label: the name as a crisp title (never generated text) over the box's blank band."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    t1, t2 = name.upper(), "COLLECTOR EDITION  ·  1:64 SCALE"
    s1 = 50
    while d.textlength(t1, font=_font(s1)) > W - 90 and s1 > 26: s1 -= 2
    f1, f2 = _font(s1), _font(20)
    y = int(H * 0.80)          # low on the box, clear of the hook caption at the top
    if window_bottom:          # a label straddling the bottom edge of the box window
        y = int(min(H - s1 - 70, max(H * 0.55, window_bottom - (s1 + 32) / 2)))
    w = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2)) + 56
    d.rounded_rectangle(((W - w) / 2, y - 14, (W + w) / 2, y + s1 + 46), radius=14, fill=(20, 18, 16, 225))
    d.text(((W - d.textlength(t1, font=f1)) / 2, y), t1, font=f1, fill=(255, 214, 92, 255))
    d.text(((W - d.textlength(t2, font=f2)) / 2, y + s1 + 10), t2, font=f2, fill=(240, 232, 220, 255))
    img.save(out)



def window_mask(still):
    """The flat green window of an intro still (box window / inside of the globe) as an L mask, or None if Qwen missed it."""
    from PIL import Image, ImageFilter
    im = still.convert("RGB"); px = im.load(); w, h = im.size
    m = Image.new("L", (w, h)); mp = m.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if g > 110 and g > r + 50 and g > b + 50: mp[x, y] = 255
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))       # close small holes
    box = m.getbbox()
    # a real window is one big flat green area; a small patch means Qwen drew the diorama itself (skip, never show two)
    if not box or sum(m.histogram()[128:]) < 0.12 * w * h: return None
    return m


def intro_window(still_path, film, out, kind="box", seconds=2.5, title=""):
    """One tiny world, not two: the fly-throughs own first frame is placed in the intro stills green window, then an
    exact camera push dives through the window and lands on that frame, so the cut into the fly-through is seamless.
    Returns False (and writes nothing) when the still has no usable green window."""
    import math, random
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    still = Image.open(still_path).convert("RGB").resize((W, H), Image.LANCZOS)
    m = window_mask(still)
    if m is None: return False
    tmp = Path(tempfile.mkdtemp(prefix="tw_intro_"))
    _run("-i", film, "-vf", V, "-frames:v", 1, tmp / "f0.png")
    f0 = Image.open(tmp / "f0.png").convert("RGB")
    x0, y0, x1, y1 = m.getbbox(); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rw = max(x1 - x0, (y1 - y0) * W / H); rh = rw * H / W             # 9:16 rectangle around the window
    R = (cx - rw / 2, cy - rh / 2, rw, rh)
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    layer.paste(f0.resize((round(rw), round(rh)), Image.LANCZOS), (round(R[0]), round(R[1])))
    soft = m.filter(ImageFilter.GaussianBlur(1.5))
    if kind == "box":   # a faint diagonal sheen on the plastic window
        sheen = Image.new("L", (W, H)); d = ImageDraw.Draw(sheen)
        d.polygon([(x0 + 0.15 * rw, y0), (x0 + 0.35 * rw, y0), (x0 - 0.05 * rw, y1), (x0 - 0.25 * rw, y1)], fill=38)
        layer = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), layer, ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(18)), m))
    comp = Image.composite(layer, still, soft)
    if title:   # the name printed on the box: it moves with the box as the camera pushes in
        box_title_png(title, tmp / "label.png", y1); lab = Image.open(tmp / "label.png"); comp.paste(lab, (0, 0), lab)
    n = int(seconds * 24); hold = 6; blend = 9
    flakes = [(random.Random(i).uniform(x0, x1), random.Random(i + 99).uniform(y0, y1), random.Random(i + 7).uniform(1.2, 3.2)) for i in range(70)]
    for i in range(n):
        t = max(0.0, (i - hold) / (n - 1 - hold)); e = t * t * (3 - 2 * t)
        z = math.exp(math.log(rw / W) * e)                                 # crop width / W, log-eased push
        cw, ch = W * z, H * z
        px, py = 0 + (R[0] - 0) * e, 0 + (R[1] - 0) * e
        fr = comp
        if kind == "globe":   # snow drifting inside the glass
            fr = comp.copy(); d = ImageDraw.Draw(fr); fm = m.load()
            for fx, fy, r in flakes:
                yy = y0 + (fy - y0 + i * 1.6 * r) % max(1, y1 - y0); xx = fx + 4 * math.sin(i / 9 + fy)
                if 0 <= xx < W and 0 <= yy < H and fm[int(xx), int(yy)]: d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=(250, 250, 255))
        view = fr.crop((round(px), round(py), round(px + cw), round(py + ch))).resize((W, H), Image.LANCZOS)
        k = i - (n - blend)
        if k >= 0: view = Image.blend(view, f0, (k + 1) / blend)        # the window frame melts away into the film
        view.save(tmp / f"i{i:03d}.png")
    _run("-framerate", 24, "-i", tmp / "i%03d.png", "-vf", V, "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", out)
    comp.save(Path(out).with_suffix(".png")); Path(out).with_suffix(".json").write_text(json.dumps({"window": [x0, y0, x1, y1]}))
    return True


MORPH_FADE = 0.15   # the morph ends on the reveal's first frame, so a very short fade is enough


def with_beats(film, tmp, intro=None, cutaways=(), cut_at=3.5, intro_title="", seamless=False, morph=None, bobble=None, bobble_at=1.3):
    """Fun-layer beats around the fly-through: intro (collector box / snow globe) zooms into the first frame; cutaways (giant
    guest, tiny-me figurine) interrupt the crane at cut_at s, then the flight resumes. Returns a film that already ends where
    the door zoom starts (+0.8 s overlap) and the time of that zoom. With morph (an LTX first+last-frame clip from the miniature
    to the real photo) the rest of the flight and the door zoom are replaced by the morph, which ends on the reveal's first frame."""
    tmp = Path(tmp); fd = duration(film)
    end = round(fd - 0.6, 3)                               # same cut point as before: 1.4 s early, + 0.8 s for the zoom overlap
    parts, n = [], 0
    def seg(src, a, b, name):
        p = tmp / f"{name}.mp4"
        _run("-ss", a, "-t", round(b - a, 3), "-i", src, "-vf", V, "-an", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", p)
        return p
    f0_end = cut_at if (cutaways or morph) else end
    if bobble and bobble_at < f0_end:   # the flight pauses on the figurine, its head springs, the flight goes on
        parts += [seg(film, 0, bobble_at, "f0a"), seg(bobble, 0, duration(bobble), "bob"), seg(film, bobble_at, f0_end, "f0")]
    else:
        parts.append(seg(film, 0, f0_end, "f0"))
    for i, c in enumerate(cutaways):
        parts.append(seg(c, 0, min(duration(c), 2.4), f"c{i}"))
    if morph: parts.append(seg(morph, 0, duration(morph), "m"))
    elif cutaways: parts.append(seg(film, cut_at, end, "f1"))
    body = tmp / "beats_body.mp4"
    (tmp / "beats.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    _run("-f", "concat", "-safe", "0", "-i", tmp / "beats.txt", "-c", "copy", body)
    if intro:   # the intro pushes in, then zooms into the tiny world
        idur = min(duration(intro), 2.5)
        pre = tmp / "beats_pre.mp4"
        lab_in, lab_fc = [], ""
        if intro_title:   # name label on the box for the intro, fading out as the camera dives in
            wj = Path(intro).with_suffix(".json")
            box_title_png(intro_title, tmp / "boxtitle.png", json.loads(wj.read_text())["window"][3] if wj.exists() else None)
            lab_in = ["-loop", "1", "-t", idur, "-i", tmp / "boxtitle.png"]
            lab_fc = f"[2:v]format=rgba,fade=t=out:st={round(idur - 0.8, 3)}:d=0.4:alpha=1[lb];[i][lb]overlay=0:0[i2];"
        _run("-t", idur, "-i", intro, "-i", body, *lab_in, "-filter_complex",
             f"[0:v]{V}[i];[1:v]{V}[b];{lab_fc}[{'i2' if intro_title else 'i'}][b]xfade=transition={'fade' if seamless else 'zoomin'}:duration={0.08 if seamless else 0.5}:offset={round(idur - (0.08 if seamless else 0.5), 3)}[v]",
             "-map", "[v]", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", pre)
        body = pre
    return body, round(duration(body) - (MORPH_FADE if morph else 0.8), 3)


def whoosh_filter(at, idx):
    """A soft synthesised whoosh (filtered noise, no third-party audio) for the door zoom."""
    ms = int(at * 1000)
    return (f"anoisesrc=d=0.9:c=pink:a=0.6:r=48000,highpass=f=250,lowpass=f=3500,afade=t=in:d=0.45,afade=t=out:st=0.45:d=0.45,"
            f"volume=0.55,aformat=channel_layouts=stereo,adelay={ms}|{ms}[wh{idx}]")


def loop_tail(src, first_frame, out):
    """Loop-friendly ending: the last half second dissolves back to the opening frame, so an auto-looping feed flows on."""
    tmpc = Path(out).with_suffix(".loop.mp4")
    _run("-loop", "1", "-framerate", "24", "-t", "0.7", "-i", first_frame, "-c:v", "libx264", "-pix_fmt", "yuv420p", tmpc)
    d = duration(src)
    _run("-i", src, "-i", tmpc, "-filter_complex",
         f"[0:v]{V}[a];[1:v]{V}[b];[a][b]xfade=transition=fade:duration=0.5:offset={round(d - 0.3, 3)}[v];[0:a]apad=whole_dur={round(d + 0.4, 3)}[au]",
         "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out)
    tmpc.unlink(missing_ok=True)


def stop_motion(src, out, fps=12):
    """Handmade stop-motion feel: every frame held twice (12 fps on a 24 fps timeline). Only the tiny part gets it."""
    _run("-i", src, "-vf", f"fps={fps},fps=24", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", "-c:a", "copy", out)
    return out


BOBBLE_AT = 1.3   # seconds into the fly-through: the camera is still in front of the figurine


def bobble_clip(film, tmp, at=BOBBLE_AT):
    """The bobblehead moment: grab the fly-through frame at `at` s and spring the figurine's head on its neck
    (tools/bobble.py, OpenCV, no GPU). Returns the clip, or None if no head was found."""
    tmp = Path(tmp); still = tmp / "bobble_still.png"
    _run("-ss", at, "-i", film, "-frames:v", 1, still)
    try:
        subprocess.run([sys.executable, str(Path(__file__).parent / "tools" / "bobble.py"), "--still", str(still),
                        "--out", str(tmp / "bobble.mp4")], check=True)
        return tmp / "bobble.mp4"
    except Exception as e:
        print(f"[Tiny World] bobble skipped: {e}"); return None


def final_cut(film, reveal, name, out, music=None, title_out=None, tmp=None, hook="", intro=None, cutaways=(), whoosh=True, loop=True,
              intro_title="", seamless=False, morph=None, music_drop=None, music_beat=0.5, stopmo=False, bobble=False):
    """Fly-through -> zoom into the reveal -> name title; music under the whole cut, reveal ambience at 45 %, -14 LUFS.
    The cut starts 1.4 s before the film ends: the last doorway frames tend to blow out."""
    tmp = Path(tmp or tempfile.mkdtemp())
    title_png(name, tmp / "title.png")
    if stopmo:   # the tiny world moves like a handmade stop-motion film; the morph and the real part stay smooth
        film = stop_motion(film, tmp / "film_sm.mp4")
        cutaways = [stop_motion(c, tmp / f"cut_sm{i}.mp4") for i, c in enumerate(cutaways)]
    bob = bobble_clip(film, tmp) if bobble else None
    if intro or cutaways or morph or bob:
        film, off = with_beats(film, tmp, intro, list(cutaways), intro_title=intro_title, seamless=seamless, morph=morph, bobble=bob)
    else:
        off = round(duration(film) - 1.4, 3)
    tf = f",fade=t=out:st={off + title_out}:d=0.3:alpha=1" if title_out is not None else ""
    fc = (f"[0:v]fps=24,format=yuv420p,setsar=1[a];[1:v]fps=24,scale={W}:{H},format=yuv420p,setsar=1[b];"
          f"[a][b]xfade=transition={'fade' if morph else 'zoomin'}:duration={MORPH_FADE if morph else 0.8}:offset={off}[v];"
          f"[2:v]format=rgba,fade=t=in:st={off + 0.6}:d=0.4:alpha=1{tf}[t];[v][t]overlay=0:0:shortest=1[vt];")
    fc += (f"anullsrc=r=48000:cl=stereo,atrim=0:{off}[sil];[1:a]aresample=48000,afade=t=in:d=0.3[ra];[sil][ra]concat=n=2:v=0:a=1[amb]"
           if has_audio(reveal) else f"anullsrc=r=48000:cl=stereo,atrim=0:{off + duration(reveal)}[amb]")
    inputs = ["-i", film, "-i", reveal, "-loop", "1", "-i", tmp / "title.png"]
    vout = "[vt]"
    if hook:
        hook_png(hook, tmp / "hook.png")
        inputs += ["-loop", "1", "-i", tmp / "hook.png"]
        fc += ";[3:v]format=rgba,fade=t=out:st=1.4:d=0.3:alpha=1[hk];[vt][hk]overlay=0:0:shortest=1[vh]"
        vout = "[vh]"
    mi = 4 if hook else 3
    if music:
        total = round(off + duration(reveal), 3)
        inputs += ["-i", music]
        wh = (";" + whoosh_filter(max(0, off - 0.25), 0)) if whoosh else ""
        # the drop lands on the reveal: trim the start of the track, or (drop before the reveal) repeat its first beats,
        # cut on a whole beat so the splice stays on the groove
        ms, pre = 0, 0
        if music_drop:
            ms = round(max(0.0, music_drop - off), 3)
            if music_drop < off: pre = round(round((off - music_drop) / music_beat) * music_beat, 3)
        src = (f"[{mi}:a]aresample=48000,asplit[mA][mB];[mA]atrim=0:{pre},asetpts=PTS-STARTPTS[mpre];[mB]asetpts=PTS-STARTPTS[mfull];"
               f"[mpre][mfull]concat=n=2:v=0:a=1,") if pre else f"[{mi}:a]aresample=48000,"
        fc += (f";{src}atrim={ms}:{ms + total},asetpts=PTS-STARTPTS,afade=t=out:st={total - 0.6}:d=0.6[mus];[amb]volume=0.45[amb2]{wh};"
               f"[mus][amb2]{'[wh0]' if whoosh else ''}amix=inputs={3 if whoosh else 2}:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[aout]")
    else:
        fc += ";[amb]anull[aout]"
    cut = tmp / "cut_noloop.mp4" if loop else out
    _run(*inputs, "-filter_complex", fc, "-map", vout, "-map", "[aout]", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", cut)
    if loop:
        _run("-i", film, "-frames:v", "1", "-update", "1", tmp / "first.png")
        loop_tail(cut, tmp / "first.png", out)
    return out


def jpeg_bytes(pil_image, longest=1024):
    im = pil_image.convert("RGB"); im.thumbnail((longest, longest))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90); return buf.getvalue()


def layout_score(a, b):
    """Gate E: does a miniature keep the template's layout? Edge-map correlation at 144x256 (good 0.89-0.95, broken < 0.3)."""
    import numpy as np
    from PIL import ImageFilter
    def edges(im):
        g = im.convert("L").resize((144, 256)).filter(ImageFilter.GaussianBlur(2))
        x = np.asarray(g, float); gx = np.abs(np.diff(x, axis=1))[:-1]; gy = np.abs(np.diff(x, axis=0))[:, :-1]
        from PIL import Image
        e = np.asarray(Image.fromarray((gx + gy).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), float)
        return (e - e.mean()) / (e.std() + 1e-6)
    return float((edges(a) * edges(b)).mean())


# ---------- Any Object: photo -> 3D mesh (TripoSR) -> Blender clay camera video ----------
OBJECT_SCENES = {"town square (any object)": ("product.py", ["mesh"], "object"), "garage (cars)": ("garage.py", [], "car")}


def blender():
    return os.environ.get("TINYWORLD_BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"


def object_clay(photo, scene, out):
    """The user's own object becomes the clay: TripoSR mesh from the photo, placed in the scene so the side it was
    photographed from faces the last camera position. Returns (clay.mp4, first_frame.png, template name)."""
    import platform
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    tri = Path(os.environ.get("TINYWORLD_TRIPOSR", Path.home() / "tools/TripoSR"))
    py = tri / ".venv/bin/python"
    device = "mps" if platform.system() == "Darwin" else "cuda:0"
    subprocess.run([str(py if py.exists() else "python3"), "run.py", str(photo), "--device", device, "--mc-resolution", "256",
                    "--output-dir", str(out / "tri")], cwd=tri, check=True)
    mesh = out / "tri" / "0" / "mesh.obj"
    script, args, template = OBJECT_SCENES[scene]
    clay = out / "clay"
    subprocess.run([blender(), "-b", "-P", str(ROOT / "blender" / script), "--", str(clay), *args, str(mesh)], check=True,
                   stdout=subprocess.DEVNULL)
    _run("-framerate", "24", "-i", clay / "clay_frames" / "f_%04d.png", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", clay / "clay.mp4")
    return clay / "clay.mp4", clay / "first_frame.png", template
