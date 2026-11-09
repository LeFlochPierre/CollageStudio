#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [[ ! -f ".venv/bin/python" ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python app.py
