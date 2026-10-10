#!/usr/bin/env bash
# Update/build ulang yang aman: tetap berjalan walau SSH putus. Log: deploy/update.log
# Pemakaian: sudo bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" != "--run" ]; then
  if pgrep -f "deploy/update.sh --run|update.sh --run" >/dev/null 2>&1; then
    echo "Update masih berjalan. Lihat progres: sudo tail -f $(pwd)/update.log"
    exit 0
  fi
  setsid nohup bash "$(pwd)/update.sh" --run > update.log 2>&1 < /dev/null &
  echo "Update berjalan di latar belakang (aman bila SSH putus atau menekan Ctrl+C)."
  echo "Lihat progres kapan saja: sudo tail -f $(pwd)/update.log"
  sleep 2
  exec tail -n +1 -f update.log
fi

echo "==> $(date '+%F %T') Mulai update"
BEFORE="$(git -C .. rev-parse --short HEAD)"
echo "==> Repo: $(git -C .. remote get-url origin) | branch: $(git -C .. rev-parse --abbrev-ref HEAD) | commit: ${BEFORE}"
git -C .. pull --ff-only || echo "PERINGATAN: git pull GAGAL (ada perubahan lokal / branch berbeda / tidak ada koneksi). Build memakai kode lama."
AFTER="$(git -C .. rev-parse --short HEAD)"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "PERINGATAN: tidak ada kode baru dari GitHub (commit tetap ${AFTER}). Pastikan sudah Save to GitHub ke repo & branch di atas."
else
  echo "==> Kode diperbarui: ${BEFORE} -> ${AFTER}"
fi
echo "==> Menghentikan sementara n8n & WAHA agar RAM cukup untuk build (sesi WhatsApp tetap tersimpan)"
docker compose stop n8n waha
echo "==> Build backend & frontend (5-10 menit)"
if docker compose build backend web; then BUILD_OK=1; else BUILD_OK=0; fi
echo "==> Menyalakan semua layanan"
docker compose up -d
echo "==> Menghapus image lama sisa build (data, upload, n8n & WAHA tidak tersentuh)"
docker image prune -f >/dev/null || true
docker compose ps --format "table {{.Service}}\t{{.Status}}"
if [ "$BUILD_OK" = 1 ]; then
  echo "==> $(date '+%F %T') SELESAI. Tekan Ctrl+C untuk keluar dari tampilan log."
else
  echo "==> $(date '+%F %T') BUILD GAGAL. Layanan lama tetap berjalan. Kirim isi update.log untuk dicek."
  exit 1
fi
