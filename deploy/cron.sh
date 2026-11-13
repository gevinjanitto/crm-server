#!/bin/sh
# Pengganti cron Railway: memicu jadwal task berulang & pengingat setiap menit.
sleep 30
while true; do
  RID="vps-$(date -u +%Y%m%d%H%M)"
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  curl -fsS -o /dev/null -X POST "http://backend:8001/api/cron/project-workspace" \
    -H "Authorization: Bearer ${WEBHOOK_CRON_SECRET}" \
    -H "Content-Type: application/json" \
    -d "{\"event\":\"schedule.triggered\",\"schedule_id\":\"project-workspace\",\"run_id\":\"${RID}\",\"dispatch_time\":\"${NOW}\"}" \
    || echo "[cron] gagal memanggil backend pada ${NOW}"
  sleep 60
done
