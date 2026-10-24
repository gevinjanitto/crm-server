#!/usr/bin/env bash
# CRM Maiharta - setup lokal: membuat ulang seluruh file project lalu menginstal dependensi.
# Pemakaian: bash setup.sh [folder_tujuan]   (default: ./crm-server)
set -e
TARGET="${1:-crm-server}"
[ -n "$(ls -A "$TARGET" 2>/dev/null)" ] && echo "Folder '$TARGET' sudah ada: file project akan ditimpa (.env & node_modules tetap)."
mkdir -p "$TARGET"
echo "==> Mengekstrak file project ke $TARGET ..."
ARCHIVE_LINE=$(awk '/^__ARCHIVE_BELOW__$/ {print NR + 1; exit 0}' "$0")
tail -n +"$ARCHIVE_LINE" "$0" | base64 -d 2>/dev/null | tar -xz -C "$TARGET" --strip-components=1 \
  || tail -n +"$ARCHIVE_LINE" "$0" | base64 --decode | tar -xz -C "$TARGET" --strip-components=1
cd "$TARGET"
[ -f backend/.env ] || cat > backend/.env <<'ENV'
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
MYSQL_USER="crm"
MYSQL_PASSWORD="crmpass"
MYSQL_DATABASE="crm_maiharta"
UPLOAD_DIR="./uploads"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="ganti-dengan-string-acak-panjang"
SEED_PASSWORD="Maiharta2026!"
ADMIN_EMAIL="admin@example.com"
APP_URL="http://localhost:3000"
EMAIL_ENABLED="false"
WHATSAPP_ENABLED="false"
AI_ENABLED="true"
AI_BASE_URL="https://ai.sumopod.com/v1"
AI_MODEL="gpt-4o-mini"
AI_API_KEY=""
ENV
[ -f frontend/.env ] || cat > frontend/.env <<'ENV'
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_CONTACT_EMAIL=cvmaiharta@gmail.com
REACT_APP_CONTACT_COMPOSE_URL=https://mail.google.com/mail/
ENV
PY=""
for c in "py -3" python python3; do
  if $c -c "import sys; assert sys.version_info >= (3, 9)" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then
  echo "==> Membuat virtualenv backend dan menginstal requirements ..."
  $PY -m venv backend/.venv
  VBIN=bin; [ -d backend/.venv/Scripts ] && VBIN=Scripts
  backend/.venv/$VBIN/python -m pip install --upgrade pip
  backend/.venv/$VBIN/python -m pip install -r backend/requirements.txt
else
  echo "!! Python 3.9+ tidak ditemukan (di Windows, 'python3' bisa jadi hanya shortcut Microsoft Store)."
  echo "   Instal Python 3.11 dari https://www.python.org/downloads/ (centang 'Add python.exe to PATH'),"
  echo "   buka terminal baru, lalu jalankan lagi: bash setup.sh"
fi
if command -v yarn >/dev/null 2>&1; then
  echo "==> Menginstal dependensi frontend (yarn) ..."
  (cd frontend && yarn install)
else
  echo "!! yarn tidak ditemukan. Instal Node.js 18/20 + yarn (npm i -g yarn), lalu: cd frontend && yarn install"
fi
cat <<'DONE'

==> Selesai.
Langkah berikutnya:
  1. Siapkan MySQL/MariaDB lokal, buat database & user sesuai backend/.env, contoh:
       CREATE DATABASE crm_maiharta CHARACTER SET utf8mb4;
       CREATE USER 'crm'@'localhost' IDENTIFIED BY 'crmpass';
       CREATE USER 'crm'@'127.0.0.1' IDENTIFIED BY 'crmpass';
       GRANT ALL ON crm_maiharta.* TO 'crm'@'localhost';
       GRANT ALL ON crm_maiharta.* TO 'crm'@'127.0.0.1';
  2. Jalankan: bash start-local.sh   (Windows: start-local.bat)
  3. Buka http://localhost:3000 - login: admin / adminproject / developer dengan password SEED_PASSWORD (default Maiharta2026!)
DONE
exit 0
