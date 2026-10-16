#!/usr/bin/env bash
# CRM Maiharta - installer lokal: membuat ulang seluruh file project, instal dependency, siapkan database & .env.
# Pemakaian: bash setup.sh [FOLDER_TUJUAN]   (default: ./crm-server)
set -euo pipefail
TARGET="${1:-crm-server}"
echo "==> Mengekstrak project ke: $TARGET"
mkdir -p "$TARGET"
sed -n '/^__PAYLOAD_BELOW__$/,$p' "$0" | tail -n +2 | base64 -d | tar -xzf - -C "$TARGET"
cd "$TARGET"
ROOT="$(pwd)"

DB_USER="${DB_USER:-crm}"; DB_PASS="${DB_PASS:-crmpass}"; DB_NAME="${DB_NAME:-crm_maiharta}"
rand() { (openssl rand -hex 24 2>/dev/null || date +%s%N | sha256sum | cut -c1-48); }

if [ ! -f backend/.env ]; then
  echo "==> Membuat backend/.env untuk lokal"
  cat > backend/.env <<ENV
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
MYSQL_USER="$DB_USER"
MYSQL_PASSWORD="$DB_PASS"
MYSQL_DATABASE="$DB_NAME"
UPLOAD_DIR="$ROOT/backend/uploads"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="$(rand)"
SEED_PASSWORD="Maiharta123!"
ADMIN_EMAIL="admin@example.com"
APP_URL="http://localhost:3000"
EMAIL_ENABLED="false"
WHATSAPP_ENABLED="false"
ENV
fi
mkdir -p backend/uploads
if [ ! -f frontend/.env ]; then
  echo "==> Membuat frontend/.env untuk lokal"
  printf 'REACT_APP_BACKEND_URL=http://localhost:8001\nREACT_APP_CONTACT_EMAIL=cvmaiharta@gmail.com\nREACT_APP_CONTACT_COMPOSE_URL=https://mail.google.com/mail/\n' > frontend/.env
fi
[ -f deploy/.env ] || { [ -f deploy/.env.example ] && cp deploy/.env.example deploy/.env; }

echo "==> Menyiapkan database MySQL/MariaDB lokal"
SQL="CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
CREATE USER IF NOT EXISTS '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PASS';
GRANT ALL ON $DB_NAME.* TO '$DB_USER'@'localhost'; GRANT ALL ON $DB_NAME.* TO '$DB_USER'@'127.0.0.1'; FLUSH PRIVILEGES;"
if command -v mysql >/dev/null 2>&1; then
  (mysql -uroot -e "$SQL" 2>/dev/null || sudo mysql -uroot -e "$SQL" 2>/dev/null) && echo "    database $DB_NAME siap" \
    || echo "!! Gagal membuat database otomatis. Jalankan SQL ini sebagai root MySQL:"$'\n'"$SQL"
elif command -v docker >/dev/null 2>&1; then
  docker rm -f crm-mariadb >/dev/null 2>&1 || true
  docker run -d --name crm-mariadb -p 3306:3306 -e MARIADB_ROOT_PASSWORD="$(rand)" -e MARIADB_DATABASE="$DB_NAME" \
    -e MARIADB_USER="$DB_USER" -e MARIADB_PASSWORD="$DB_PASS" -v crm-mariadb-data:/var/lib/mysql mariadb:11 >/dev/null \
    && echo "    MariaDB berjalan di Docker (container crm-mariadb)"
else
  echo "!! MySQL/MariaDB maupun Docker tidak ditemukan. Instal MariaDB lalu jalankan ulang, atau buat manual:"$'\n'"$SQL"
fi

PY="$(command -v python3.11 || command -v python3 || true)"
if [ -n "$PY" ]; then
  echo "==> Instal dependency backend ($PY, venv: backend/.venv)"
  "$PY" -m venv backend/.venv
  backend/.venv/bin/pip install --upgrade pip
  backend/.venv/bin/pip install -r backend/requirements.txt
else
  echo "!! python3 tidak ditemukan, lewati instal backend"
fi

if ! command -v yarn >/dev/null 2>&1; then
  command -v corepack >/dev/null 2>&1 && corepack enable >/dev/null 2>&1 || true
  command -v yarn >/dev/null 2>&1 || { command -v npm >/dev/null 2>&1 && npm install -g yarn >/dev/null 2>&1 || true; }
fi
if command -v yarn >/dev/null 2>&1; then
  echo "==> Instal dependency frontend (yarn install)"
  (cd frontend && yarn install --network-timeout 600000)
else
  echo "!! yarn/Node.js tidak ditemukan. Instal Node.js 18/20 lalu: cd frontend && yarn install"
fi

cat > start-local.sh <<'RUN'
#!/usr/bin/env bash
cd "$(dirname "$0")"
(cd backend && .venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --reload) &
BACK=$!; trap 'kill $BACK' EXIT
cd frontend && yarn start
RUN
chmod +x start-local.sh

cat <<MSG

Selesai. Jalankan aplikasi: cd $TARGET && ./start-local.sh
  Frontend: http://localhost:3000   Backend: http://localhost:8001/api/health
  Login awal: admin / Maiharta123!  (SEED_PASSWORD di backend/.env, ganti setelah login)
  Deploy VPS (Docker): sudo bash deploy/setup.sh  (lihat DEPLOY_IDCLOUDHOST.md)
MSG
exit 0
__PAYLOAD_BELOW__
