#!/usr/bin/env bash
# Backup database MySQL + file upload + data n8n + sesi WAHA ke deploy/backups/<tanggal>/
# Pemakaian: sudo bash deploy/backup.sh      (simpan 14 hari terakhir)
set -euo pipefail
cd "$(dirname "$0")"
OUT="backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --quick "$MYSQL_DATABASE"' | gzip > "$OUT/mysql.sql.gz"
[ "$(gzip -dc "$OUT/mysql.sql.gz" | head -c 1 | wc -c)" -gt 0 ] || { echo "Dump MySQL kosong" >&2; exit 1; }
for vol in uploads n8n_data waha_sessions; do
  docker run --rm -v "crm-maiharta_${vol}:/data:ro" -v "$(pwd)/$OUT:/out" alpine tar czf "/out/${vol}.tar.gz" -C /data .
done
find backups -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "Backup tersimpan di deploy/$OUT"
