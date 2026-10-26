#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
[ -d .venv ] || uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .
uv pip install pytest pytest-asyncio
python -m playwright install chromium
python fixtures/make_assets.py
python fixtures/make_grid_assets.py
python -m pytest -q
echo "BOOTSTRAP OK"
