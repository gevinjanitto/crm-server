from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from docstore import DuplicateKeyError
from core import db, uid, now, project_statuses, validate_assignee
from auth import current_user
from schemas import Record
from workspace_models import SprintInput, GoalInput, CapacityInput
from workspace_common import access, record, validate_task_ids
from task_rules import assignee_ids

router = APIRouter(prefix='/projects/{pid}/workspace')

def done_names(p): return [s['name'] for s in project_statuses(p) if s['kind'] == 'done']

@router.get('/sprints', response_model=list[Record])
async def sprints(pid: str, u=Depends(current_user)):
    p = await access(u, pid)
    tasks = await db.tasks.find({'project_id': pid}, {'_id': 0}).to_list(5000)
    rows = await db.workspace_sprints.find({'project_id': pid}, {'_id': 0}).sort('start_date', -1).to_list(100)
    for s in rows:
        group = [t for t in tasks if t.get('sprint_id') == s['id']]
        s.update(total=len(group), done=sum(t['status'] in done_names(p) for t in group), estimate=sum(t.get('estimate_hours', 0) for t in group))
    return rows

@router.post('/sprints', response_model=Record)
async def create_sprint(pid: str, data: SprintInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(mode='json'), 'created_at': now()}
    try: await db.workspace_sprints.insert_one(doc.copy())
    except DuplicateKeyError: raise HTTPException(400, 'Selesaikan sprint aktif sebelum memulai sprint berikutnya.')
    return doc

@router.patch('/sprints/{rid}', response_model=Record)
async def edit_sprint(pid: str, rid: str, data: SprintInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    old = await record('workspace_sprints', pid, rid)
    update = {**data.model_dump(mode='json'), 'updated_at': now()}
    try: await db.workspace_sprints.update_one({'id': rid}, {'$set': update})
    except DuplicateKeyError: raise HTTPException(400, 'Hanya satu sprint aktif per project.')
    return {**old, **update}

@router.delete('/sprints/{rid}')
async def delete_sprint(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True)
    await record('workspace_sprints', pid, rid)
    await db.workspace_sprints.delete_one({'id': rid})
    await db.tasks.update_many({'project_id': pid, 'sprint_id': rid}, {'$set': {'sprint_id': ''}})
    return {'message': 'Sprint dihapus; task dipindahkan ke backlog.'}

@router.get('/goals', response_model=list[Record])
async def goals(pid: str, u=Depends(current_user)):
    p = await access(u, pid)
    done = await db.tasks.distinct('id', {'project_id': pid, 'status': {'$in': done_names(p)}})
    rows = await db.workspace_goals.find({'project_id': pid}, {'_id': 0}).sort('created_at', -1).to_list(200)
    active_tasks = set(await db.tasks.distinct('id', {'project_id': pid}))
    for g in rows:
        if g['metric'] == 'tasks':
            g['task_ids'] = [i for i in g['task_ids'] if i in active_tasks]
            g['actual'] = len(set(g['task_ids']) & set(done)); g['total'] = len(g['task_ids'])
        else: g['actual'], g['total'] = g['current'], g['target']
        g['progress'] = min(100, round(g['actual'] / g['total'] * 100)) if g['total'] else 0
    return rows

@router.post('/goals', response_model=Record)
async def create_goal(pid: str, data: GoalInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    await validate_task_ids(pid, data.task_ids)
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(mode='json'), 'created_at': now()}
    await db.workspace_goals.insert_one(doc.copy())
    return doc

@router.patch('/goals/{rid}', response_model=Record)
async def edit_goal(pid: str, rid: str, data: GoalInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    old = await record('workspace_goals', pid, rid)
    await validate_task_ids(pid, data.task_ids)
    update = {**data.model_dump(mode='json'), 'updated_at': now()}
    await db.workspace_goals.update_one({'id': rid}, {'$set': update})
    return {**old, **update}

@router.delete('/goals/{rid}')
async def delete_goal(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True); await record('workspace_goals', pid, rid)
    await db.workspace_goals.delete_one({'id': rid})
    return {'message': 'Goal dihapus.'}

@router.post('/capacity', response_model=Record)
async def save_capacity(pid: str, data: CapacityInput, u=Depends(current_user)):
    p = await access(u, pid, write=True)
    await validate_assignee(data.user_id, p)
    doc = {'id': f'{pid}:{data.user_id}', 'project_id': pid, **data.model_dump(), 'updated_at': now()}
    await db.workspace_capacity.update_one({'id': doc['id']}, {'$set': doc}, upsert=True)
    return doc

@router.get('/workload')
async def workload(pid: str, week: date | None = None, u=Depends(current_user)):
    p = await access(u, pid, internal=True)
    start = week or date.today(); start -= timedelta(days=start.weekday()); end = start + timedelta(days=6)
    tasks = await db.tasks.find({'project_id': pid, 'status': {'$nin': done_names(p)}}, {'_id': 0}).to_list(5000)
    people = await db.users.find({'id': {'$in': p.get('assigned_to', [])}, 'active': True}, {'_id': 0, 'id': 1, 'name': 1}).to_list(100)
    capacities = {c['user_id']: c['hours'] for c in await db.workspace_capacity.find({'project_id': pid}, {'_id': 0}).to_list(100)}
    for person in people:
        assigned = [t for t in tasks if person['id'] in assignee_ids(t)]
        days = [0.0] * 5; scheduled = []
        for t in assigned:
            if not t.get('start_date') and not t.get('due_date'): continue
            a = date.fromisoformat(t.get('start_date') or t['due_date']); b = date.fromisoformat(t.get('due_date') or t['start_date'])
            duration = (b - a).days + 1
            weekdays = (duration // 7) * 5 + sum((a + timedelta(days=i)).weekday() < 5 for i in range(duration % 7))
            per_day = t.get('estimate_hours', 0) / max(1, weekdays) / max(1, len(assignee_ids(t)))
            if a <= end and b >= start: scheduled.append(t['id'])
            for i in range(5):
                if a <= start + timedelta(days=i) <= b: days[i] += per_day
        person.update(capacity=capacities.get(person['id'], 40), hours=round(sum(days), 1), days=[round(x, 1) for x in days], task_ids=scheduled, unscheduled=sum(not t.get('start_date') and not t.get('due_date') for t in assigned), unestimated=sum(not t.get('estimate_hours') for t in assigned))
    return {'start': start.isoformat(), 'end': end.isoformat(), 'people': people, 'unassigned': sum(not assignee_ids(t) for t in tasks)}

@router.get('/reports')
async def reports(pid: str, u=Depends(current_user)):
    p = await access(u, pid)
    tasks = await db.tasks.find({'project_id': pid}, {'_id': 0}).to_list(5000)
    names = done_names(p); done = [t for t in tasks if t['status'] in names]; today = date.today()
    trend = []
    for i in range(13, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        trend.append({'date': day, 'created': sum(t['created_at'][:10] == day for t in tasks), 'completed': sum((t.get('completed_at') or t['updated_at'])[:10] == day for t in done)})
    milestones = [{k: t.get(k) for k in ['id', 'title', 'status', 'due_date', 'start_date']} for t in tasks if t.get('milestone')]
    blocked = sum(any(d not in {t['id'] for t in done} for d in task.get('dependencies', [])) for task in tasks if task['status'] not in names)
    return {'total': len(tasks), 'done': len(done), 'blocked': blocked, 'overdue': sum(bool(t.get('due_date') and t['due_date'] < today.isoformat() and t['status'] not in names) for t in tasks),
            'estimated': sum(t.get('estimate_hours', 0) for t in tasks), 'actual': round(sum(e.get('seconds', 0) for t in tasks for e in t.get('time_entries', []) if e.get('ended_at')) / 3600, 1),
            'trend': trend, 'milestones': milestones, 'statuses': [{'name': s['name'], 'color': s['color'], 'count': sum(t['status'] == s['name'] for t in tasks)} for s in project_statuses(p)],
            'open_comments': await db.task_comments.count_documents({'project_id': pid, 'assigned_to': {'$exists': True, '$nin': ['', None]}, 'resolved': {'$ne': True}})}