#!/usr/bin/env bash
# Kosongkan data CRM & bersihkan server. Kode aplikasi, .env, n8n, sesi WAHA dan sertifikat HTTPS TIDAK dihapus.
# Pemakaian: sudo bash deploy/reset-data.sh
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "deploy/.env tidak ditemukan."; exit 1; }

cat <<'EOF'
PERINGATAN: semua data CRM akan DIHAPUS PERMANEN:
  - database MySQL (user, client, project, task, tiket, keuangan, reminder, notifikasi, log)
  - semua file upload (dokumen project, lampiran)
  - folder backup lama, log update, file .env.bak.*
  - image & cache build Docker yang tidak terpakai
Yang TETAP: kode aplikasi, deploy/.env, workflow n8n, sesi WhatsApp (WAHA), sertifikat HTTPS.
EOF
read -r -p "Ketik HAPUS untuk melanjutkan: " answer
[ "$answer" = "HAPUS" ] || { echo "Dibatalkan."; exit 1; }
read -r -p "Buat backup terakhir dulu (disimpan di /root/crm-backup-terakhir)? [Y/n]: " keep
if [ "${keep:-Y}" != "n" ] && [ "${keep:-Y}" != "N" ]; then
  bash backup.sh
  rm -rf /root/crm-backup-terakhir && mkdir -p /root/crm-backup-terakhir
  cp -r "backups/$(ls -1 backups | tail -n 1)"/. /root/crm-backup-terakhir/
  echo "Backup terakhir disimpan di /root/crm-backup-terakhir"
fi

echo "==> Mulai tanpa data contoh (hanya akun admin)"
if grep -q '^SEED_SAMPLE_DATA=' .env; then sed -i 's/^SEED_SAMPLE_DATA=.*/SEED_SAMPLE_DATA=false/' .env; else echo 'SEED_SAMPLE_DATA=false' >> .env; fi

echo "==> Menghentikan backend, cron & MySQL"
docker compose stop backend cron mysql
docker compose rm -f backend cron mysql
echo "==> Menghapus database & file upload"
docker volume rm crm-maiharta_mysql_data crm-maiharta_uploads

echo "==> Membersihkan backup lama, log & file sementara"
rm -rf backups update.log .env.bak.*
apt-get clean >/dev/null 2>&1 || true
journalctl --vacuum-time=3d >/dev/null 2>&1 || true

echo "==> Menyalakan ulang dengan database kosong"
docker compose up -d
sleep 20
echo "==> Menghapus image & cache build Docker yang tidak dipakai"
docker image prune -af
docker builder prune -af
docker compose ps --format "table {{.Service}}\t{{.Status}}"
PASS="$(grep -E '^SEED_PASSWORD=' .env | cut -d= -f2-)"
cat <<EOF

================= SELESAI =================
Login CRM : username admin
Password  : ${PASS}  (wajib diganti saat login pertama)
Ruang disk: $(df -h / | awk 'NR==2{print $4" kosong dari "$2}')
===========================================
EOF
