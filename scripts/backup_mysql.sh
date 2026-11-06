#!/usr/bin/env bash
# Backup MySQL CRM (read-only). Di VPS gunakan: sudo bash deploy/backup.sh
set -euo pipefail
OUT="${1:?Pemakaian: bash scripts/backup_mysql.sh DIREKTORI_BARU}"
mkdir -p "$OUT"
: "${MYSQL_HOST:?}" "${MYSQL_USER:?}" "${MYSQL_PASSWORD:?}" "${MYSQL_DATABASE:?}"
MYSQL_PWD="$MYSQL_PASSWORD" mysqldump -h "$MYSQL_HOST" -P "${MYSQL_PORT:-3306}" -u "$MYSQL_USER" --single-transaction --quick "$MYSQL_DATABASE" | gzip > "$OUT/mysql.sql.gz"
echo "Backup tersimpan di $OUT/mysql.sql.gz"
