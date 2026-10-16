# CRM Maiharta (cloned from github.com/gevinjanitto/crm-server)
Stack: React (CRA/craco) + FastAPI + MySQL (local preview: MariaDB via /root/start-mariadb.sh, supervisor program `mariadb`).

## Requests (2026-10-10)
1. All descriptions (revision, maintenance, subtask, new-task form) get the same rich editor as the Kanban task description: paste/drop photos, bold/italic/lists/link, image resize/align.
2. Clicking a revision/maintenance card (main menu or project tab) opens project Kanban with that task's detail open.
3. Preview for every uploaded document.
Constraint: don't change anything else.

## Implemented
- RichDescription.jsx (generic editor, extracted from TaskDescription), DraftDescription.jsx (create forms: photos uploaded to the new task after save via commitDraft)
- Subtask rich description + photos: backend POST/GET /api/projects/{pid}/tasks/{tid}/subtasks/{sid}/images, PATCH subtask description_html (sanitized)
- Work cards show linked task's rich description; cards with task_id are clickable -> /projects/{pid}/kanban?task={tid} (ticket-based maintenance rows unchanged)
- DocPreview.jsx: images, PDF, TXT/CSV, DOCX (docx-preview), XLSX (read-excel-file); others -> download fallback. Added in project documents, task attachments, comment files, reminder files, ticket attachments
- deploy/frontend-yarn-lock.txt synced with new packages

## Backlog
- P2: preview for legacy .doc/.xls/.pptx
- P2: edit revision description directly from the revision edit modal

## Requests (2026-10-12)
1. Create-task form: subtask descriptions visible directly. 2. Nested subtasks up to 3 levels. 3. Add (nested) subtasks when editing a task (Kanban detail + revision/maintenance edit modal). 4. Task attachments editable (rename/replace file) & deletable. 5. Project documents editable. 6. Project progress = status number / 12 statuses x 100. 7. Notification pause auto-resumes after chosen duration (default 1 hour).
Constraint: don't change anything else.

## Implemented (2026-10-12)
- Subtasks stored flat with `parent_id`; backend build_subtasks/subtask_level (max 3), cascade delete, POST /tasks/{tid}/subtasks/tree
- SubtaskTreeInput.jsx (create task, create/edit revision & maintenance); SubtaskItem nested + description open by default
- PATCH/DELETE /projects/{pid}/tasks/{tid}/documents/{did}; PATCH /projects/{pid}/documents/{did} (documents.update_document/archive_document)
- core.status_progress used in project_public, status change, CSV/XLSX export
- Pause/mute store `<channel>_until`; channel_muted() lapses automatically; durations 1/3/8/24 jam or manual
- Local preview: MariaDB supervisor program (/etc/supervisor/conf.d/mariadb.conf -> /app/scripts/start_mariadb.sh)

## Backlog
- P2: drag to reorder/re-parent subtasks
- P2: show remaining pause time countdown on Notifications page

## Requests (2026-10-13)
1. Project year groups: rows per page 10/25/50/Semua/custom. 2. Project with maintenance (manual or client ticket) this year -> grouped in current year; only current year open by default.
3. Dashboard filtered to current year + year filter. 4. Finance grouped by year, current year default, year filter changes cards/chart/table.
5. Notes: @mention users (notify new mentions) + autosave (2s). 6. Inbox: expand full thread + per-user delete (returns on new comment).
7. Important notifs (pengingat/akun/sambutan) queued while paused, delivered exactly once on resume (notification_queue, 60s loop + on unpause + cron).
8. Description images: click once -> toolbar delete button or Delete/Backspace.

## Implemented (2026-10-13)
- backend/project_years.py, GET /projects maintenance_years, GET /dashboard?year=, DELETE /inbox/{tid}, doc mention notify, notification queue
- frontend YearControls.jsx (YearSelect, PageSizeSelect), ProjectYearGroups, Dashboard, Finance, Inbox, DocsPage, RichDescription/ImageTools
- Tests: backend/tests/test_iter19_year_notes_inbox_queue.py (10/10)

## Backlog
- P2: remember chosen page size per user
- P2: highlight @mentions in notes

## Requests (2026-10-13 b)
- Notes: @tags shown blue (ProseMirror decoration, stored HTML unchanged)
- Kanban: drag empty board area to scroll sideways (no need for bottom scrollbar)

## Bug fix (2026-10-13 c) — GDrive backup tidak jalan tengah malam
- deploy/gdrive-backup.sh --install-cron: crontab (00:00 WIB = 01:00 WITA, tergantung TZ server) diganti systemd timer `crm-gdrive-backup` OnCalendar 00:00 sesuai TIMEZONE deploy/.env (default Asia/Makassar), Persistent=true, hapus crontab lama, flock; tambah --status. Docs section 12 diperbarui. Test iteration_20 100%.

## Requests (2026-10-15) — re-cloned into fresh environment
1. Glosarium global menu (MENU UTAMA): Admin CRUD; Admin Project & Developer read-only; Client hidden. Title, WYSIWYG description, multi-document upload (rename/replace/delete).
2. Project status "Maintenance": Selesai project with open maintenance (manual != Selesai or unfinished client ticket) shows Maintenance automatically; back to Selesai when done.

## Implemented (2026-10-15)
- backend/glossary.py (/api/glossary CRUD, /documents multi upload/patch/delete/download, perms glossary.read/glossary.write in core.py)
- backend/project_maintenance.py mark_maintenance -> in_maintenance flag (stored status stays Selesai) on GET /projects, /projects/{pid}, dashboard
- frontend pages/Glossary.jsx + glossary.css, nav + route; projectStatus() badge, Projects "Maintenance" tab
- Tests: backend/tests/test_glossary_and_maintenance.py, iteration_1 (backend 22/22, UI 21/22 flaky timing only)

## Backlog
- P2: Glosarium categories/tags; P2: link glossary to projects


## Update Jun 2026 — Maintenance & tahun selesai
- Maintenance hanya bisa ditambah (admin) / di-approve dari tiket client (status Diterima) bila project berstatus Selesai (backend guard + UI disembunyikan).
- Pengelompokan tahun project = tahun selesai (completed_at / log status Selesai); project belum selesai masuk tahun berjalan.
- Project Selesai dengan maintenance yang di-approve tampil juga sebagai baris amber di tahun maintenance terbaru (tahun tanggal mulai), tetap ada di tahun selesai.
- Keuangan & dashboard: baris maintenance hanya menghitung total biaya maintenance (estimate), bukan nilai awal project.
- Backlog: ekspor Excel belum memisahkan baris maintenance.
