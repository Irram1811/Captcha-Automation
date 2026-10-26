#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH=src:.
mkdir -p runs
lsof -t -iTCP:8765 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
python -m fixtures.server --port 8765 > runs/server.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do
  curl -sf "http://127.0.0.1:8765/slider.html?seed=1" > /dev/null && break
  sleep 0.5
done
for url in "slider.html?seed=1" "assets/slider_bg.png?seed=1" "assets/slider_piece.png?seed=1" "imagegrid.html?seed=1" "checkbox.html" "none.html"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8765/$url")
  echo "$code  $url"
done
python -m captcha_agent run-all --mode deterministic || true
python scripts/measure_rates.py --widget all --runs 20
cat runs/rates.md
cat runs/summary.md
