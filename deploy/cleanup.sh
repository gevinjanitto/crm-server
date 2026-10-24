#!/usr/bin/env bash
# Bersihkan file tidak penting di server tanpa menyentuh data CRM, file upload, n8n, maupun sesi WAHA.
# Pemakaian: sudo bash deploy/cleanup.sh          (aman, update berikutnya tetap cepat)
#            sudo bash deploy/cleanup.sh --deep   (+ hapus semua cache build; update berikutnya lebih lama)
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then echo "Jalankan dengan sudo."; exit 1; fi
if pgrep -f "update.sh --run" >/dev/null 2>&1; then echo "Update sedang berjalan. Coba lagi setelah selesai."; exit 1; fi

echo "==> Sebelum:"; df -h / | tail -1
echo "==> Image Docker lama yang tidak dipakai"
docker image prune -f
echo "==> Cache build yang tidak dipakai"
if [ "${1:-}" = "--deep" ]; then docker builder prune -af; else docker builder prune -f; fi
echo "==> Log sistem (disisakan 100 MB)"
journalctl --vacuum-size=100M >/dev/null 2>&1 || true
echo "==> Cache paket apt"
apt-get clean
echo "==> Backup lokal lebih dari 3 hari"
find backups -mindepth 1 -maxdepth 1 -type d -mtime +2 -exec rm -rf {} + 2>/dev/null || true
echo "==> Sesudah:"; df -h / | tail -1
docker compose ps --format "table {{.Service}}\t{{.Status}}"
