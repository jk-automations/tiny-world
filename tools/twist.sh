#!/bin/zsh
# "Plot twist" cut: starts on the REAL place, the camera pulls back out of the door, and it was a tiny model all along.
# Same renders as the normal cut, played in reverse (the figures never move, so reversed footage stays natural).
# twist.sh <film.mp4> <reveal.mp4> "<Name>" <out.mp4> [music.mp3] ["hook text"]
set -e
export PATH=/opt/homebrew/bin:$PATH
FILM=$1; REVEAL=$2; NAME=$3; OUT=$4; MUSIC=${5:-}; HOOK=${6:-}
TMP=$(mktemp -d)
FD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILM")
RD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$REVEAL")
CUT=$(python3 -c "print(round($FD - 1.4, 3))")             # skip the doorway frames that blow out, as in the normal cut
V="fps=24,scale=576:1024,setsar=1,format=yuv420p,settb=AVTB"
# Build the normal direction (tiny fly-through -> zoom into the door -> real), then reverse the whole thing:
# real pulls back out of the door, the zoom plays as a zoom-out, and the tiny world opens up to the wide diorama.
FC="[0:v]trim=0:${CUT},setpts=PTS-STARTPTS,${V}[t];[1:v]${V}[r];[t][r]xfade=transition=zoomin:duration=0.8:offset=$(python3 -c "print(round($CUT-0.8,3))"),reverse[v]"
ffmpeg -v error -y -i "$FILM" -i "$REVEAL" -filter_complex "$FC" -map "[v]" -an $TMP/rev.mp4
# hold the final wide shot 1.2 s so the reveal lands
ffmpeg -v error -y -i $TMP/rev.mp4 -vf "tpad=stop_mode=clone:stop_duration=1.2" $TMP/tiny_hold.mp4
~/ComfyUI/venv/bin/python $(dirname $0)/title.py "$NAME" $TMP/title.png
TOT=$(python3 -c "print(round($CUT + $RD - 0.8 + 1.2, 3))")
FC="[0:v]${V}[v];"
FC+="[1:v]format=rgba,fade=t=in:st=$(python3 -c "print(round($TOT-2.2,3))"):d=0.4:alpha=1[ti];[v][ti]overlay=0:0:shortest=1[vt]"
INPUTS=(-i $TMP/tiny_hold.mp4 -loop 1 -i $TMP/title.png)
if [ -n "$HOOK" ]; then   # optional hook caption over the first 1.6 s
  ~/ComfyUI/venv/bin/python -c "
import sys; from PIL import Image, ImageDraw, ImageFont
f = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 46, index=0); t = sys.argv[1]
im = Image.new('RGBA', (576, 1024), (0, 0, 0, 0)); d = ImageDraw.Draw(im); w = d.textlength(t, font=f)
d.text(((576 - w) / 2 + 2, 182), t, font=f, fill=(0, 0, 0, 160)); d.text(((576 - w) / 2, 180), t, font=f, fill=(255, 255, 255, 255)); im.save(sys.argv[2])" "$HOOK" $TMP/hook.png
  INPUTS+=(-loop 1 -i $TMP/hook.png)
  FC+=";[2:v]format=rgba,fade=t=out:st=1.3:d=0.3:alpha=1[hk];[vt][hk]overlay=0:0:shortest=1[vt2]"; VOUT="[vt2]"; AI=3
else
  VOUT="[vt]"; AI=2
fi
if [ -n "$MUSIC" ]; then
  INPUTS+=(-i "$MUSIC")
  FC+=";[${AI}:a]aresample=48000,atrim=0:${TOT},afade=t=out:st=$(python3 -c "print($TOT-0.6)"):d=0.6,loudnorm=I=-14:TP=-1:LRA=11[aout]"
  AMAP=(-map "[aout]" -c:a aac -b:a 192k)
else
  AMAP=()
fi
ffmpeg -v error -y "${INPUTS[@]}" -filter_complex "$FC" -map "$VOUT" "${AMAP[@]}" -t $TOT -c:v libx264 -crf 17 -pix_fmt yuv420p -movflags +faststart "$OUT"
rm -rf $TMP
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT"
