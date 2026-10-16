import math
from datetime import date, datetime, timezone
from fastapi import HTTPException
from core import db, project_for, MANAGERS

async def access(u, pid, write=False, internal=False):
    p = await project_for(u, pid, 'task.write' if write else 'task.read')
    if internal and u['role'] not in MANAGERS + ['Developer']:
        raise HTTPException(403, 'Ruang kerja ini hanya untuk tim internal.')
    return p

async def record(coll, pid, rid):
    row = await db[coll].find_one({'id': rid, 'project_id': pid}, {'_id': 0})
    if not row: raise HTTPException(404, 'Data tidak ditemukan pada project ini.')
    return row

async def members(p, clients=True):
    clauses = [{'role': {'$in': MANAGERS}}, {'id': {'$in': p.get('assigned_to', [])}}]
    if clients: clauses.append({'role': 'Client', 'client_id': p.get('client_id')})
    return await db.users.find({'active': True, '$or': clauses}, {'_id': 0, 'id': 1, 'name': 1, 'username': 1, 'role': 1}).to_list(500)

async def validate_task_extensions(pid, update):
    for key, coll in [('list_id', 'workspace_nodes'), ('sprint_id', 'workspace_sprints')]:
        if update.get(key):
            obj = await record(coll, pid, update[key])
            if key == 'list_id' and obj['kind'] != 'list': raise HTTPException(400, 'Pilih List, bukan Space atau Folder.')
            if key == 'sprint_id' and obj['status'] == 'completed': raise HTTPException(400, 'Sprint telah ditutup.')
    if 'custom_fields' in update:
        fields = await db.workspace_fields.find({'project_id': pid}, {'_id': 0}).to_list(100)
        by_id = {f['id']: f for f in fields}
        for key, value in update['custom_fields'].items():
            f = by_id.get(key)
            if not f: raise HTTPException(400, 'Custom field tidak ditemukan.')
            if value is None or value == '': continue
            valid = True
            if f['kind'] == 'text': valid = isinstance(value, str) and len(value) <= 2000
            elif f['kind'] == 'number': valid = type(value) in (int, float) and math.isfinite(value)
            elif f['kind'] == 'checkbox': valid = isinstance(value, bool)
            elif f['kind'] == 'dropdown': valid = value in f['options']
            elif f['kind'] == 'date':
                try: date.fromisoformat(value)
                except (ValueError, TypeError): valid = False
            if not valid: raise HTTPException(400, f"Nilai {f['name']} tidak sesuai tipe field.")
    if update.get('reminder_at'):
        dt = datetime.fromisoformat(update['reminder_at'].replace('Z', '+00:00'))
        if not dt.tzinfo: raise HTTPException(400, 'Pengingat harus memiliki zona waktu.')
        update['reminder_at'] = dt.astimezone(timezone.utc).isoformat()

async def validate_task_ids(pid, ids):
    count = await db.tasks.count_documents({'project_id': pid, 'id': {'$in': list(set(ids))}})
    if count != len(set(ids)): raise HTTPException(400, 'Task harus berasal dari project yang sama.')