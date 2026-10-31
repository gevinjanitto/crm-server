#!/usr/bin/env bash
# Membuat setup.sh (header scripts/setup_header.sh + arsip base64 seluruh file project, tanpa .env/rahasia/node_modules).
set -e
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
tar -cf - --exclude='./.git' --exclude='*/node_modules' --exclude='./frontend/build' --exclude='*/__pycache__' --exclude='*/.venv' \
  --exclude='./backend/.env' --exclude='./frontend/.env' --exclude='./backend/uploads' --exclude='./test_reports' --exclude='*/.ruff_cache' --exclude='./.ruff_cache' \
  --exclude='./setup.sh' --exclude='./frontend/public/setup.sh' --exclude='*.pyc' --exclude='./memory/test_credentials.md' . | tar -xf - -C "$TMP"
{ cat scripts/setup_header.sh; echo "__PAYLOAD_BELOW__"; tar -czf - -C "$TMP" . | base64; } > setup.sh
rm -rf "$TMP"
chmod +x setup.sh
cp setup.sh frontend/public/setup.sh
echo "setup.sh dibuat ($(du -h setup.sh | cut -f1)) dan disalin ke frontend/public/setup.sh"
