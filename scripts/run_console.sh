#!/usr/bin/env bash
# Serve the built React console and live API from one local process.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=""
for candidate in .venv-runtime/bin/python .venv-runtime/Scripts/python.exe .venv/bin/python .venv/Scripts/python.exe; do
  if [ -x "$candidate" ]; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "Create .venv-runtime with Python 3.12 and install requirements-runtime.txt plus requirements-api.txt (README.md)." >&2
  exit 1
fi
if [ ! -f web/dist/index.html ]; then
  echo "Build the console first: cd web && npm ci && npm run build" >&2
  exit 1
fi

export SENTINEL_WEB_DIST="$PWD/web/dist"
export HF_HUB_OFFLINE=1
export PYTHONDONTWRITEBYTECODE=1
echo "Sentinel console: http://127.0.0.1:${PORT:-8101}/live"
exec "$PY" -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port "${PORT:-8101}"
