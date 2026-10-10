# PRD — CRM Maiharta (clone of github.com/gevinjanitto/crm-server)

## Original problem statement
Clone the project and check whether the last agent request was done correctly: "di foto 1 yg upload gambar buat biar gambarnya di dalam deskripsi jadi dia bisa copas juga jadi modelnya kayak foto 2 (ClickUp style). Di dashboard kotak KPI di-link ke tujuannya: 3 dari kiri ke project dan yg paling kanan ke tiket, role lain disesuaikan." Fix anything that is wrong.

## Architecture
React (CRA/craco) + FastAPI + MySQL/MariaDB (backend/docstore.py emulates Motor API). Local preview runs MariaDB via mysqld_safe.

## Personas
Admin, Admin Project, Developer, Accounting, Client.

## Implemented / verified (Oct 2026)
- Inline rich description in task detail (TaskDescription.jsx): images inside text, paste/drag/upload, copy-paste, saves description_html (sanitized by backend/rich_text.py). Verified OK.
- Dashboard KPI cards are links: Total/Aktif/Selesai -> /projects (?tab=), rightmost -> tickets; Accounting rightmost -> /finance; Client 4 ticket cards -> /tickets with filters. Verified OK.
- Fixed: "Tiket terbuka" card linked to group=open (excluded "Dikerjakan") so list count didn't match the card -> new group "active" (Belum selesai).
- Fixed: script/style inner text leaking into plain-text description (rich_text.py).

- Image resize & alignment in task description (ImageTools.jsx): click image -> toolbar (kiri/tengah/kanan, 25/50/75/100%, preview) + drag handle; stored as data-width/data-align, sanitized by backend. Verified 100%.

- Admin notification controls (notification_controls.py, UserNotificationControls.jsx): global pause email/WA, per-user mute, reset password to default (12345678) with forced email+WA notif using existing template. Verified 100%.
- Daily Google Drive backup: deploy/gdrive-backup.sh (rclone docker, sync replaces old backup, cron 00:00 WIB). Guide in DEPLOY_IDCLOUDHOST.md §12-13. Not run here (needs VPS + Drive credentials).

## Iteration: Reminder upgrade (Oct 2026)
Request: "di reminder tambahkan deskripsi dan upload dokumen. serta tambahkan juga mau dikasi notif tambahan gak? berapa hari notif tambahan sebelum tanggal akhir tapi yg 2 minggu tetep ada"
- Reminder form: Deskripsi textarea, multi-document upload (PDF/DOC/XLS/PPT/TXT/CSV/ZIP/RAR/images, 10MB each, 5 per upload, 20 per reminder) stored on local disk (UPLOAD_DIR) via storage.py.
- "Notif tambahan?" switch + chips 1/3/7 hari + free input (1-365, not 14). 14-day notif unchanged; extra tracked by extra_notified_at; combined message if both due together.
- Endpoints: /api/projects/{pid}/reminders/{rid}/attachments (POST, GET/{aid}, DELETE/{aid}). Report page shows description, extra-notif note, files.
- Local preview: MariaDB via supervisor `mariadb` -> scripts/start_mariadb.sh. Tested 100% (iteration_15).

## Iteration: Remove Emergent tracking (Oct 2026)
- Removed from frontend/public/index.html: emergent-main.js script and PostHog snippet (api_host ap.emergent.sh — the "e/" requests).
- yarn remove @emergentbase/overlay @emergentbase/visual-edits; craco.config.js cleaned; deploy/frontend-yarn-lock.txt synced.
- Verified: production build contains 0 "emergent"/"posthog" strings; browser makes no emergent.sh requests.

## Iteration: Fix Google Drive backup (Oct 2026)
- Bug: gdrive-backup.sh built path "backups/backups/<ts>" from backup.sh output -> false "backup.sh gagal". Fixed path parsing + proper failure detection.
- backup.sh: mysqldump uses MYSQL_PWD (no password on command line), empty-dump check.
- Verified via fake-docker simulation tests/gdrive_backup_sim.sh (iteration_16, pass). Real Drive upload still to be confirmed on VPS.

## Backlog
- P2: replace deprecated execCommand; revoke blob URLs earlier.
