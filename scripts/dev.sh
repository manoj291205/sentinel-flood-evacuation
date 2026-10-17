#!/usr/bin/env bash
# Start the Sentinel V4 console for development.
#   scripts/dev.sh          API on :8000 + console on :5173
#   scripts/dev.sh --mock   console only on :5173, answered by the in-browser mock (VITE_API_MOCK=1)
set -euo pipefail
cd "$(dirname "$0")/.."

MOCK=0
[ "${1:-}" = "--mock" ] && MOCK=1

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js >= 20 is required (https://nodejs.org)." >&2; exit 1
fi
if [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  echo "Node.js >= 20 is required; found $(node -v)." >&2; exit 1
fi
if [ "$MOCK" -eq 0 ]; then
  PY=".venv/bin/python"; [ -x "$PY" ] || PY=".venv/Scripts/python"
  if [ ! -x "$PY" ]; then
    echo "No .venv found. Create it: python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-api.txt" >&2; exit 1
  fi
fi
if [ ! -d web/node_modules ]; then
  (cd web && npm ci)
fi

PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if [ "$MOCK" -eq 1 ]; then
  echo "Console (mock API): http://127.0.0.1:5173"
  cd web && VITE_API_MOCK=1 npm run dev
else
  "$PY" -m uvicorn src.api.app:create_app --factory --port 8000 --reload &
  PIDS+=($!)
  echo "API:     http://127.0.0.1:8000"
  echo "Console: http://127.0.0.1:5173"
  (cd web && npm run dev) &
  PIDS+=($!)
  wait
fi
