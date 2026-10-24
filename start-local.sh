#!/usr/bin/env bash
# Menjalankan backend (port 8001) dan frontend (port 3000) di lokal. Linux/macOS/Git Bash Windows.
cd "$(dirname "$0")"
VBIN="bin"; [ -d backend/.venv/Scripts ] && VBIN="Scripts"
PY="backend/.venv/$VBIN/python"
[ -x "$PY" ] || [ -f "$PY.exe" ] || { echo "Virtualenv belum ada. Jalankan dulu: bash setup.sh"; exit 1; }
[ -d frontend/node_modules ] || { echo "node_modules belum ada. Jalankan: cd frontend && yarn install"; exit 1; }
(cd backend && ".venv/$VBIN/python" -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM
cd frontend && yarn start
