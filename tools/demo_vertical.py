"""Vertical (9:16, 1080x1920) Tiny World demo, edited like a TikTok: hard cuts on the beat, big captions that slide in.
Only edits finished clips and stills; nothing is generated here. Shot list: docs/demo_vertical.json.
python3 tools/demo_vertical.py docs/demo_vertical.json runs/demo/tiny-world-demo-v2.mp4"""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinyworld_core as core
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
spec_path, out = Path(sys.argv[1]), Path(sys.argv[2])
spec = json.loads(spec_path.read_text())
root = spec_path.resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="tw_vdemo_"))
BEAT = 60 / spec.get("bpm", 105)
FF = core.ffmpeg()


def ff(*a):
    subprocess.run([FF, "-v", "error", "-y", *map(str, a)], check=True)


def src(p):
    return p if p.startswith("/") else str(root / p)


def caption_png(text, size, path, tag=False, bg=False):
    """Big bold caption with a soft shadow; tag=True is the small 'AI-made demo' / 'real photo' corner label."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lines = text.split("\n")
    s = size
    while max(d.textlength(l, font=core._font(s)) for l in lines) > W - 120 and s > 36: s -= 4
    f = core._font(s)
    lh = int(s * 1.12); h = lh * len(lines)
    y0 = 0
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for i, l in enumerate(lines):
        x = (W - d.textlength(l, font=f)) / 2
        ds.text((x, y0 + i * lh + 6), l, font=f, fill=(0, 0, 0, 190))
        d.text((x, y0 + i * lh), l, font=f, fill=(255, 255, 255, 255) if not tag else (255, 255, 255, 215))
    im = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), im)
    if bg:   # dark rounded backing so the caption reads over busy screen UI
        tw = max(d.textlength(l, font=f) for l in lines)
        back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(back).rounded_rectangle(((W - tw) / 2 - 36, -14, (W + tw) / 2 + 36, h + 18), radius=28, fill=(18, 16, 14, 225))
        im = Image.alpha_composite(back, im)
    im = im.crop((0, 0, W, h + 40)); im.save(path)
    return h + 40


def base_clip(s, path):
    """The picture under the captions: a 9:16 clip, a still with a slow push-in, a 16:9 screen in the top 60 %, or a card."""
    dur = s["seconds"]; kind = s.get("type", "clip")
    if kind == "clip":
        speed = s.get("speed", 1.0); st = s.get("start", 0)
        ff("-ss", st, "-t", dur * speed, "-i", src(s["src"]), "-vf",
           (f"crop={s['crop']}," if s.get("crop") else "") +
           f"setpts=PTS/{speed},fps=24,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1" +
           (",eq=brightness=-0.18:saturation=0.8,gblur=sigma=6" if s.get("dim") else ""),
           "-an", "-t", dur, "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", path)
    elif kind == "split":   # two 9:16 clips side by side (e.g. Blender clay | finished video), same moment
        st = s.get("start", 0)
        ff("-ss", st, "-t", dur, "-i", src(s["src"]), "-ss", st, "-t", dur, "-i", src(s["src2"]),
           "-f", "lavfi", "-i", f"color=c=0x161412:s={W}x{H}:d={dur}:r=24", "-filter_complex",
           f"[0:v]fps=24,scale=520:924,setsar=1[a];[1:v]fps=24,scale=520:924,setsar=1[b];"
           f"[2:v][a]overlay=13:{int(H * 0.30)}[x];[x][b]overlay=547:{int(H * 0.30)}:shortest=1[v]",
           "-map", "[v]", "-t", dur, "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", path)
    elif kind == "photo":
        n = int(dur * 24)
        ff("-loop", "1", "-i", src(s["src"]), "-vf",
           f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
           f"zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=24,setsar=1",
           "-t", dur, "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", path)
    elif kind == "screen":   # a landscape screen recording or screenshot, framed in the top of a dark card
        speed = s.get("speed", 1.0); st = s.get("start", 0)
        inp = ["-loop", "1", "-i", src(s["src"])] if s["src"].endswith(".png") else ["-ss", st, "-t", dur * speed, "-i", src(s["src"])]
        ff(*inp, "-f", "lavfi", "-i", f"color=c=0x161412:s={W}x{H}:d={dur}:r=24", "-filter_complex",
           f"[0:v]setpts=PTS/{speed},fps=24,scale={W - 80}:-2[s];[1:v][s]overlay=40:{int(H * 0.30)}:shortest=1,setsar=1[v]",
           "-map", "[v]", "-t", dur, "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", path)
    else:   # card
        ff("-f", "lavfi", "-i", f"color=c=0x161412:s={W}x{H}:d={dur}:r=24", "-t", dur, "-c:v", "libx264", "-crf", "17",
           "-pix_fmt", "yuv420p", path)


parts = []
for i, s in enumerate(spec["shots"]):
    if "beats" in s: s["seconds"] = round(s["beats"] * BEAT, 3)
    b = tmp / f"b{i:02d}.mp4"; base_clip(s, b)
    inputs = ["-i", b]; fc = "[0:v]null[v0]"; last = "v0"
    caps = s.get("captions", [])
    if s.get("tag"): caps = caps + [{"text": s["tag"], "size": 34, "y": 0.93, "t0": 0, "t1": s["seconds"], "tag": True}]
    for k, c in enumerate(caps):
        png = tmp / f"c{i:02d}_{k}.png"; ch = caption_png(c["text"], c.get("size", 96), png, c.get("tag", False), c.get("bg", s.get("bg", False)))
        t0, t1 = c.get("t0", 0), c.get("t1", s["seconds"]); y = int(H * c.get("y", 0.12))
        inputs += ["-loop", "1", "-t", s["seconds"], "-i", png]
        slide = "" if c.get("tag") else f"-40*max(0,1-(t-{t0})/0.25)"      # slides up 40 px into place in 0.25 s
        fc += (f";[{k + 1}:v]format=rgba,fade=t=in:st={t0}:d=0.2:alpha=1,fade=t=out:st={max(t0, t1 - 0.15)}:d=0.15:alpha=1[c{k}]"
               f";[{last}][c{k}]overlay=0:'{y}{slide}':enable='between(t,{t0},{t1})'[v{k + 1}]")
        last = f"v{k + 1}"
    p = tmp / f"p{i:02d}.mp4"
    ff(*inputs, "-filter_complex", fc, "-map", f"[{last}]", "-t", s["seconds"], "-c:v", "libx264", "-crf", "17",
       "-pix_fmt", "yuv420p", "-r", "24", p)
    parts.append(p)

lst = tmp / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
body = tmp / "body.mp4"; ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", body)
total = core.duration(body)
out.parent.mkdir(parents=True, exist_ok=True)
lead = spec["shots"][0] if spec.get("lead_audio") else None   # the opening app video keeps its own soundtrack (drop on the reveal)
if lead:
    ld = lead["seconds"]
    mix = (f"[2:a]atrim={lead.get('start', 0)}:{lead.get('start', 0) + ld},asetpts=PTS-STARTPTS,aresample=48000,afade=t=out:st={ld - 0.4}:d=0.4[l];"
           f"[1:a]atrim=0:{total - ld},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.3[m];[l][m]concat=n=2:v=0:a=1,"
           f"afade=t=out:st={total - 1.2}:d=1.2,loudnorm=I=-14:TP=-1:LRA=11[a]")
else:
    mix = f"[1:a]atrim=0:{total},afade=t=out:st={total - 1.2}:d=1.2,loudnorm=I=-14:TP=-1:LRA=11[a]"
music = src(spec["music"])
if spec.get("music_loop"):   # loop only the full-energy part (generated tracks fade out at the end), cut on a whole beat
    L = round(int(spec["music_loop"] / BEAT) * BEAT, 3); music = tmp / "loop.wav"
    ff("-i", src(spec["music"]), "-af", f"atrim=0:{L},afade=t=in:d=0.02,afade=t=out:st={L - 0.04}:d=0.04", music)
ff("-i", body, "-stream_loop", "-1", "-i", music, *(["-i", src(lead["src"])] if lead else []), "-filter_complex",
   mix,
   "-map", "0:v", "-map", "[a]", "-t", total, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
print(f"{out} {total:.1f} s, {len(parts)} shots")
