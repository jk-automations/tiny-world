#!/bin/zsh
# Final cut: fly-through -> zoom-through into the reveal clip -> name title. 576x1024, 24 fps.
# assemble.sh <film.mp4> <reveal.mp4> "<Shop name>" <out.mp4> [music.mp3] [title_out_seconds]
# With music: music runs the whole cut, reveal ambience sits under it, 0.6 s fade out, loudness -14 LUFS.
# TODO before public release: ship an OFL font in the repo (Avenir Next is a macOS system font, demo only).
set -e
export PATH=/opt/homebrew/bin:$PATH  # not a login shell: a login profile can change the working directory
FILM=$1; REVEAL=$2; NAME=$3; OUT=$4; MUSIC=${5:-}
TITLE_OUT=${6:-}   # optional: seconds after the cut when the title fades out (used when an ending follows the reveal)
TITLE=$(mktemp).png
~/ComfyUI/venv/bin/python $(dirname $0)/title.py "$NAME" $TITLE
FD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILM")
OFF=$(python3 -c "print(round($FD - 1.4, 3))")  # cut starts 1.4 s before the end; the last doorway frames tend to blow out
FC="[0:v]fps=24,format=yuv420p,setsar=1[a];[1:v]fps=24,scale=576:1024,format=yuv420p,setsar=1[b];"
FC+="[a][b]xfade=transition=zoomin:duration=0.8:offset=${OFF}[v];"
TF=""; [ -n "$TITLE_OUT" ] && TF=",fade=t=out:st=$(python3 -c "print($OFF+$TITLE_OUT)"):d=0.3:alpha=1"
FC+="[2:v]format=rgba,fade=t=in:st=$(python3 -c "print($OFF+0.6)"):d=0.4:alpha=1${TF}[t];[v][t]overlay=0:0:shortest=1[vt];"
FC+="anullsrc=r=48000:cl=stereo,atrim=0:${OFF}[sil];[1:a]aresample=48000,afade=t=in:d=0.3[ra];[sil][ra]concat=n=2:v=0:a=1[amb]"
INPUTS=(-i "$FILM" -i "$REVEAL" -loop 1 -i $TITLE)
if [ -n "$MUSIC" ]; then
  TOTAL=$(python3 -c "print(round($OFF + $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$REVEAL"), 3))")
  INPUTS+=(-i "$MUSIC")
  FC+=";[3:a]aresample=48000,atrim=0:${TOTAL},afade=t=out:st=$(python3 -c "print($TOTAL-0.6)"):d=0.6[mus];[amb]volume=0.45[amb2];[mus][amb2]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[aout]"
else
  FC+=";[amb]anull[aout]"
fi
ffmpeg -loglevel error -y "${INPUTS[@]}" -filter_complex "$FC" -map "[vt]" -map "[aout]" \
  -c:v libx264 -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
rm -f $TITLE
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT"
