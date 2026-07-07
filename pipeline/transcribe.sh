#!/usr/bin/env bash
# Batch-transcribe every episode in a folder with whisper.cpp. Produces .vtt + .txt.
# Prefers a light .mp3/.m4a/.wav over the big .mp4 when extracting audio, and skips
# anything that already has a .vtt.
#
# Usage:  ./transcribe.sh [DIR]           (default: current dir)
#
# Config via env vars (with sensible defaults):
#   WHISPER   path to whisper-cli   (default: ~/whisper.cpp/build/bin/whisper-cli
#                                    or ~/github.com/ggerganov/whisper.cpp/...)
#   MODEL     path to a ggml model  (default: medium next to whisper)
#   LANG      transcription language (default: en)
set -euo pipefail

DIR="${1:-$(pwd)}"
LANG="${LANG:-en}"

# Find whisper-cli: $WHISPER, then PATH, then common clone locations.
if [[ -z "${WHISPER:-}" ]]; then
  WHISPER="$(command -v whisper-cli || true)"
  for c in "$HOME/whisper.cpp/build/bin/whisper-cli" \
           "$HOME/github.com/ggerganov/whisper.cpp/build/bin/whisper-cli"; do
    [[ -x "$WHISPER" ]] && break; [[ -x "$c" ]] && WHISPER="$c"
  done
fi
if [[ -z "${MODEL:-}" ]]; then
  for c in "$HOME/whisper.cpp/models/ggml-medium.bin" \
           "$HOME/github.com/ggerganov/whisper.cpp/models/ggml-medium.bin"; do
    [[ -f "$c" ]] && MODEL="$c" && break
  done
fi

[[ -x "${WHISPER:-}" ]] || { echo "ERROR: whisper-cli not found. Set \$WHISPER."; exit 1; }
[[ -f "${MODEL:-}"   ]] || { echo "ERROR: model not found. Set \$MODEL."; exit 1; }

shopt -s nullglob
for f in "$DIR"/*.mp3 "$DIR"/*.m4a "$DIR"/*.wav "$DIR"/*.mp4 "$DIR"/*.mov; do
  base="${f%.*}"
  if [[ -f "$base.vtt" ]]; then
    echo "SKIP (already transcribed): $(basename "$base")"
    continue
  fi
  wav="$base.16k.wav"
  echo "-> extracting audio: $(basename "$f")"
  ffmpeg -y -i "$f" -ar 16000 -ac 1 -c:a pcm_s16le "$wav" -loglevel error
  echo "-> transcribing:     $(basename "$f")"
  "$WHISPER" -m "$MODEL" -l "$LANG" -f "$wav" -otxt -ovtt -of "$base" >/dev/null 2>&1
  rm -f "$wav"
  echo "OK: $(basename "$base").vtt / .txt"
done
echo "Done."
