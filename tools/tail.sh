#!/bin/zsh
# Ending after the reveal: reveal -> zoom through the door (0.5 s) -> 3 close-ups cut on the beat -> end card (2.3 s).
# tail.sh <reveal.mp4> <closeup1> <closeup2> <closeup3> "<Shop name>" "<line>" <out.mp4> [bpm]
# Two passes: one ffmpeg graph with both xfades left the end card off (video stopped at the second xfade's offset).
set -e
export PATH=/opt/homebrew/bin:$PATH
R=$1; C1=$2; C2=$3; C3=$4; NAME=$5; LINE=$6; OUT=$7; BPM=${8:-105}
BEAT2=$(python3 -c "print(round(120/$BPM, 3))")      # each close-up = 2 beats
RD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$R")
TMP=$(mktemp -d)
ffmpeg -v error -y -sseof -0.1 -i "$C3" -frames:v 1 -update 1 $TMP/last.png
~/ComfyUI/venv/bin/python $(dirname $0)/endcard.py "$NAME" "$LINE" $TMP/last.png $TMP/card.png
ffmpeg -v error -y -loop 1 -framerate 24 -t 2.3 -i $TMP/card.png -c:v libx264 -pix_fmt yuv420p $TMP/card.mp4
V="fps=24,scale=576:1024:force_original_aspect_ratio=increase,crop=576:1024,setsar=1,format=yuv420p,settb=AVTB"
# pass 1: reveal -> zoom -> close-ups (video only)
FC="[0:v]${V}[r];[1:v]${V},trim=0:$(python3 -c "print($BEAT2+0.5)"),setpts=PTS-STARTPTS[c1];"
FC+="[2:v]${V},trim=0:$BEAT2,setpts=PTS-STARTPTS[c2];[3:v]${V},trim=0:$(python3 -c "print($BEAT2+0.3)"),setpts=PTS-STARTPTS[c3];"
FC+="[r][c1]xfade=transition=zoomin:duration=0.5:offset=$(python3 -c "print(round($RD-0.5,3))")[x1];[x1][c2][c3]concat=n=3:v=1:a=0[v]"
ffmpeg -v error -y -i "$R" -i "$C1" -i "$C2" -i "$C3" -filter_complex "$FC" -map "[v]" -c:v libx264 -crf 15 -pix_fmt yuv420p $TMP/body.mp4
# pass 2: fade into the end card; the reveal's ambience runs on under it, padded with silence
BD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $TMP/body.mp4)
FC="[0:v]${V}[b];[1:v]${V}[e];[b][e]xfade=transition=fade:duration=0.3:offset=$(python3 -c "print(round($BD-0.3,3))")[v];"
FC+="[2:a]aresample=48000,apad=whole_dur=$(python3 -c "print(round($BD+2.0,3))")[a]"
ffmpeg -v error -y -i $TMP/body.mp4 -i $TMP/card.mp4 -i "$R" -filter_complex "$FC" -map "[v]" -map "[a]" -c:v libx264 -crf 17 -pix_fmt yuv420p -c:a aac "$OUT"
rm -rf $TMP
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT"
