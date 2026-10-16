"""A live maintenance view of tickets, without duplicate tasks or copied records."""
from core import db


async def ticket_maintenance_rows(user, project_ids):
    query = {'project_id': {'$in': project_ids}}
    if user['role'] == 'Developer':
        query['assigned_to'] = user['id']
    rows = await db.tickets.find(query, {'_id': 0}).sort('created_at', -1).to_list(2000)
    result = []
    for t in rows:
        finished = t['status'] in ['Selesai', 'Ditutup', 'Ditolak']
        row = {
            'id': 'ticket:' + t['id'], 'ticket_id': t['id'], 'task_id': t.get('task_id'),
            'project_id': t['project_id'], 'project_name': t.get('project_name', ''),
            'title': t['title'], 'description': t.get('description', ''),
            'kind': 'Tiket client', 'ticket_status': t['status'], 'ticket_code': t['code'],
            'status': 'Selesai' if finished else 'Development' if t['status'] == 'Dikerjakan' else 'Belum dikerjakan',
            'priority': t.get('priority', 'Sedang'), 'assigned_to': t.get('assigned_to', ''),
            'entry_date': t['created_at'][:10], 'created_at': t['created_at'],
            'completed_at': t.get('updated_at') if t['status'] in ['Selesai', 'Ditutup'] else None,
            'approved': t.get('approved', False),
        }
        if user['role'] != 'Developer': row['estimate'] = t.get('estimate', 0)
        result.append(row)
    return result