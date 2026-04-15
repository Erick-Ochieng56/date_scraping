#!/usr/bin/env bash
# Build the Vite app, run Django on :8000, and start ngrok (free tier).
# Run from repo root:  bash scripts/start_ngrok_stack.sh
# On Windows in PowerShell, use:  scripts/start_ngrok_stack.ps1
# Prerequisites: Node/npm, Python deps, ngrok authtoken (`ngrok config add-authtoken`).
#
# Optional: activate your venv first, e.g.
#   source source/venv/Scripts/activate   # Git Bash on Windows
#   source .venv/bin/activate             # Linux/macOS
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT/source/venv/Scripts/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/source/venv/Scripts/activate"
elif [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

cd "$ROOT/frontend"
npm run build

cd "$ROOT/backend"
export DJANGO_SERVE_SPA="${DJANGO_SERVE_SPA:-1}"
export DJANGO_DISABLE_CORS="${DJANGO_DISABLE_CORS:-1}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"
export DJANGO_USE_X_FORWARDED_HOST="${DJANGO_USE_X_FORWARDED_HOST:-1}"
export DJANGO_BEHIND_HTTPS_PROXY="${DJANGO_BEHIND_HTTPS_PROXY:-1}"

cleanup() {
  [[ -n "${DJANGO_PID:-}" ]] && kill "$DJANGO_PID" 2>/dev/null || true
  [[ -n "${NGROK_PID:-}" ]] && kill "$NGROK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python manage.py runserver 8000 &
DJANGO_PID=$!
echo "Django: http://127.0.0.1:8000 (PID $DJANGO_PID)"
sleep 2

ngrok http 8000 --log=stdout &
NGROK_PID=$!
echo "ngrok PID: $NGROK_PID (local inspector: http://127.0.0.1:4040)"
sleep 3

echo ""
echo "=== Public ngrok URL(s) ==="
# Avoid mktemp + file: Git Bash mktemp lives under /tmp; Windows Python cannot open that path.
if TUNNEL_JSON="$(curl -fsS "http://127.0.0.1:4040/api/tunnels" 2>/dev/null)"; then
  printf '%s\n' "$TUNNEL_JSON" | python -c 'import json,sys; d=json.load(sys.stdin); [print(t.get("public_url") or "") for t in d.get("tunnels") or [] if t.get("public_url")]'
else
  echo "(Could not query ngrok local API — open http://127.0.0.1:4040 for the public URL.)"
fi
echo ""
echo "If browser POSTs fail CSRF, set in backend/.env (then restart):"
echo "  DJANGO_CSRF_TRUSTED_ORIGINS=https://YOUR-SUBDOMAIN.ngrok-free.dev"
echo "  (or .ngrok-free.app — match the host ngrok prints)"
echo ""
echo "Press Ctrl+C to stop Django and ngrok."
wait
