from fastapi import APIRouter, Depends
from core import db, authorize, project_statuses
from auth import current_user
from task_rules import assignee_ids

router = APIRouter()


@router.get('/admin/tasks-by-user')
async def tasks_by_user(u=Depends(current_user)):
    await authorize(u, 'team.read')
    projects = {p['id']: p for p in await db.projects.find({}, {'_id': 0, 'id': 1, 'name': 1, 'task_statuses': 1}).to_list(5000)}
    done = {pid: {s['name'] for s in project_statuses(p) if s.get('kind') == 'done'} for pid, p in projects.items()}
    users = {x['id']: x for x in await db.users.find({}, {'_id': 0, 'id': 1, 'name': 1, 'role': 1, 'username': 1}).to_list(2000)}
    tasks = await db.tasks.find({'project_id': {'$in': list(projects)}}, {'_id': 0}).to_list(20000)
    groups = {}
    for t in tasks:
        if t.get('status') in done[t['project_id']]: continue
        row = {'id': t['id'], 'project_id': t['project_id'], 'project_name': projects[t['project_id']]['name'], 'title': t['title'],
               'status': t.get('status', ''), 'priority': t.get('priority', ''), 'due_date': t.get('due_date'), 'subtasks': []}
        owners = assignee_ids(t)
        for s in t.get('subtasks', []):
            if s.get('assigned_to') and not s.get('done') and s['assigned_to'] not in owners:
                groups.setdefault(s['assigned_to'], {}).setdefault(t['id'], {**row, 'subtasks': []})['subtasks'].append(s['title'])
        for o in owners or ['']: groups.setdefault(o, {})[t['id']] = row
    rank = {'Mendesak': 0, 'Tinggi': 1, 'Sedang': 2, 'Rendah': 3}
    out = []
    for user_id, items in groups.items():
        x = users.get(user_id, {})
        rows = sorted(items.values(), key=lambda r: (rank.get(r['priority'], 4), r['due_date'] or '9999', r['title']))
        out.append({'user_id': user_id, 'name': x.get('name') or ('Belum ditugaskan' if not user_id else 'User terhapus'), 'role': x.get('role', ''), 'tasks': rows})
    return sorted(out, key=lambda g: (not g['user_id'], -len(g['tasks']), g['name'].lower()))
