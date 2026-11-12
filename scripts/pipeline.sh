#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG=${CONFIG:-config/camera-glass.json}
PROXY_FPS=5

usage() {
  cat <<EOF
Usage: scripts/rc <command> VIDEO [args]

  probe    VIDEO                  codec, resolution, fps, keyframe interval
  prepare  VIDEO [AUDIO]          proxy 360p@${PROXY_FPS}fps + audio 16 kHz mono
  signals  VIDEO                  motion/shake/scoreboard/audio features
  segment  VIDEO                  detect rallies, score, evaluate vs scoreboard, plots
  export   VIDEO [--all]          top-N clips + reel (--all: every rally + clean match)
  sheet    VIDEO START DUR [FPS]  contact sheet from the proxy (START in seconds)
  inspect  VIDEO                  motion/audio features per interval of labels.csv
  sweep    VIDEO [TOP]            grid-search segment params against labels.csv
  all      VIDEO [AUDIO]          prepare + signals + segment
  run      VIDEO [AUDIO] [--all]  end to end: all + export
  test     [PYTEST ARGS]          run the test suite

Outputs go to <video dir>/work. Camera config: CONFIG=$CONFIG
EOF
  exit 1
}

work_dir() { echo "$(dirname "$1")/work"; }

has_audio() {
  [ -n "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$1")" ]
}

probe() {
  ffprobe -v error -show_entries \
    format=duration,size,bit_rate:stream=codec_type,codec_name,profile,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels \
    -of compact "$1"
  echo "keyframes (first 60 s):"
  ffprobe -v error -select_streams v:0 -read_intervals %+60 \
    -show_entries packet=pts_time,flags -of csv=p=0 "$1" | awk -F, '$2 ~ /K/ {printf "%s ", $1}'
  echo
}

camera_maker() {
  local tags
  tags=$(ffprobe -v error -show_entries format_tags:stream_tags -of default=nw=1 "$1" | tr '[:upper:]' '[:lower:]')
  case $tags in
    *gopro*) echo gopro ;;
    *dji*)   echo dji ;;
    *)       echo unknown ;;
  esac
}

# Log footage (GoPro GP-Log, DJI D-Log M) needs the maker's LUT; configured in $CONFIG under "luts".
lut_for() {
  local lut
  lut=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("luts", {}).get(sys.argv[2], ""))' "$CONFIG" "$1")
  if [ -n "$lut" ] && [ ! -f "$lut" ]; then
    echo "warning: LUT for $1 not found at $lut, continuing without color conversion" >&2
    lut=""
  fi
  echo "$lut"
}

prepare() {
  local video=$1 audio=${2:-$1} work audio_json=null maker lut lut_json=null vf
  work=$(work_dir "$video")
  mkdir -p "$work"
  maker=$(camera_maker "$video")
  lut=$(lut_for "$maker")
  vf="fps=$PROXY_FPS,scale=640:-2"
  if [ -n "$lut" ]; then
    vf="lut3d=$lut,$vf"
    lut_json="\"$lut\""
  fi
  echo "camera: $maker | LUT: ${lut:-none}"
  ffmpeg -v error -y -i "$video" -vf "$vf" -an -pix_fmt yuv420p \
    -c:v libx264 -crf 23 -preset veryfast -g "$PROXY_FPS" "$work/proxy.mp4"
  if has_audio "$audio"; then
    ffmpeg -v error -y -i "$audio" -vn -ac 1 -ar 16000 "$work/audio16k.wav"
    audio_json="\"$audio\""
  else
    rm -f "$work/audio16k.wav"
    echo "no audio track: motion-only analysis"
  fi
  printf '{"video": "%s", "audio": %s, "camera": "%s", "lut": %s}\n' \
    "$video" "$audio_json" "$maker" "$lut_json" > "$work/meta.json"
  echo "prepared $work"
}

sheet() {
  local video=$1 start=$2 dur=$3 fps=${4:-1} work rows
  work=$(work_dir "$video")
  rows=$(( (dur * fps + 4) / 5 ))
  ffmpeg -v error -y -ss "$start" -t "$dur" -i "$work/proxy.mp4" \
    -vf "fps=$fps,scale=320:-1,tile=5x$rows" -frames:v 1 "$work/sheet_${start}s.jpg"
  echo "$work/sheet_${start}s.jpg"
}

run_py() { uv run -q "scripts/$1.py" "$(work_dir "$2")" "$CONFIG" "${@:3}"; }

run_all() {
  local export_flag="" args=()
  for arg in "$@"; do
    if [ "$arg" = --all ]; then export_flag=--all; else args+=("$arg"); fi
  done
  prepare "${args[@]}"
  run_py signals "${args[0]}"
  run_py segment "${args[0]}"
  run_py export "${args[0]}" $export_flag
}

run_tests() {
  uv run -q --with pytest --with numpy --with scipy --with opencv-python-headless --with matplotlib \
    pytest -q tests "$@"
}

[ "${1:-}" = test ] && { shift; run_tests "$@"; exit; }
[ $# -ge 2 ] || usage
cmd=$1; shift
case $cmd in
  probe)   probe "$@" ;;
  prepare) prepare "$@" ;;
  signals) run_py signals "$@" ;;
  segment) run_py segment "$@" ;;
  export)  run_py export "$@" ;;
  sheet)   sheet "$@" ;;
  inspect) run_py inspect_labels "$@" ;;
  sweep)   run_py sweep "$@" ;;
  all)     prepare "$@" && run_py signals "$1" && run_py segment "$1" ;;
  run)     run_all "$@" ;;
  *)       usage ;;
esac
