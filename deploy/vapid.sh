#!/usr/bin/env bash
# Tambahkan kunci notifikasi web (VAPID) ke file env bila belum ada. Kunci lama tidak pernah diganti.
# Pemakaian: bash deploy/vapid.sh [FILE_ENV] [EMAIL]
set -euo pipefail
ENV_FILE="${1:-$(dirname "$0")/.env}"
EMAIL="${2:-}"
touch "$ENV_FILE"
if grep -q '^VAPID_PRIVATE_KEY=.\+' "$ENV_FILE"; then echo "==> Kunci notifikasi web (VAPID) sudah ada"; exit 0; fi
[ -n "$EMAIL" ] || EMAIL="$(grep '^ADMIN_EMAIL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"')"
b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
TMP="$(mktemp)"
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP" 2>/dev/null
PRIV="$(openssl ec -in "$TMP" -outform DER 2>/dev/null | tail -c +8 | head -c 32 | b64url)"
PUB="$(openssl ec -in "$TMP" -pubout -outform DER 2>/dev/null | tail -c 65 | b64url)"
rm -f "$TMP"
sed -i.bak '/^VAPID_/d' "$ENV_FILE" && rm -f "$ENV_FILE.bak"
[ -z "$(tail -c1 "$ENV_FILE")" ] || echo >> "$ENV_FILE"
printf 'VAPID_PRIVATE_KEY=%s\nVAPID_PUBLIC_KEY=%s\nVAPID_SUBJECT=mailto:%s\n' "$PRIV" "$PUB" "${EMAIL:-admin@localhost}" >> "$ENV_FILE"
echo "==> Kunci notifikasi web (VAPID) dibuat di $ENV_FILE (simpan baik-baik, jangan diganti)"
