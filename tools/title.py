"""Render the shop-name title as a transparent 576x1024 PNG: lower third, on a soft dark gradient band so it reads over
busy footage (passers-by, bright shop fronts).
python title.py "<Shop name>" out.png [font_path]"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

name, out = sys.argv[1], sys.argv[2]
font_path = sys.argv[3] if len(sys.argv) > 3 else "/System/Library/Fonts/Avenir Next.ttc"
W, H = 576, 1024
size = 54
font = ImageFont.truetype(font_path, size, index=0)
while ImageDraw.Draw(Image.new("L", (1, 1))).textlength(name, font=font) > W - 64 and size > 30:
    size -= 2; font = ImageFont.truetype(font_path, size, index=0)
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
band = Image.new("L", (1, 256))
for i in range(256):                          # transparent at the top of the band, ~55% black at the bottom
    band.putpixel((0, i), int(140 * (i / 255) ** 1.6))
band = band.resize((W, int(H * 0.36)))
img.paste((0, 0, 0, 255), (0, H - band.height), band)
d = ImageDraw.Draw(img)
tw = d.textlength(name, font=font)
x, y = (W - tw) / 2, H * 0.80
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shadow).text((x, y + 3), name, font=font, fill=(0, 0, 0, 170))
img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(4)))
ImageDraw.Draw(img).text((x, y), name, font=font, fill=(255, 255, 255, 255))
img.save(out)
