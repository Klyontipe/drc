#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

# Charge .env si présent
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"

if [ "${DEBUG:-false}" = "true" ]; then
  echo "Mode développement (Flask)"
  .venv/bin/python app.py
else
  echo "Mode production (gunicorn, ${WORKERS} worker(s), port ${PORT})"
  .venv/bin/gunicorn -w "${WORKERS}" -b "0.0.0.0:${PORT}" --timeout 120 app:app
fi
