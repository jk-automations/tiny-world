"""End card: the shop name and one call-to-action line over a blurred, darkened frame. 576x1024 PNG.
python endcard.py "<Shop name>" "<line>" background.png out.png [font_path]"""
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
name, line, bg, out = sys.argv[1:5]
font_path = sys.argv[5] if len(sys.argv) > 5 else "/System/Library/Fonts/Avenir Next.ttc"   # demo only; ship an OFL font
W, H = 576, 1024
img = Image.open(bg).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(18))
img = ImageEnhance.Brightness(img).enhance(0.45)
d = ImageDraw.Draw(img)
def fit(text, size, idx, maxw):
    f = ImageFont.truetype(font_path, size, index=idx)
    while d.textlength(text, font=f) > maxw and size > 24:
        size -= 2; f = ImageFont.truetype(font_path, size, index=idx)
    return f
fn, fl = fit(name, 64, 0, W - 64), fit(line, 30, 0, W - 96)
d.text(((W - d.textlength(name, font=fn)) / 2, H * 0.43), name, font=fn, fill=(255, 255, 255))
d.text(((W - d.textlength(line, font=fl)) / 2, H * 0.43 + fn.size + 28), line, font=fl, fill=(235, 225, 210))
img.save(out)
