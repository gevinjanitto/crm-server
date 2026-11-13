#!/usr/bin/env bash
# Memulihkan deploy/.env dari container yang masih berjalan (nilai env tersimpan di container).
# Pemakaian: sudo bash deploy/restore-env.sh
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && { echo "deploy/.env sudah ada, tidak diubah."; exit 0; }
P=crm-maiharta
cid() { docker ps -aq --filter "label=com.docker.compose.project=$P" --filter "label=com.docker.compose.service=$1" | head -1; }
envof() { local c; c="$(cid "$1")"; [ -n "$c" ] && docker inspect "$c" --format '{{range .Config.Env}}{{println .}}{{end}}'; }
BACK="$(envof backend || true)"; DB="$(envof mysql || true)"; WEB="$(envof web || true)"
[ -n "$BACK" ] || { echo "Container backend tidak ditemukan, .env tidak bisa dipulihkan otomatis. Cek /root/crm-maiharta.env, deploy/.env.bak.* atau backup Google Drive."; exit 1; }
get() { printf '%s\n' "$2" | grep -E "^$1=" | head -1 | cut -d= -f2- || true; }
SKIP='^(PATH|LANG|GPG_KEY|HOME|HOSTNAME|PYTHON_[A-Z_]*|PIP_[A-Z_]*|PYTHONUNBUFFERED|PYTHONDONTWRITEBYTECODE|MYSQL_HOST|MYSQL_PORT|UPLOAD_DIR|CORS_ORIGINS|APP_URL)='
{
  echo "SERVER_IP=$(get SERVER_IP "$WEB")"
  echo "APP_DOMAIN=$(get APP_DOMAIN "$WEB")"
  echo "MYSQL_ROOT_PASSWORD=$(get MYSQL_ROOT_PASSWORD "$DB")"
  echo "TIMEZONE=Asia/Makassar"
  printf '%s\n' "$BACK" | grep -E '^[A-Z][A-Z0-9_]*=' | grep -Ev "$SKIP"
} > .env
chmod 600 .env
cp .env /root/crm-maiharta.env && chmod 600 /root/crm-maiharta.env
echo "deploy/.env dipulihkan ($(grep -c = .env) variabel) dan disalin ke /root/crm-maiharta.env"
grep -E '^(APP_DOMAIN|SERVER_IP|ADMIN_EMAIL)=' .env
grep -Eq '^MYSQL_ROOT_PASSWORD=.+' .env || echo "PERINGATAN: MYSQL_ROOT_PASSWORD kosong, isi manual."
grep -Eq '^APP_DOMAIN=.+' .env || echo "PERINGATAN: APP_DOMAIN kosong, isi manual (contoh: portal.maiharta.com)."
