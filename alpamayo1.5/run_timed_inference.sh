#!/usr/bin/env bash
set -euo pipefail

cd /mnt/g/alpamayo1.5
. a1_5_venv/bin/activate

python -m py_compile /mnt/g/alpamayo1.5/timed_inference.py /mnt/g/alpamayo1.5/src/alpamayo1_5/models/alpamayo1_5.py
python -c 'import flash_attn; print("flash_attn_ok", flash_attn.__file__)'

HF_HOME=/mnt/g/hf HF_TOKEN="$(cat ~/.cache/huggingface/token)" \
  python -u /mnt/g/alpamayo1.5/timed_inference.py "$@"
