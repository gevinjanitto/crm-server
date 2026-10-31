#!/usr/bin/env bash
# Simulasi deploy/gdrive-backup.sh dengan "docker" palsu (tanpa VPS / Google Drive).
# Pemakaian: bash tests/gdrive_backup_sim.sh [ok|mysqlfail|drivefail|retryflow]
set -uo pipefail
MODE="${1:-ok}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp -r /app/deploy "$WORK/deploy"
printf 'GDRIVE_FOLDER_ID="folder123"\nMYSQL_DATABASE=crm\n' > "$WORK/deploy/.env"
echo '{}' > "$WORK/deploy/gdrive-service-account.json"
echo "$MODE" > "$WORK/mode"
mkdir -p "$WORK/bin"
cat > "$WORK/bin/docker" <<EOF
#!/usr/bin/env bash
M="\$(cat "$WORK/mode")"
echo "docker \$*" >> "$WORK/docker.log"
if [ "\$1" = compose ]; then
  [ "\$M" = mysqlfail ] && { echo "mysqldump: Got error: 1045 Access denied" >&2; exit 2; }
  echo "-- MySQL dump"; exit 0
fi
OUTDIR=""; DATADIR=""
for a in "\$@"; do case "\$a" in *:/out) OUTDIR="\${a%:/out}";; *:/data:ro) DATADIR="\${a%:/data:ro}";; esac; done
if printf '%s ' "\$@" | grep -q 'rclone/rclone'; then
  [ "\$M" = drivefail ] && { echo "Failed to sync: dial tcp: lookup www.googleapis.com: no such host" >&2; exit 1; }
  ls "\$DATADIR" > "$WORK/uploaded.txt"; echo x >> "$WORK/uploads.count"; exit 0
fi
name="\$(printf '%s\n' "\$@" | grep '^/out/' | head -1)"; touch "\$OUTDIR/\${name#/out/}"
EOF
chmod +x "$WORK/bin/docker"
run() { PATH="$WORK/bin:$PATH" bash "$WORK/deploy/gdrive-backup.sh" "$@"; }
pending() { [ -f "$WORK/deploy/.gdrive-backup.pending" ] && echo yes || echo no; }
uploads() { [ -f "$WORK/uploads.count" ] && wc -l < "$WORK/uploads.count" || echo 0; }
if [ "$MODE" = retryflow ]; then
  run --retry; echo "STEP0 retry-without-failure EXIT=$? PENDING=$(pending) UPLOADS=$(uploads)"
  echo drivefail > "$WORK/mode"; run; echo "STEP1 daily-drivefail EXIT=$? PENDING=$(pending) UPLOADS=$(uploads)"
  run --retry; echo "STEP2 retry-still-offline EXIT=$? PENDING=$(pending) UPLOADS=$(uploads)"
  echo ok > "$WORK/mode"; run --retry; echo "STEP3 retry-online EXIT=$? PENDING=$(pending) UPLOADS=$(uploads)"
  run --retry; echo "STEP4 retry-after-success EXIT=$? PENDING=$(pending) UPLOADS=$(uploads)"
  exit 0
fi
run; CODE=$?
echo "EXIT=$CODE"
echo "PENDING=$(pending)"
echo "UPLOADED=$(cat "$WORK/uploaded.txt" 2>/dev/null)"
ls "$WORK/deploy/backups/"* 2>/dev/null | sed 's/^/LOCAL: /'
grep -c -- ' -p' "$WORK/docker.log" | sed 's/^/PASSWORD_ON_CMDLINE=/'
