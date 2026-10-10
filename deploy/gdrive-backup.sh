#!/usr/bin/env bash
# Backup harian ke Google Drive: jalankan backup.sh (MySQL + upload + n8n + WAHA) + salinan .env,
# gabungkan jadi 1 file, lalu ganti isi folder Drive dengan backup hari ini (backup lama dihapus).
# Pemakaian: sudo bash deploy/gdrive-backup.sh               (jalankan sekarang)
#            sudo bash deploy/gdrive-backup.sh --install-cron (jadwal tiap 00:00 WIB)
set -euo pipefail
cd "$(dirname "$0")"
DEPLOY_DIR="$(pwd)"
LOG="$DEPLOY_DIR/gdrive-backup.log"

if [ "${1:-}" = "--install-cron" ]; then
  OFFSET=$(date +%z)                          # contoh +0000 (UTC) atau +0700 (WIB)
  SIGN=${OFFSET:0:1}; HOURS=$((10#${OFFSET:1:2}))
  [ "$SIGN" = "-" ] && HOURS=$((-HOURS))
  HOUR=$(( ((17 + HOURS) % 24 + 24) % 24 ))  # 00:00 WIB = 17:00 UTC
  LINE="0 $HOUR * * * bash $DEPLOY_DIR/gdrive-backup.sh >> $LOG 2>&1"
  (crontab -l 2>/dev/null | grep -v 'gdrive-backup.sh'; echo "$LINE") | crontab -
  echo "Cron terpasang (jam server $HOUR:00 = 00:00 WIB): $LINE"
  exit 0
fi

env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//"; }
FOLDER_ID="$(env_value GDRIVE_FOLDER_ID || true)"
SA_FILE="$(env_value GDRIVE_SERVICE_ACCOUNT_FILE || true)"
SHARED_DRIVE="$(env_value GDRIVE_SHARED_DRIVE_ID || true)"
TOKEN="$(env_value GDRIVE_TOKEN || true)"
CLIENT_ID="$(env_value GDRIVE_CLIENT_ID || true)"
CLIENT_SECRET="$(env_value GDRIVE_CLIENT_SECRET || true)"
[ -n "$FOLDER_ID" ] || { echo "[$(date)] GDRIVE_FOLDER_ID belum diisi di deploy/.env"; exit 1; }
SA_FILE="${SA_FILE:-gdrive-service-account.json}"
case "$SA_FILE" in /*) ;; *) SA_FILE="$DEPLOY_DIR/$SA_FILE" ;; esac

echo "[$(date)] Mulai backup"
RESULT="$(bash backup.sh)" || { echo "[$(date)] backup.sh gagal (lihat pesan error di atas)"; exit 1; }
OUT="$(printf '%s\n' "$RESULT" | sed -n 's#^Backup tersimpan di deploy/##p' | tail -1)"
[ -n "$OUT" ] && [ -d "$OUT" ] || { echo "[$(date)] Folder hasil backup tidak ditemukan. Output backup.sh: $RESULT"; exit 1; }
echo "[$(date)] Backup lokal OK: deploy/$OUT"
cp .env "$OUT/env.txt"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
NAME="crm-maiharta-backup-$(TZ=Asia/Jakarta date +%Y%m%d-%H%M).tar"
tar cf "$STAGE/$NAME" -C "$OUT" .

RCLONE=(docker run --rm -v "$STAGE:/data:ro" -e RCLONE_CONFIG_GDRIVE_TYPE=drive -e RCLONE_CONFIG_GDRIVE_SCOPE=drive
        -e RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID="$FOLDER_ID")
if [ -n "$TOKEN" ]; then
  RCLONE+=(-e RCLONE_CONFIG_GDRIVE_TOKEN="$TOKEN" -e RCLONE_CONFIG_GDRIVE_CLIENT_ID="$CLIENT_ID" -e RCLONE_CONFIG_GDRIVE_CLIENT_SECRET="$CLIENT_SECRET")
elif [ -f "$SA_FILE" ]; then
  RCLONE+=(-v "$SA_FILE:/sa.json:ro" -e RCLONE_CONFIG_GDRIVE_SERVICE_ACCOUNT_FILE=/sa.json)
else
  echo "[$(date)] Kredensial Drive belum ada: simpan file service account di $SA_FILE atau isi GDRIVE_TOKEN"; exit 1
fi
[ -n "$SHARED_DRIVE" ] && RCLONE+=(-e RCLONE_CONFIG_GDRIVE_TEAM_DRIVE="$SHARED_DRIVE")
RCLONE+=(rclone/rclone)

# sync = isi folder Drive dibuat sama persis dengan folder staging (hanya backup hari ini).
"${RCLONE[@]}" sync /data gdrive: --drive-use-trash=false --retries 5 --low-level-retries 20 --stats-one-line -v
echo "[$(date)] Selesai: $NAME diunggah ke Google Drive, backup lama di Drive dihapus"
