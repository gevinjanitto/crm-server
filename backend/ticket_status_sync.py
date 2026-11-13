"""Translate board progress into ticket workflow states, independently of column names."""
from fastapi import HTTPException
from core import db, now, uid, project_statuses, log_activity


def ticket_target(ticket, project, status):
    kind = next((s['kind'] for s in project_statuses(project) if s['name'] == status), None)
    if kind is None:
        raise HTTPException(400, 'Status tujuan tidak ditemukan.')
    if ticket['status'] == 'Ditutup' and kind == 'done':
        return 'Ditutup'
    if kind == 'done':
        return 'Selesai'
    if kind == 'active':
        return 'Dikerjakan'
    # An untouched backlog ticket keeps its triage/approval stage. Returning
    # completed or active work to backlog means accepted, not newly submitted.
    if ticket['status'] in ['Dikerjakan', 'Selesai']:
        return 'Diterima'
    return ticket['status']


async def linked_ticket(task):
    if task.get('source') != 'ticket' or not task.get('source_id'):
        return None
    return await db.tickets.find_one(
        {'id': task['source_id'], 'project_id': task['project_id']}, {'_id': 0})


def validate_target(ticket, target):
    if target == ticket['status']:
        return
    if ticket['status'] in ['Ditolak', 'Ditutup']:
        raise HTTPException(400, 'Tiket ditolak atau ditutup tidak dapat dipindahkan ke pekerjaan aktif.')
    if target in ['Dikerjakan', 'Selesai'] and ticket.get('category') in ['Change Request', 'Out of Scope']:
        if not ticket.get('estimate') or ticket['estimate'] <= 0:
            raise HTTPException(400, 'Tiket wajib memiliki estimasi biaya sebelum pekerjaan dimulai.')
        if not ticket.get('approved'):
            raise HTTPException(400, 'Estimasi tiket harus disetujui sebelum pekerjaan dimulai.')


async def validate_ticket_move(task, status, project):
    ticket = await linked_ticket(task)
    if ticket:
        validate_target(ticket, ticket_target(ticket, project, status))


async def sync_ticket_status(task, status, project, actor=None):
    ticket = await linked_ticket(task)
    if not ticket:
        return
    target = ticket_target(ticket, project, status)
    validate_target(ticket, target)
    if target == ticket['status']:
        return
    timestamp = now()
    update = {'status': target, 'updated_at': timestamp}
    if target in ['Dikerjakan', 'Selesai']:
        update['triaged'] = True
    result = await db.tickets.update_one(
        {'id': ticket['id'], 'project_id': task['project_id'], 'status': ticket['status']},
        {'$set': update})
    if not result.modified_count:
        return
    actor = actor or {'id': 'system', 'name': 'Sistem', 'role': 'Sistem'}
    await db.ticket_comments.insert_one({
        'id': uid(), 'ticket_id': ticket['id'],
        'message': f"Status diperbarui melalui Kanban: {ticket['status']} → {target} (kolom {status})",
        'internal': False, 'system': True, 'author_name': actor['name'],
        'author_role': actor.get('role', 'Sistem'), 'created_at': timestamp,
    })
    await log_activity(actor, 'ubah status', 'tiket', ticket['id'], ticket['title'],
                       task['project_id'], {'dari': ticket['status'], 'ke': target, 'kolom': status, 'sumber': 'kanban'})