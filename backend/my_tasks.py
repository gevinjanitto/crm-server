from fastapi import APIRouter, Depends
from core import db, project_scope, project_statuses, MANAGERS
from auth import current_user
from task_rules import assignee_ids

router = APIRouter()

@router.get('/tasks/mine')
async def my_tasks(u=Depends(current_user)):
    if u['role'] not in MANAGERS + ['Developer']: return []
    projects = await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'name': 1, 'task_statuses': 1}).to_list(2000)
    info = {p['id']: p for p in projects}
    done = {pid: {s['name'] for s in project_statuses(p) if s.get('kind') == 'done'} for pid, p in info.items()}
    tasks = await db.tasks.find({'project_id': {'$in': list(info)}}, {'_id': 0}).to_list(10000)
    out = []
    for t in tasks:
        if t.get('status') in done[t['project_id']]: continue
        subs = [s for s in t.get('subtasks', []) if s.get('assigned_to') == u['id'] and not s.get('done')]
        if u['id'] not in assignee_ids(t) and not subs: continue
        out.append({'id': t['id'], 'project_id': t['project_id'], 'project_name': info[t['project_id']]['name'], 'title': t['title'],
                    'status': t.get('status', ''), 'priority': t.get('priority', ''), 'due_date': t.get('due_date'),
                    'subtasks': [s['title'] for s in subs] if u['id'] not in assignee_ids(t) else []})
    rank = {'Mendesak': 0, 'Tinggi': 1, 'Sedang': 2, 'Rendah': 3}
    return sorted(out, key=lambda x: (rank.get(x['priority'], 4), x['due_date'] or '9999', x['title']))
