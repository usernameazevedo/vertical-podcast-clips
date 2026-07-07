#!/usr/bin/env bash
# Help find the WIDE two-shot segments in a multicam clip, so you can feed their
# time ranges to reframe.py --wide.
#
# It runs scene detection to get the camera-cut points, prints the resulting
# segments, and (unless --no-sheet) writes a contact sheet with one frame per
# segment so you can eyeball which ones are the wide two-shot.
#
# Usage:  ./find_wides.sh <clip.mp4> [threshold] [--no-sheet]
#         threshold default 0.3 (lower = more cuts detected)
#
# Then pick the wide segments and run, e.g.:
#   reframe.py clip.mp4 out.mp4 --closeup 0.52 --split 0.30,0.82 --wide 16.9-23.5
set -euo pipefail
FF="${FFMPEG:-ffmpeg}"; FP="${FFPROBE:-ffprobe}"

IN="${1:?usage: find_wides.sh <clip.mp4> [threshold] [--no-sheet]}"
THR="${2:-0.3}"; [[ "$THR" == --* ]] && THR="0.3"
SHEET=1; [[ "${2:-}" == "--no-sheet" || "${3:-}" == "--no-sheet" ]] && SHEET=0

DURATION=$("$FP" -v error -show_entries format=duration -of csv=p=0 "$IN")
echo "clip: $(basename "$IN")  (${DURATION%.*}s)"

# scene-change timestamps
mapfile -t CUTS < <("$FF" -i "$IN" -filter_complex "select='gt(scene,${THR})',metadata=print:file=-" \
  -an -f null - 2>/dev/null | awk -F'pts_time:' '/pts_time/{printf "%.1f\n",$2}')

echo "camera cuts: ${CUTS[*]:-none}"
echo "segments (start-end):"
prev=0
mids=()
for c in "${CUTS[@]}"; do
  awk "BEGIN{exit !($c-$prev>0.1)}" && { printf "  %.1f-%.1f\n" "$prev" "$c"; mids+=( "$(awk "BEGIN{print ($prev+$c)/2}")" ); }
  prev="$c"
done
printf "  %.1f-%.1f\n" "$prev" "$DURATION"; mids+=( "$(awk "BEGIN{print ($prev+$DURATION)/2}")" )

if [[ "$SHEET" == 1 ]]; then
  sheet="${IN%.*}_segments.jpg"
  tmp="$(mktemp -d)"; i=1
  for t in "${mids[@]}"; do
    "$FF" -y -ss "$t" -i "$IN" -frames:v 1 -vf scale=320:-1 "$tmp/$(printf '%02d' $i).jpg" -loglevel error
    i=$((i+1))
  done
  cols=${#mids[@]}
  "$FF" -y -framerate 1 -i "$tmp/%02d.jpg" -vf "tile=${cols}x1" -frames:v 1 "$sheet" -loglevel error
  rm -rf "$tmp"
  echo "contact sheet (1 frame per segment): $sheet"
  echo "-> the wide two-shot segments show BOTH people small + the background; feed those to --wide."
fi
