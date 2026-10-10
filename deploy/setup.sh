#!/usr/bin/env bash
# Instalasi sekali jalan CRM Maiharta di VPS IDCloudHost (Ubuntu 22.04/24.04).
# Pemakaian: sudo bash deploy/setup.sh [IP_PUBLIK]
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then echo "Jalankan dengan sudo / sebagai root."; exit 1; fi

IP="${1:-$(curl -4 -fsS https://api.ipify.org || hostname -I | awk '{print $1}')}"
echo "==> IP server: $IP"

echo "==> Instal paket dasar & Docker"
apt-get update -y
apt-get install -y ca-certificates curl git openssl ufw
if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi
systemctl enable --now docker

if ! swapon --show | grep -q .; then
  echo "==> Membuat swap 2GB (agar build frontend tidak kehabisan RAM)"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Firewall: buka SSH, HTTP, HTTPS, n8n (5678), WAHA (3000)"
ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null
ufw allow 5678/tcp >/dev/null; ufw allow 3000/tcp >/dev/null
ufw --force enable >/dev/null

if [ ! -f .env ]; then
  echo "==> Membuat deploy/.env dengan password acak"
  rnd() { openssl rand -hex "${1:-24}"; }
  while true; do
    ADMIN_EMAIL=""
    read -r -p "Email admin (untuk login awal & sertifikat SSL) [cvmaiharta@gmail.com]: " ADMIN_EMAIL || true
    ADMIN_EMAIL="$(printf '%s' "${ADMIN_EMAIL:-cvmaiharta@gmail.com}" | tr -d '[:space:]')"
    [[ "$ADMIN_EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] && break
    echo "Email tidak valid. Ketik ulang tanpa tombol panah, atau langsung Enter untuk memakai email bawaan."
  done
  cat > .env <<EOF
SERVER_IP=${IP}
APP_DOMAIN=${IP}
N8N_DOMAIN=${IP}:5678
WAHA_DOMAIN=${IP}:3000
ADMIN_EMAIL=${ADMIN_EMAIL}
TIMEZONE=Asia/Makassar
MYSQL_DATABASE=crm_maiharta
MYSQL_USER=crm
MYSQL_PASSWORD=$(rnd 16)
MYSQL_ROOT_PASSWORD=$(rnd 16)
JWT_SECRET=$(rnd 32)
SEED_PASSWORD=Mh-$(rnd 6)
WEBHOOK_CRON_SECRET=$(rnd 24)
N8N_ENCRYPTION_KEY=$(rnd 24)
N8N_WAHA_WEBHOOK_SECRET=$(rnd 24)
WAHA_API_KEY=$(rnd 20)
WAHA_DASHBOARD_PASSWORD=$(rnd 8)
WAHA_ENGINE=WEBJS
MAIL_SENDER_NAME=CRM Maiharta
EMAIL_ENABLED=false
N8N_EMAIL_WEBHOOK_URL=
WHATSAPP_ENABLED=false
N8N_WAHA_WEBHOOK_URL=
RECAPTCHA_SITE_KEY=
RECAPTCHA_SECRET_KEY=
EOF
  chmod 600 .env
else
  echo "==> deploy/.env sudah ada, dipakai apa adanya"
fi

echo "==> Build & jalankan semua layanan (pertama kali bisa 10-20 menit)"
docker compose up -d --build

set -a; . ./.env; set +a
cat <<EOF

================= SELESAI =================
CRM      : https://${APP_DOMAIN}
           login: admin / ${SEED_PASSWORD}   (ganti setelah login)
n8n      : https://${N8N_DOMAIN}   (buat akun owner saat pertama dibuka)
WAHA     : https://${WAHA_DOMAIN}/dashboard
           login: admin / ${WAHA_DASHBOARD_PASSWORD}
           API key: ${WAHA_API_KEY}
Secret webhook CRM <-> n8n (X-CRM-Webhook-Secret): ${N8N_WAHA_WEBHOOK_SECRET}
Semua nilai di atas tersimpan di: $(pwd)/.env
Sertifikat HTTPS dibuat otomatis, tunggu 1-2 menit bila browser masih menolak.
===========================================
EOF
