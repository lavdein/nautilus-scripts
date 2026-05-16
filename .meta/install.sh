#!/usr/bin/env bash
# Installs Python venv for the Whisper transcription script.
# Run once after cloning, or after a system reinstall.
set -eo pipefail

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
WHISPER_DIR="$SCRIPT_DIR/Утилиты/.whisper"
VENV="$WHISPER_DIR/env"

echo "==> Creating virtual environment at $VENV"
python3 -m venv "$VENV"

echo "==> Installing faster-whisper (with CUDA support)"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install faster-whisper \
    nvidia-cublas-cu12 nvidia-cuda-nvrtc-cu12 nvidia-cudnn-cu12

echo ""
echo "Done. First run will download the selected Whisper model automatically."
echo "Models are cached in: $WHISPER_DIR/models/"
