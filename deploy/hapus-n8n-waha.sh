#!/usr/bin/env bash
# Hapus n8n + WAHA dari server lama (container, image, volume, port firewall) dan tambahkan variabel GMAIL_*/TWILIO_* ke deploy/.env.
# Data CRM (MySQL, file upload, sertifikat HTTPS) TIDAK disentuh. Backup n8n & WAHA dibuat dulu ke deploy/backups/.
# Pemakaian: sudo bash deploy/hapus-n8n-waha.sh
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then echo "Jalankan dengan sudo."; exit 1; fi
[ -f .env ] || { echo "deploy/.env belum ada."; exit 1; }

read -r -p "Hapus n8n + WAHA beserta datanya dari server ini? Ketik YA untuk lanjut: " OK || true
[ "${OK:-}" = "YA" ] || { echo "Dibatalkan."; exit 0; }

OUT="backups/sebelum-hapus-n8n-waha-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
echo "==> Backup terakhir volume n8n & WAHA ke deploy/$OUT"
for vol in n8n_data waha_sessions waha_media; do
  if docker volume inspect "crm-maiharta_${vol}" >/dev/null 2>&1; then
    docker run --rm -v "crm-maiharta_${vol}:/data:ro" -v "$(pwd)/$OUT:/out" alpine tar czf "/out/${vol}.tar.gz" -C /data . || true
  fi
done
cp .env "$OUT/env.txt"

echo "==> Hentikan & hapus container n8n / WAHA"
for c in $(docker ps -a --filter "label=com.docker.compose.project=crm-maiharta" --format '{{.Names}}' | grep -E 'n8n|waha' || true); do
  docker rm -f "$c" >/dev/null && echo "    dihapus: $c"
done

echo "==> Hapus volume n8n / WAHA"
for vol in n8n_data waha_sessions waha_media; do
  docker volume rm "crm-maiharta_${vol}" >/dev/null 2>&1 && echo "    dihapus: crm-maiharta_${vol}" || true
done

echo "==> Hapus image n8n / WAHA"
docker image rm docker.n8n.io/n8nio/n8n:latest devlikeapro/waha:latest >/dev/null 2>&1 || true

echo "==> Tutup port 5678 & 3000 di firewall"
if command -v ufw >/dev/null 2>&1; then ufw delete allow 5678/tcp >/dev/null 2>&1 || true; ufw delete allow 3000/tcp >/dev/null 2>&1 || true; fi

echo "==> Rapikan deploy/.env (variabel n8n/WAHA dihapus, variabel Gmail API & WhatsApp API ditambahkan)"
sed -i -E '/^(N8N_DOMAIN|WAHA_DOMAIN|N8N_ENCRYPTION_KEY|N8N_WAHA_WEBHOOK_SECRET|N8N_EMAIL_WEBHOOK_URL|N8N_WAHA_WEBHOOK_URL|WAHA_API_KEY|WAHA_DASHBOARD_PASSWORD|WAHA_ENGINE)=/d' .env
for kv in GMAIL_CLIENT_ID= GMAIL_CLIENT_SECRET= GMAIL_REFRESH_TOKEN= GMAIL_SENDER= TWILIO_ACCOUNT_SID= TWILIO_AUTH_TOKEN= TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 TWILIO_CONTENT_SID=; do
  grep -q "^${kv%%=*}=" .env || echo "$kv" >> .env
done
sed -i -E 's/^EMAIL_ENABLED=.*/EMAIL_ENABLED=false/; s/^WHATSAPP_ENABLED=.*/WHATSAPP_ENABLED=false/' .env

echo "==> Jalankan ulang CRM tanpa n8n/WAHA"
docker compose up -d --remove-orphans
docker image prune -f >/dev/null || true
docker compose ps --format "table {{.Service}}\t{{.Status}}"
cat <<EOF

================= SELESAI =================
n8n & WAHA sudah dihapus. Backup terakhirnya: $(pwd)/$OUT
Langkah berikutnya: isi GMAIL_* dan WA_* di $(pwd)/.env (sudo nano .env),
set EMAIL_ENABLED=true / WHATSAPP_ENABLED=true, lalu: sudo docker compose up -d backend
Panduan lengkap: DEPLOY_IDCLOUDHOST.md langkah 6 & 7.
===========================================
EOF
