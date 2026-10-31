#!/usr/bin/env bash
# Ganti alamat CRM: IP server ATAU domain.
# Pakai IP    : sudo bash deploy/change-domain.sh IP_SERVER            -> CRM https://IP
# Pakai domain: sudo bash deploy/change-domain.sh maihartacrm.duckdns.org -> CRM https://domain
set -euo pipefail
cd "$(dirname "$0")"
BASE="${1:?Pemakaian: sudo bash deploy/change-domain.sh IP_SERVER_atau_domain}"
BASE="${BASE#http://}"; BASE="${BASE#https://}"; BASE="${BASE%%/*}"
[ -f .env ] || { echo "deploy/.env belum ada. Jalankan dulu: sudo bash deploy/setup.sh"; exit 1; }
SERVER_IP="$(grep -E '^SERVER_IP=' .env | cut -d= -f2)"
ADMIN_EMAIL="$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2-)"
if ! [[ "$ADMIN_EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
  echo "ADMIN_EMAIL di deploy/.env tidak valid (dibutuhkan untuk sertifikat HTTPS). Perbaiki dengan:"
  echo "  sudo sed -i 's/^ADMIN_EMAIL=.*/ADMIN_EMAIL=emailanda@gmail.com/' $(pwd)/.env"
  exit 1
fi

if [[ "$BASE" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  if [ "$BASE" != "$SERVER_IP" ]; then
    sed -i -E "s|^SERVER_IP=.*|SERVER_IP=${BASE}|" .env
    echo "SERVER_IP diubah dari ${SERVER_IP} menjadi ${BASE}"
  fi
else
  got="$(getent ahostsv4 "$BASE" | awk 'NR==1{print $1}' || true)"
  if [ "$got" != "$SERVER_IP" ]; then
    echo "PERINGATAN: $BASE mengarah ke '${got:-tidak ditemukan}', seharusnya $SERVER_IP."
    echo "Atur dulu DNS/IP di DuckDNS (atau DNS domain Anda), tunggu 1-5 menit, lalu ulangi."
    exit 1
  fi
fi

cp .env ".env.bak.$(date +%Y%m%d%H%M%S)"
sed -i -E "s|^APP_DOMAIN=.*|APP_DOMAIN=${BASE}|" .env

echo "==> Alamat diganti. Build ulang frontend & restart layanan (3-10 menit)"
docker compose up -d --build --remove-orphans web backend

cat <<EOF

================= SELESAI =================
CRM  : https://${BASE}
Sertifikat HTTPS dibuat otomatis, tunggu 1-2 menit lalu buka di browser.
===========================================
EOF
