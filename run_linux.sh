#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Setting up PanelForge for the first time..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi
( sleep 2; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5000 >/dev/null 2>&1 || true ) &
echo "PanelForge is running at http://127.0.0.1:5000"
echo "Press Ctrl+C to stop."
exec .venv/bin/python app.py
