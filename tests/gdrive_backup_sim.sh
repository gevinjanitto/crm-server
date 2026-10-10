#!/usr/bin/env bash
# Simulasi deploy/gdrive-backup.sh dengan "docker" palsu (tanpa VPS / Google Drive).
# Pemakaian: bash tests/gdrive_backup_sim.sh [ok|mysqlfail]
set -uo pipefail
MODE="${1:-ok}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp -r /app/deploy "$WORK/deploy"
printf 'GDRIVE_FOLDER_ID="folder123"\nMYSQL_DATABASE=crm\n' > "$WORK/deploy/.env"
echo '{}' > "$WORK/deploy/gdrive-service-account.json"
mkdir -p "$WORK/bin"
cat > "$WORK/bin/docker" <<EOF
#!/usr/bin/env bash
echo "docker \$*" >> "$WORK/docker.log"
if [ "\$1" = compose ]; then
  [ "$MODE" = mysqlfail ] && { echo "mysqldump: Got error: 1045 Access denied" >&2; exit 2; }
  echo "-- MySQL dump"; exit 0
fi
OUTDIR=""; DATADIR=""
for a in "\$@"; do case "\$a" in *:/out) OUTDIR="\${a%:/out}";; *:/data:ro) DATADIR="\${a%:/data:ro}";; esac; done
if printf '%s ' "\$@" | grep -q 'rclone/rclone'; then ls "\$DATADIR" > "$WORK/uploaded.txt"; exit 0; fi
name="\$(printf '%s\n' "\$@" | grep '^/out/' | head -1)"; touch "\$OUTDIR/\${name#/out/}"
EOF
chmod +x "$WORK/bin/docker"
PATH="$WORK/bin:$PATH" bash "$WORK/deploy/gdrive-backup.sh"; CODE=$?
echo "EXIT=$CODE"
echo "UPLOADED=$(cat "$WORK/uploaded.txt" 2>/dev/null)"
ls "$WORK/deploy/backups/"* 2>/dev/null | sed 's/^/LOCAL: /'
grep -c -- ' -p' "$WORK/docker.log" | sed 's/^/PASSWORD_ON_CMDLINE=/'
