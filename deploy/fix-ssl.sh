#!/usr/bin/env bash
# Perbaiki error Cloudflare 525 (SSL handshake failed) + tampilkan diagnosa.
# Pemakaian: sudo bash deploy/fix-ssl.sh portal.maiharta.com
set -uo pipefail
cd "$(dirname "$0")"
DOMAIN="${1:-portal.maiharta.com}"
[ -f .env ] || bash ./restore-env.sh || { echo "deploy/.env tidak ada dan tidak bisa dipulihkan."; exit 1; }
setv() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }
cp .env ".env.bak.$(date +%Y%m%d-%H%M%S)"
setv APP_DOMAIN "$DOMAIN"
setv CADDY_TLS_MODE internal
grep -q '^SERVER_IP=.\+' .env || setv SERVER_IP "$(curl -4 -s -m 8 https://api.ipify.org || hostname -I | awk '{print $1}')"
cp .env /root/crm-maiharta.env && chmod 600 /root/crm-maiharta.env
echo "==> .env: $(grep -E '^(APP_DOMAIN|SERVER_IP|CADDY_TLS_MODE)=' .env | tr '\n' ' ')"
echo "==> Build ulang web (Caddy) dan backend..."
docker compose up -d --build web backend || { echo "Gagal build/start. Lihat error di atas."; exit 1; }
sleep 8
echo "==> Status container:"; docker compose ps
echo "==> Port 443 di server:"; (ss -ltnp 2>/dev/null | grep -E ':443\b') || echo "Port 443 TIDAK listen!"
echo "==> Tes HTTPS lokal (SNI $DOMAIN):"
code="$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health" || true)"
echo "    HTTP $code"
echo | openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | grep -E 'subject=|issuer=' || echo "    Handshake TLS lokal GAGAL"
echo "==> Log Caddy terakhir:"; docker compose logs --tail=25 web
if [ "$code" = "200" ]; then
  echo
  echo "BERHASIL di server. Di Cloudflare: SSL/TLS > Overview > pilih 'Full' (BUKAN 'Full (strict)' / 'Flexible')."
  echo "Pastikan juga firewall/security group VPS membuka port 443 dan 80."
else
  echo
  echo "Masih gagal di server. Kirim seluruh output di atas ke saya."
fi
