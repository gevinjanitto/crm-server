#!/usr/bin/env bash
# Backup harian ke Google Drive: jalankan backup.sh (MySQL + upload) + salinan .env,
# gabungkan jadi 1 file, lalu ganti isi folder Drive dengan backup hari ini (backup lama dihapus).
# Pemakaian: sudo bash deploy/gdrive-backup.sh               (jalankan sekarang)
#            sudo bash deploy/gdrive-backup.sh --install-cron (jadwal tiap 00:00 sesuai TIMEZONE di deploy/.env)
#            sudo bash deploy/gdrive-backup.sh --status       (cek jadwal berikutnya & hasil terakhir)
#            sudo bash deploy/gdrive-backup.sh --retry        (ulangi hanya bila backup terakhir gagal; dipanggil timer tiap 15 menit)
set -euo pipefail
cd "$(dirname "$0")"
DEPLOY_DIR="$(pwd)"
LOG="$DEPLOY_DIR/gdrive-backup.log"
UNIT=crm-gdrive-backup
PENDING="$DEPLOY_DIR/.gdrive-backup.pending"

env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//"; }

# Jadwal memakai systemd timer dengan zona waktu eksplisit, jadi tetap jalan tepat 00:00
# walau jam server UTC / zona server berubah, dan dijalankan susulan bila server mati saat tengah malam.
if [ "${1:-}" = "--install-cron" ]; then
  TZ_NAME="$(env_value TIMEZONE || true)"; TZ_NAME="${TZ_NAME:-Asia/Makassar}"
  [ -f "/usr/share/zoneinfo/$TZ_NAME" ] || { echo "Zona waktu $TZ_NAME tidak dikenal"; exit 1; }
  cat > "/etc/systemd/system/$UNIT.service" <<EOF
[Unit]
Description=Backup CRM Maiharta ke Google Drive
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'exec /bin/bash $DEPLOY_DIR/gdrive-backup.sh >> $LOG 2>&1'
EOF
  # Backup ulang otomatis: tiap 15 menit cek apakah backup terakhir gagal, kalau ya ulangi sampai berhasil.
  cat > "/etc/systemd/system/$UNIT-retry.service" <<EOF
[Unit]
Description=Ulangi backup CRM Maiharta ke Google Drive yang gagal
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'exec /bin/bash $DEPLOY_DIR/gdrive-backup.sh --retry >> $LOG 2>&1'
EOF
  cat > "/etc/systemd/system/$UNIT-retry.timer" <<EOF
[Unit]
Description=Cek & ulangi backup Google Drive yang gagal tiap 15 menit

[Timer]
OnCalendar=*:0/15
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
  cat > "/etc/systemd/system/$UNIT.timer" <<EOF
[Unit]
Description=Backup CRM Maiharta ke Google Drive tiap 00:00 $TZ_NAME

[Timer]
OnCalendar=*-*-* 00:00:00 $TZ_NAME
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
  # Hapus jadwal crontab lama supaya backup tidak jalan 2x.
  (crontab -l 2>/dev/null | grep -v 'gdrive-backup.sh') | crontab - || true
  systemctl daemon-reload
  systemctl enable --now "$UNIT.timer" "$UNIT-retry.timer"
  echo "Jadwal terpasang: setiap 00:00 $TZ_NAME, bila gagal diulang otomatis tiap 15 menit sampai berhasil (log: $LOG)"
  systemctl list-timers "$UNIT.timer" "$UNIT-retry.timer" --no-pager
  exit 0
fi

if [ "${1:-}" = "--status" ]; then
  systemctl list-timers "$UNIT.timer" "$UNIT-retry.timer" --no-pager || echo "Timer belum terpasang: sudo bash gdrive-backup.sh --install-cron"
  systemctl is-enabled "$UNIT-retry.timer" >/dev/null 2>&1 || echo "PERINGATAN: backup ulang otomatis belum aktif, jalankan: sudo bash gdrive-backup.sh --install-cron"
  crontab -l 2>/dev/null | grep 'gdrive-backup.sh' && echo "PERINGATAN: masih ada jadwal crontab lama di atas"
  if [ -f "$PENDING" ]; then echo "STATUS: backup terakhir GAGAL (sejak $(cat "$PENDING")), akan diulang otomatis tiap 15 menit"; else echo "STATUS: backup terakhir berhasil"; fi
  echo "--- 15 baris terakhir $LOG ---"; tail -n 15 "$LOG" 2>/dev/null || echo "(log belum ada: backup belum pernah jalan otomatis)"
  exit 0
fi

# Cegah 2 backup berjalan bersamaan (mis. jadwal + manual).
exec 9>"$DEPLOY_DIR/.gdrive-backup.lock"
flock -n 9 || { [ "${1:-}" = "--retry" ] || echo "[$(date)] Backup lain masih berjalan, dilewati"; exit 0; }
# --retry: hanya jalan bila backup sebelumnya gagal (penanda .gdrive-backup.pending masih ada).
if [ "${1:-}" = "--retry" ]; then
  [ -f "$PENDING" ] || exit 0
  echo "[$(date)] Backup sebelumnya gagal (sejak $(cat "$PENDING")), mencoba backup ulang"
else
  date > "$PENDING"
fi
# Penanda dihapus hanya setelah unggahan ke Drive berhasil; setiap kegagalan meninggalkan penanda.
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
rm -f "$PENDING"
echo "[$(date)] Selesai: $NAME diunggah ke Google Drive, backup lama di Drive dihapus"
