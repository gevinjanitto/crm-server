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
