#!/usr/bin/env bash
# One command for the whole pipeline: transcribe -> validate -> render.
# Usage:  ./make_cuts.sh <PROJECT_DIR> [extra render flags, e.g. --burn]
#
# Runs in two passes (choosing the cuts sits in the middle -- it needs judgement):
#   1st pass: transcribe. If cuts.tsv has no cuts yet, stop and tell you.
#   2nd pass (after you fill cuts.tsv): validate + render everything.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  echo "Usage: ./make_cuts.sh <PROJECT_DIR> [render flags, e.g. --burn]"
  exit 1
fi
shift || true
CUTS="$HERE/cuts.tsv"

echo "==================== 1/3  TRANSCRIBE ===================="
"$HERE/transcribe.sh" "$DIR"

# Count the cuts already defined in cuts.tsv (skip comments, blank lines, header).
rows=0
[[ -f "$CUTS" ]] && rows=$(grep -vE '^[[:space:]]*#' "$CUTS" | grep -vE '^[[:space:]]*$' | tail -n +2 | wc -l | tr -d ' ')
if [[ "${rows:-0}" -eq 0 ]]; then
  echo
  echo ">>> Transcripts ready. Now CHOOSE THE CUTS:"
  echo "    - fill  $CUTS"
  echo "      (columns: ep source start end title quote theme why score cx segments)"
  echo "    - read each .txt to pick the best moments (see criteria.md)"
  echo "    Then run this same command again to validate + render."
  exit 0
fi

echo
echo "==================== 2/3  VALIDATE ($rows cuts) ===================="
python3 "$HERE/validate.py" --dir "$DIR"

echo
echo "==================== 3/3  RENDER ===================="
python3 "$HERE/render.py" --dir "$DIR" ${@+"$@"}

echo
echo "==================== DONE ===================="
echo "Output per episode: $DIR/EPxx/{horizontal, vertical} + EPxx_cuts.docx"
