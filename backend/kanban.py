from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from core import db, uid, now, authorize, project_scope, project_for, validate_assignee, project_statuses, recalc_progress, log_activity, trash_item, sync_task_members, MANAGERS
from auth import current_user
from schemas import Record, TaskInput, TaskUpdate, SubtaskInput, SubtaskUpdate, StatusColumnInput, StatusColumnUpdate, ReorderInput, TaskCommentInput, TimeEntryInput, BulkTaskInput
from documents import store_document
from storage import delete_object
from rich_text import clean_description
from notify import notify, notify_assignment, manager_ids
from task_rules import assignee_ids, normalize_assignees, validate_dates, validate_dependencies, ensure_completable
from ticket_status_sync import validate_ticket_move, sync_ticket_status
from workspace_common import validate_task_extensions, members
from workspace_engine import apply_automations
from docstore import DuplicateKeyError
import re

router = APIRouter()

def kind_of(p, status): return next((s['kind'] for s in project_statuses(p) if s['name'] == status), 'active')
def status_names(p): return [s['name'] for s in project_statuses(p)]
def fallback_status(p, kind='todo'): return next((s['name'] for s in project_statuses(p) if s['kind'] == kind), status_names(p)[0])
def secs(e): return e.get('seconds') or 0
def public_files(files): return [{k: v for k, v in a.items() if k != 'storage_path'} for a in files or []]

async def enrich(tasks, user=None):
    public_fields = set()
    if user and user['role'] not in MANAGERS + ['Developer']:
        public_fields = set(await db.workspace_fields.distinct('id', {'project_id': {'$in': list({t['project_id'] for t in tasks})}, 'visibility': 'Client'}))
    ids = {i for t in tasks for i in assignee_ids(t)} | {s.get('assigned_to') for t in tasks for s in t.get('subtasks', [])}
    users = await db.users.find({'id': {'$in': [i for i in ids if i]}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(500)
    names = {r['id']: r['name'] for r in users}
    projects = await db.projects.find({'id': {'$in': list({t['project_id'] for t in tasks})}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(2000)
    pnames = {p['id']: p['name'] for p in projects}
    tids = [t['id'] for t in tasks]
    counts, comments = {}, {}
    async for d in db.project_documents.aggregate([{'$match': {'task_id': {'$in': tids}, 'is_deleted': False}}, {'$group': {'_id': '$task_id', 'n': {'$sum': 1}}}]): counts[d['_id']] = d['n']
    async for d in db.task_comments.aggregate([{'$match': {'task_id': {'$in': tids}}}, {'$group': {'_id': '$task_id', 'n': {'$sum': 1}}}]): comments[d['_id']] = d['n']
    for t in tasks:
        t['assigned_name'] = names.get(t.get('assigned_to'), '')
        t['assignee_ids'] = assignee_ids(t)
        t['assignees'] = [{'id': i, 'name': names.get(i, 'Pengguna tidak aktif')} for i in t['assignee_ids']]
        t.setdefault('dependencies', [])
        t.setdefault('list_id', ''); t.setdefault('sprint_id', ''); t.setdefault('milestone', False); t.setdefault('custom_fields', {})
        if user and user['role'] not in MANAGERS + ['Developer']:
            t['custom_fields'] = {k: v for k, v in t['custom_fields'].items() if k in public_fields}
            t.pop('reminder_at', None); t.pop('reminder_sent_at', None)
        for s in t.get('subtasks', []): s['assigned_name'] = names.get(s.get('assigned_to'), ''); s.setdefault('description', ''); s['images'] = public_files(s.get('images'))
        t['description_images'] = public_files(t.get('description_images'))
        t['project_name'] = pnames.get(t['project_id'], ''); t['document_count'] = counts.get(t['id'], 0); t['comment_count'] = comments.get(t['id'], 0)
        entries = t.get('time_entries', [])
        t['time_total'] = sum(secs(e) for e in entries if e.get('ended_at'))
        t['running_entry'] = next((e for e in entries if not e.get('ended_at') and user and e['user_id'] == user['id']), None)
        t['running_count'] = sum(1 for e in entries if not e.get('ended_at'))
        t.setdefault('tags', []); t.setdefault('estimate_hours', 0); t.setdefault('order', 0); t.setdefault('start_date', None)
    return tasks

async def create_task(pid, u, title, description='', status='Belum Mulai', server='Belum Naik', assigned_to='', due_date=None, priority='Sedang', source='manual', source_id='', subtasks=None, tags=None, start_date=None, estimate_hours=0, assignee_ids=None, dependencies=None, list_id='', sprint_id='', milestone=False, custom_fields=None, reminder_at=None, task_id=None):
    p = await db.projects.find_one({'id': pid}, {'_id': 0}) or {}
    if status not in status_names(p): status = fallback_status(p)
    order = (await db.tasks.count_documents({'project_id': pid})) + 1
    t = {'id': uid(), 'project_id': pid, 'title': title, 'description': description, 'status': status, 'server': server, 'assigned_to': assigned_to or '', 'due_date': due_date, 'start_date': start_date, 'priority': priority, 'source': source, 'source_id': source_id,
         'tags': tags or [], 'estimate_hours': estimate_hours or 0, 'order': order, 'time_entries': [],
         'assignee_ids': assignee_ids if assignee_ids is not None else ([assigned_to] if assigned_to else []), 'dependencies': dependencies or [],
         'subtasks': [{'id': uid(), 'title': s.strip(), 'done': False, 'assigned_to': ''} for s in (subtasks or []) if s.strip()], 'created_at': now(), 'updated_at': now(), 'created_by': u['id']}
    if task_id: t['id'] = task_id
    t.update(list_id=list_id, sprint_id=sprint_id, milestone=milestone, custom_fields=custom_fields or {}, reminder_at=reminder_at, reminder_sent_at=None, completed_at=now() if kind_of(p, status) == 'done' else None)
    try: await db.tasks.insert_one(t.copy())
    except DuplicateKeyError:
        if task_id: return await db.tasks.find_one({'id': task_id}, {'_id': 0})
        raise
    if t['assignee_ids']: await sync_task_members(pid)
    for person in t['assignee_ids']:
        await notify([person], 'Penugasan task', title, 'penugasan', f'/projects/{pid}/kanban?task={t["id"]}', pid, 'task', t['id'], u if u.get('id') != 'system' else None, email=False)
    return await apply_automations(p, t, 'task_created', u)

async def sync_task_status(source, source_id, status):
    t = await db.tasks.find_one({'source': source, 'source_id': source_id}, {'_id': 0, 'project_id': 1})
    if not t: return
    p = await db.projects.find_one({'id': t['project_id']}, {'_id': 0}) or {}
    target = status if status in status_names(p) else fallback_status(p, {'Selesai': 'done', 'Dikerjakan': 'active'}.get(status, 'todo'))
    await db.tasks.update_many({'source': source, 'source_id': source_id}, {'$set': {'status': target, 'updated_at': now()}})

async def sync_source(t, status, p, actor=None):
    kind, src, sid = kind_of(p, status), t.get('source'), t.get('source_id')
    if src in ['revision', 'maintenance']:
        coll = 'maintenances' if src == 'maintenance' else 'revisions'
        if src == 'maintenance': s = {'done': 'Selesai', 'active': 'Testing' if status == 'Testing' else 'Development', 'todo': 'Belum dikerjakan'}[kind]
        else: s = {'done': 'Selesai', 'active': 'Dikerjakan', 'todo': 'Terbuka'}[kind]
        await db[coll].update_one({'id': sid}, {'$set': {'status': s, 'completed_at': now() if kind == 'done' else None}})
        if src == 'maintenance' and kind == 'active': await db[coll].update_one({'id': sid, 'started_date': None}, {'$set': {'started_date': now()[:10]}})
    elif src == 'ticket':
        await sync_ticket_status(t, status, p, actor)
    elif src == 'feature':
        s = {'done': 'Selesai', 'active': 'Dikerjakan', 'todo': 'Belum dimulai'}[kind]
        await db.project_features.update_one({'id': sid}, {'$set': {'status': s}})
        await recalc_progress(t['project_id'])

async def sync_assignees(t, update):
    collection = {'ticket': 'tickets', 'maintenance': 'maintenances', 'revision': 'revisions', 'feature': 'project_features'}.get(t.get('source'))
    if not collection: return
    fields = {}
    if 'assigned_to' in update: fields['assigned_to'] = update['assigned_to']
    if 'priority' in update and collection != 'project_features': fields['priority'] = update['priority']
    if 'due_date' in update and collection != 'tickets': fields['due_date'] = update['due_date']
    if 'start_date' in update and collection in ['maintenances', 'revisions']: fields['started_date'] = update['start_date']
    if fields:
        await db[collection].update_one({'id': t.get('source_id'), 'project_id': t['project_id']}, {'$set': {**fields, 'updated_at': now()}})

def can_edit(u, t):
    if u['role'] in MANAGERS or (u['role'] == 'Developer' and (not assignee_ids(t) or u['id'] in assignee_ids(t))): return
    raise HTTPException(403, 'Task ini ditugaskan kepada developer lain.')

async def task_for(u, pid, tid, action='task.read'):
    p = await project_for(u, pid, action)
    t = await db.tasks.find_one({'id': tid, 'project_id': pid}, {'_id': 0})
    if not t: raise HTTPException(404, 'Task tidak ditemukan.')
    return p, t

async def one(tid, u):
    t = await db.tasks.find_one({'id': tid}, {'_id': 0})
    return (await enrich([t], u))[0]

# ---------- status columns ----------
@router.get('/projects/{pid}/statuses', response_model=list[Record])
async def get_statuses(pid: str, u=Depends(current_user)):
    return project_statuses(await project_for(u, pid, 'task.read'))

async def save_statuses(pid, cols):
    await db.projects.update_one({'id': pid}, {'$set': {'task_statuses': cols, 'updated_at': now()}})
    return cols

@router.post('/projects/{pid}/statuses', response_model=list[Record])
async def add_status(pid: str, data: StatusColumnInput, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write'); cols = project_statuses(p)
    if data.name in [c['name'] for c in cols]: raise HTTPException(400, 'Nama status sudah dipakai.')
    await log_activity(u, 'buat', 'status kanban', '', data.name, pid)
    return await save_statuses(pid, cols + [{'id': uid(), **data.model_dump()}])

@router.patch('/projects/{pid}/statuses/{sid}', response_model=list[Record])
async def edit_status(pid: str, sid: str, data: StatusColumnUpdate, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write'); cols = project_statuses(p)
    c = next((x for x in cols if x['id'] == sid), None)
    if not c: raise HTTPException(404, 'Status tidak ditemukan.')
    update = data.model_dump(exclude_none=True)
    previous = dict(c)
    if update.get('name') and update['name'] != c['name'] and update['name'] in [x['name'] for x in cols]:
        raise HTTPException(400, 'Nama status sudah dipakai.')
    c.update(update)
    if c['name'] != previous['name'] or c['kind'] != previous['kind']:
        next_project = {**p, 'task_statuses': cols}
        affected = await db.tasks.find({'project_id': pid, 'status': previous['name']}, {'_id': 0}).to_list(10000)
        completing = [t['id'] for t in affected]
        for t in affected:
            await ensure_completable(next_project, {**t, 'status': c['name']}, completing)
            await validate_ticket_move(t, c['name'], next_project)
        task_update = {'status': c['name'], 'updated_at': now()}
        if c['kind'] != previous['kind']:
            task_update['completed_at'] = now() if c['kind'] == 'done' else None
        await db.tasks.update_many({'project_id': pid, 'status': previous['name']}, {'$set': task_update})
        for t in affected:
            await sync_source(t, c['name'], next_project, u)
    await log_activity(u, 'ubah', 'status kanban', sid, c['name'], pid, update)
    return await save_statuses(pid, cols)

@router.delete('/projects/{pid}/statuses/{sid}', response_model=list[Record])
async def delete_status(pid: str, sid: str, move_to: str = '', u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write'); cols = project_statuses(p)
    c = next((x for x in cols if x['id'] == sid), None)
    if not c: raise HTTPException(404, 'Status tidak ditemukan.')
    rest = [x for x in cols if x['id'] != sid]
    if not rest: raise HTTPException(400, 'Minimal harus ada satu status.')
    if move_to and move_to not in [x['name'] for x in rest]: raise HTTPException(400, 'Status tujuan tidak ditemukan.')
    target = move_to or rest[0]['name']
    affected = await db.tasks.find({'project_id': pid, 'status': c['name']}, {'_id': 0}).to_list(10000)
    completing = [t['id'] for t in affected]
    for t in affected:
        await ensure_completable(p, {**t, 'status': target}, completing)
        await validate_ticket_move(t, target, p)
    await db.tasks.update_many({'project_id': pid, 'status': c['name']}, {'$set': {
        'status': target, 'updated_at': now(), 'completed_at': now() if kind_of(p, target) == 'done' else None}})
    for t in affected:
        await sync_source(t, target, p, u)
    await log_activity(u, 'hapus', 'status kanban', sid, c['name'], pid, {'task_dipindah_ke': target})
    return await save_statuses(pid, rest)

@router.post('/projects/{pid}/statuses/reorder', response_model=list[Record])
async def reorder_statuses(pid: str, data: ReorderInput, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write'); cols = project_statuses(p)
    by_id = {c['id']: c for c in cols}
    ordered = [by_id[i] for i in data.ids if i in by_id] + [c for c in cols if c['id'] not in data.ids]
    return await save_statuses(pid, ordered)

# ---------- tasks ----------
@router.get('/tasks', response_model=list[Record])
async def all_tasks(u=Depends(current_user)):
    await authorize(u, 'task.read')
    pids = await db.projects.distinct('id', project_scope(u))
    return await enrich(await db.tasks.find({'project_id': {'$in': pids}}, {'_id': 0}).sort('order', 1).to_list(5000), u)

@router.get('/projects/{pid}/tasks', response_model=list[Record])
async def project_tasks(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'task.read')
    return await enrich(await db.tasks.find({'project_id': pid}, {'_id': 0}).sort('order', 1).to_list(2000), u)

@router.get('/projects/{pid}/tasks/stats')
async def task_stats(pid: str, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.read')
    tasks = await enrich(await db.tasks.find({'project_id': pid}, {'_id': 0}).to_list(2000), u)
    today = datetime.now(timezone.utc).date().isoformat(); week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cols = project_statuses(p); done_names = {c['name'] for c in cols if c['kind'] == 'done'}
    by_assignee = {}
    for t in tasks:
        for person in t['assignees'] or [{'id': '', 'name': 'Belum ditugaskan'}]:
            a = by_assignee.setdefault(person['id'], {'name': person['name'], 'total': 0, 'done': 0, 'time': 0})
            a['total'] += 1; a['done'] += t['status'] in done_names
            a['time'] += sum(secs(e) for e in t.get('time_entries', []) if e.get('ended_at') and e.get('user_id') == person['id'])
    return {
        'total': len(tasks), 'done': sum(t['status'] in done_names for t in tasks),
        'overdue': sum(1 for t in tasks if t.get('due_date') and t['status'] not in done_names and t['due_date'] < today),
        'unassigned': sum(1 for t in tasks if not t.get('assigned_to')),
        'completed_week': sum(1 for t in tasks if t['status'] in done_names and t.get('updated_at', '') >= week_ago),
        'time_total': sum(t['time_total'] for t in tasks), 'estimate_total': sum(t.get('estimate_hours') or 0 for t in tasks),
        'by_status': [{'name': c['name'], 'color': c['color'], 'count': sum(t['status'] == c['name'] for t in tasks)} for c in cols],
        'by_priority': [{'name': pr, 'count': sum(t.get('priority') == pr for t in tasks)} for pr in ['Mendesak', 'Tinggi', 'Sedang', 'Rendah']],
        'by_assignee': sorted(by_assignee.values(), key=lambda a: -a['total']),
        'by_source': [{'name': s, 'count': sum(t.get('source') == s for t in tasks)} for s in ['manual', 'feature', 'revision', 'maintenance', 'ticket']],
    }

@router.post('/projects/{pid}/tasks', response_model=Record)
async def add_task(pid: str, data: TaskInput, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write')
    body = data.model_dump(mode='json', exclude_none=True)
    await normalize_assignees(body, p)
    await validate_task_extensions(pid, body)
    validate_dates(body)
    if body['status'] not in status_names(p): raise HTTPException(400, 'Status tidak valid.')
    body['dependencies'] = await validate_dependencies(pid, '', body.get('dependencies', []))
    await ensure_completable(p, body)
    t = await create_task(pid, u, **body)
    await log_activity(u, 'buat', 'task', t['id'], t['title'], pid)
    return (await enrich([t], u))[0]

@router.post('/projects/{pid}/tasks/bulk')
async def bulk_tasks(pid: str, data: BulkTaskInput, u=Depends(current_user)):
    p = await project_for(u, pid, 'task.write')
    q = {'id': {'$in': data.ids}, 'project_id': pid}
    if data.delete:
        async for t in db.tasks.find(q, {'_id': 0}): await trash_item(u, 'tasks', t, 'task', t['title'])
        await db.project_documents.update_many({'task_id': {'$in': data.ids}}, {'$set': {'is_deleted': True}})
        await db.tasks.update_many({'project_id': pid}, {'$pull': {'dependencies': {'$in': data.ids}}})
        await db.task_schedules.update_many({'project_id': pid, 'task_id': {'$in': data.ids}}, {'$set': {'enabled': False}})
        return {'message': f'{len(data.ids)} task dipindahkan ke arsip.'}
    update = {k: v for k, v in data.model_dump(exclude_none=True).items() if k in ['status', 'assigned_to', 'priority', 'list_id', 'sprint_id']}
    await validate_task_extensions(pid, update)
    if 'status' in update and update['status'] not in status_names(p): raise HTTPException(400, 'Status tidak valid.')
    await normalize_assignees(update, p)
    if not update: raise HTTPException(400, 'Tidak ada perubahan.')
    affected = await db.tasks.find(q, {'_id': 0}).to_list(2000)
    if 'status' in update:
        for t in affected:
            await ensure_completable(p, {**t, **update}, data.ids)
            await validate_ticket_move(t, update['status'], p)
        update['completed_at'] = now() if kind_of(p, update['status']) == 'done' else None
    await db.tasks.update_many(q, {'$set': {**update, 'updated_at': now()}})
    if 'assignee_ids' in update: await sync_task_members(pid)
    if 'assignee_ids' in update:
        for t in affected:
            await sync_assignees(t, update)
            for person in set(update['assignee_ids']) - set(assignee_ids(t)):
                await notify_assignment(person, 'task Kanban', t['title'], pid, t.get('due_date'), actor=u)
    await log_activity(u, 'ubah massal', 'task', '', f'{len(data.ids)} task', pid, update)
    if 'status' in update:
        for old in affected:
            await sync_source(old, update['status'], p, u)
            if old['status'] != update['status']: await apply_automations(p, {**old, **update}, 'status_changed', u)
    return {'message': f'{len(data.ids)} task diperbarui.'}

def drop_unused_images(t, update):
    """Sanitize rich description; delete photos removed from it (10-min grace for in-flight uploads)."""
    update['description_html'], update['description'], used = clean_description(update['description_html'])
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    images = t.get('description_images') or []
    stale = [a for a in images if a['id'] not in used and a.get('created_at', '') < cutoff]
    if not stale: return
    update['description_images'] = [a for a in images if a not in stale]
    for a in stale:
        try: delete_object(a['storage_path'])
        except Exception: pass

def drop_unused_subtask_images(s, update):
    update['description_html'], update['description'], used = clean_description(update['description_html'])
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    images = s.get('images') or []
    stale = [a for a in images if a['id'] not in used and a.get('created_at', '') < cutoff]
    update['images'] = [a for a in images if a not in stale]
    for a in stale:
        try: delete_object(a['storage_path'])
        except Exception: pass

@router.patch('/projects/{pid}/tasks/{tid}', response_model=Record)
async def edit_task(pid: str, tid: str, data: TaskUpdate, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress')
    update = data.model_dump(mode='json', exclude_unset=True)
    for k in ['title', 'status', 'server', 'priority', 'tags', 'order', 'estimate_hours', 'description', 'assigned_to', 'assignee_ids', 'dependencies', 'list_id', 'sprint_id', 'milestone', 'custom_fields']:
        if k in update and update[k] is None: update.pop(k)
    # Developer yang memiliki akses project (anggota / minimal 1 task) boleh memindahkan semua kartu.
    if not (u['role'] == 'Developer' and set(update) <= {'status', 'server', 'order'}): can_edit(u, t)
    if u['role'] == 'Developer' and set(update) - {'status', 'server', 'order'}: raise HTTPException(403, 'Developer hanya dapat memperbarui status, server, dan urutan.')
    if 'status' in update and update['status'] not in status_names(p): raise HTTPException(400, 'Status tidak valid.')
    await normalize_assignees(update, p)
    await validate_task_extensions(pid, update)
    if 'reminder_at' in update and update['reminder_at'] != t.get('reminder_at'): update['reminder_sent_at'] = None
    if 'status' in update and update['status'] != t['status']: update['completed_at'] = now() if kind_of(p, update['status']) == 'done' else None
    if 'dependencies' in update: update['dependencies'] = await validate_dependencies(pid, tid, update['dependencies'])
    if 'start_date' in update or 'due_date' in update: validate_dates({**t, **update})
    if 'status' in update or 'dependencies' in update: await ensure_completable(p, {**t, **update})
    if 'status' in update: await validate_ticket_move(t, update['status'], p)
    if 'tags' in update: update['tags'] = [x.strip() for x in update['tags'] if x.strip()][:10]
    if update.get('description_html') is not None: drop_unused_images(t, update)
    else: update.pop('description_html', None)
    update['updated_at'] = now()
    await db.tasks.update_one({'id': tid}, {'$set': update})
    if 'assignee_ids' in update: await sync_task_members(pid)
    await sync_assignees(t, update)
    for person in set(update.get('assignee_ids', [])) - set(assignee_ids(t)):
        await notify_assignment(person, 'task Kanban', update.get('title', t['title']), pid, update.get('due_date', t.get('due_date')), actor=u)
    if 'status' in update:
        await sync_source(t, update['status'], p, u)
    if 'status' in update and update['status'] != t['status']:
        audience = list(set(assignee_ids({**t, **update}) + (await manager_ids() if u['role'] == 'Developer' else [])))
        await notify(audience, f"Task \"{t['title']}\" → {update['status']}", f"{u['name']} memindahkan task ke {update['status']} pada project {p.get('name', '')}.", 'task', f'/projects/{pid}', pid, 'task', tid, u, email=False)
    changed = {k: v for k, v in update.items() if k != 'updated_at' and t.get(k) != v}
    if changed and set(changed) != {'order'}: await log_activity(u, 'ubah status' if 'status' in changed else 'ubah', 'task', tid, t['title'], pid, {'dari': t['status'], 'ke': changed['status']} if 'status' in changed else changed)
    if 'status' in changed: await apply_automations(p, {**t, **update}, 'status_changed', u)
    return await one(tid, u)

@router.delete('/projects/{pid}/tasks/{tid}')
async def delete_task(pid: str, tid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.write')
    comments = await db.task_comments.find({'task_id': tid}, {'_id': 0}).to_list(1000)
    await trash_item(u, 'tasks', t, 'task', t['title'], [{'collection': 'task_comments', 'docs': comments}])
    await db.project_documents.update_many({'task_id': tid}, {'$set': {'is_deleted': True}})
    await db.tasks.update_many({'project_id': pid}, {'$pull': {'dependencies': tid}})
    await db.task_schedules.update_many({'project_id': pid, 'task_id': tid}, {'$set': {'enabled': False}})
    return {'message': 'Task dipindahkan ke arsip.'}

# ---------- subtasks ----------
@router.post('/projects/{pid}/tasks/{tid}/subtasks', response_model=Record)
async def add_subtask(pid: str, tid: str, data: SubtaskInput, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    await validate_assignee(data.assigned_to, p)
    s = {**data.model_dump(), 'id': uid(), 'done': False}
    await db.tasks.update_one({'id': tid}, {'$push': {'subtasks': s}, '$set': {'updated_at': now()}})
    if data.assigned_to: await notify_assignment(data.assigned_to, 'subtask', f"{data.title} ({t['title']})", pid, t.get('due_date'), actor=u)
    return await one(tid, u)

@router.patch('/projects/{pid}/tasks/{tid}/subtasks/{sid}', response_model=Record)
async def edit_subtask(pid: str, tid: str, sid: str, data: SubtaskUpdate, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    subs = t.get('subtasks', []); s = next((x for x in subs if x['id'] == sid), None)
    if not s: raise HTTPException(404, 'Subtask tidak ditemukan.')
    update = data.model_dump(exclude_none=True)
    if 'description_html' in update: drop_unused_subtask_images(s, update)
    if update.get('assigned_to'): await validate_assignee(update['assigned_to'], p)
    if update.get('assigned_to') and update['assigned_to'] != s.get('assigned_to'): await notify_assignment(update['assigned_to'], 'subtask', f"{s['title']} ({t['title']})", pid, t.get('due_date'), actor=u)
    s.update(update)
    await db.tasks.update_one({'id': tid}, {'$set': {'subtasks': subs, 'updated_at': now()}})
    return await one(tid, u)

@router.delete('/projects/{pid}/tasks/{tid}/subtasks/{sid}')
async def delete_subtask(pid: str, tid: str, sid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    s = next((x for x in t.get('subtasks', []) if x['id'] == sid), None)
    await db.tasks.update_one({'id': tid}, {'$pull': {'subtasks': {'id': sid}}, '$set': {'updated_at': now()}})
    for a in (s or {}).get('images') or []:
        try: delete_object(a['storage_path'])
        except Exception: pass
    return {'message': 'Subtask dihapus.'}

# ---------- comments ----------
@router.get('/projects/{pid}/tasks/{tid}/comments', response_model=list[Record])
async def task_comments(pid: str, tid: str, u=Depends(current_user)):
    await task_for(u, pid, tid)
    rows = await db.task_comments.find({'task_id': tid}, {'_id': 0}).sort('created_at', 1).to_list(1000)
    return [{**c, 'attachments': public_files(c.get('attachments'))} for c in rows]

async def check_comment(p, u, message, assigned_to, mention_ids=None):
    people = await members(p)
    by_id = {m['id']: m for m in people}
    usernames = re.findall(r'(?<!\w)@([a-zA-Z0-9_.-]+)', message)
    mention_ids = list(set((mention_ids or []) + [m['id'] for m in people if m.get('username') in usernames]))
    if any(i not in by_id for i in mention_ids): raise HTTPException(400, 'Mention harus merupakan anggota project.')
    if assigned_to and (assigned_to not in by_id or by_id[assigned_to]['role'] == 'Client' or u['role'] not in MANAGERS + ['Developer']): raise HTTPException(403, 'Komentar hanya dapat ditugaskan oleh tim internal kepada anggota internal project.')
    return by_id, mention_ids

async def save_comment(pid, tid, u, message, assigned_to, by_id, mention_ids, attachments=None):
    c = {'id': uid(), 'task_id': tid, 'project_id': pid, 'message': message, 'author_id': u['id'], 'author_name': u['name'], 'author_role': u['role'], 'created_at': now()}
    c.update(mentions=[{'id': i, 'name': by_id[i]['name']} for i in mention_ids], assigned_to=assigned_to, assigned_name=by_id.get(assigned_to, {}).get('name', ''), resolved=False, attachments=attachments or [])
    await db.task_comments.insert_one(c.copy())
    text = message or f"Mengirim {len(attachments or [])} lampiran."
    await notify(mention_ids, f"{u['name']} menyebut Anda", text[:200], 'mention', f'/projects/{pid}/kanban?task={tid}', pid, 'task', tid, u, email=False)
    if assigned_to: await notify([assigned_to], 'Komentar ditugaskan kepada Anda', text[:200], 'penugasan', f'/projects/{pid}/kanban?task={tid}', pid, 'task', tid, u, email=False)
    t = await db.tasks.find_one({'id': tid}, {'_id': 0, 'title': 1, 'assigned_to': 1, 'assignee_ids': 1, 'created_by': 1})
    await notify(assignee_ids(t) + [t.get('created_by', '')] + await manager_ids(), f"Komentar baru di task \"{t['title']}\"", f"{u['name']}: {text[:160]}", 'task', f'/projects/{pid}', pid, 'task', tid, u, email=False)
    return {**c, 'attachments': public_files(c['attachments'])}

@router.post('/projects/{pid}/tasks/{tid}/comments', response_model=Record)
async def add_comment(pid: str, tid: str, data: TaskCommentInput, u=Depends(current_user)):
    p, task = await task_for(u, pid, tid)
    by_id, mention_ids = await check_comment(p, u, data.message, data.assigned_to, data.mention_ids)
    return await save_comment(pid, tid, u, data.message, data.assigned_to, by_id, mention_ids)

@router.delete('/projects/{pid}/tasks/{tid}/comments/{cid}')
async def delete_comment(pid: str, tid: str, cid: str, u=Depends(current_user)):
    await task_for(u, pid, tid)
    q = {'id': cid, 'task_id': tid}
    if u['role'] not in MANAGERS: q['author_id'] = u['id']
    c = await db.task_comments.find_one(q, {'_id': 0})
    if not c: raise HTTPException(404, 'Komentar tidak ditemukan.')
    await db.task_comments.delete_one(q)
    for a in c.get('attachments') or []:
        try: delete_object(a['storage_path'])
        except Exception: pass
    await log_activity(u, 'hapus', 'komentar', cid, '', pid, {'task_id': tid})
    return {'message': 'Komentar dihapus.'}

# ---------- time tracking ----------
@router.post('/projects/{pid}/tasks/{tid}/timer', response_model=Record)
async def toggle_timer(pid: str, tid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    entries = t.get('time_entries', [])
    running = next((e for e in entries if not e.get('ended_at') and e['user_id'] == u['id']), None)
    if running:
        started = datetime.fromisoformat(running['started_at'])
        running['ended_at'] = now(); running['seconds'] = max(1, int((datetime.now(timezone.utc) - started).total_seconds()))
    else:
        entries.append({'id': uid(), 'user_id': u['id'], 'user_name': u['name'], 'started_at': now(), 'ended_at': None, 'seconds': 0, 'note': '', 'manual': False})
    await db.tasks.update_one({'id': tid}, {'$set': {'time_entries': entries, 'updated_at': now()}})
    return await one(tid, u)

@router.post('/projects/{pid}/tasks/{tid}/time', response_model=Record)
async def add_time(pid: str, tid: str, data: TimeEntryInput, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    at = datetime.combine(data.date, datetime.min.time(), tzinfo=timezone.utc).isoformat() if data.date else now()
    e = {'id': uid(), 'user_id': u['id'], 'user_name': u['name'], 'started_at': at, 'ended_at': at, 'seconds': data.minutes * 60, 'note': data.note, 'manual': True}
    await db.tasks.update_one({'id': tid}, {'$push': {'time_entries': e}, '$set': {'updated_at': now()}})
    return await one(tid, u)

@router.delete('/projects/{pid}/tasks/{tid}/time/{eid}', response_model=Record)
async def delete_time(pid: str, tid: str, eid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress')
    e = next((x for x in t.get('time_entries', []) if x['id'] == eid), None)
    if not e: raise HTTPException(404, 'Catatan waktu tidak ditemukan.')
    if u['role'] not in MANAGERS and e['user_id'] != u['id']: raise HTTPException(403, 'Hanya pemilik catatan yang dapat menghapus.')
    await db.tasks.update_one({'id': tid}, {'$pull': {'time_entries': {'id': eid}}, '$set': {'updated_at': now()}})
    await log_activity(u, 'hapus', 'catatan waktu', eid, t['title'], pid, {'detik': e.get('seconds'), 'oleh': e.get('user_name')})
    return await one(tid, u)

# ---------- documents ----------
@router.get('/projects/{pid}/tasks/{tid}/documents', response_model=list[Record])
async def task_documents(pid: str, tid: str, u=Depends(current_user)):
    await task_for(u, pid, tid)
    return await db.project_documents.find({'task_id': tid, 'is_deleted': False}, {'_id': 0, 'storage_path': 0}).sort('created_at', -1).to_list(200)

@router.post('/projects/{pid}/tasks/{tid}/documents', response_model=Record)
async def upload_task_document(pid: str, tid: str, file: UploadFile = File(...), u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    return await store_document(pid, u, file, 'Lampiran Task', 'Internal', tid)

