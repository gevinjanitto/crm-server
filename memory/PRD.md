# CRM Maiharta – PRD / progress
Repo: github.com/gevinjanitto/crm-server (React CRA/craco + FastAPI + MariaDB via docstore). Preview: run /app/scripts/start_mariadb.sh (background) before backend.

## 2026-11-04
- WhatsApp: new admin page /whatsapp-report (backend/whatsapp_report.py) reads messages straight from Twilio Messages API (status, error code + Indonesian explanation incl. 63049), CRM-side failures list, manual resend (POST /api/admin/whatsapp-report/resend). Deliveries now store the notification payload for resend.
- Template sync sends allow_category_change=false so Meta can't recategorize UTILITY -> MARKETING (cause of 63049); report warns when current template category isn't UTILITY.
- Admin: Keuangan sidebar menu + dashboard finance summary removed (Accounting unchanged).
- Dashboard "Mention" card: GET /api/mentions/mine = notes + task comments + ticket comments with source label.
- Admin page /task-per-user (GET /api/admin/tasks-by-user): unfinished tasks grouped per user.
- Testing iteration_1: backend 23/23, frontend passed.

## 2026-11-04 (lanjutan)
- WA template: sync checks Meta category; if MARKETING creates new UTILITY template (allow_category_change=false), old stays until approved; card shows category.
- Task drawer: compose box right under comments (.ck-feed flex 0 1 auto, max 45vh).
- Notification deep links: tasks/comments (&comment=), tickets (/tickets?ticket=), revisi/maintenance -> linked kanban task, dokumen/deployment tabs; frontend notificationLink() fallback for old notifs.
- setup.sh rebuilt (scripts/build_setup.sh, header identical to group.sh) -> /setup.sh
- Testing iteration_2: backend 28/28, frontend passed.

## 2026-11-04 (kwitansi + deploy fix)
- Kwitansi tab (Admin/Accounting) per project: backend/receipts.py + receipt_doc.py (layout from user's docx template, VML for DOCX, reportlab for PDF). Auto number 00N/INV/MH/MM/YYYY, PPN % + PPh 23 gross-up, terbilang, per-receipt logo next to "Diterima dari". Frontend components/ReceiptsTab.jsx.
- Deploy: deploy/.env removed from git (+.gitignore); update.sh backs up/restores .env (/root/crm-maiharta.env); compose backend env_file: .env (all vars reach backend, e.g. CLOUDINARY_*/AI_*); Caddy CADDY_TLS_MODE=acme|internal (internal for Cloudflare SSL Full); change-domain.sh skips DNS check behind Cloudflare.
- setup.sh rebuilt -> /setup.sh. Testing iteration_1: backend 14/14, frontend pass.

## Backlog
- P2: ticket mention opens the specific ticket; ticket comments store author_id
- P2: Twilio status callback webhook for real-time status

## 2026-11-04 (invoice + TTD + preview)
- Invoice tab (Admin/Accounting) per project: backend/invoices.py + invoice_doc.py (layout from user's invoice.docx -> templates/invoice_template.docx), DOCX/PDF, client logo left of "Kepada" name, auto number 00N/INV/MH/MM/YYYY (own sequence).
- Master rekening (invoice only): /api/bank-accounts CRUD; pick in form + add/delete inline; invoice stores bank snapshot.
- TTD option (default off) + per-document TTD upload (default templates/ttd_default.png) for kwitansi & invoice.
- Live preview (POST .../preview returns layout elements) in both editors: click text to edit inline, drag image corner / sliders to resize brand logo, client logo, TTD (logo_scale, client_logo_scale, sign_scale 30-250%).
- setup.sh rebuilt (header identical to group.sh, excludes .emergent) -> /setup.sh. Testing iteration_1: backend 26/26; 2 UI bugs fixed (Esc closed dialog, TTD handle covered).

## Backlog
- P2: decide if invoice & kwitansi should share numbering (currently separate sequences, same format)

## 2026-11-04 (mention dismiss)
- Dashboard Mention: task/ticket comment mentions can be removed per user (DELETE /api/mentions/mine/{id}, collection mention_dismissals). Notes mentions unchanged (disappear when checked). setup.sh rebuilt.

## 2026-06 update
- Laporan WhatsApp moved from sidebar into Pengaturan > Notifikasi akun (dialog), Muat ulang fixed (spinner + toast, refetch)
- Uji notifikasi / Uji notifikasi web / Laporan WhatsApp in one row
- Project tabs Kwitansi & Invoice moved into More menu
- Live edit kwitansi/invoice: images draggable + 8-handle resize, stored as image_boxes {key:{dx,dy,dw,dh}} applied in receipt_doc.apply_boxes (preview, PDF, DOCX)
- setup.sh rebuilt via scripts/build_setup.sh (served at /setup.sh); added start-local.bat
- Preview: MariaDB via supervisor (/etc/supervisor/conf.d/mariadb.conf -> scripts/start_mariadb.sh)

## 2026-06 update 2
- Notif project: Admin Project only if member (assigned_to); Admin always
- Project needs >=1 Admin/AP + >=1 Developer (create & edit)
- Every task has PIC (creator default; backfill on startup)
- Task Tim sorted by task count, accessible to Admin Project
- Admin Project: Kwitansi & Invoice (billing.* permissions)
- WA report: removed CRM failures section; Trash buttons fixed

## 2026-06 update 3
- Admin counts as developer in project team validation
- Startup backfill removed; one-time revert_task_pic_backfill (flag app_settings migration_revert_pic_backfill) clears auto-filled PICs (skips tasks with assignment notification, activity log, or source record assigned to that PIC)
