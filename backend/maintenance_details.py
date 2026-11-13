from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from core import db, uid, now, project_for, log_activity
from auth import current_user
from schemas import Input, Record
from kanban import create_task, build_subtasks, subtask_descendants, fallback_status, kind_of
from task_rules import assignee_ids

router = APIRouter()
SYSTEM = {'id': 'system', 'name': 'Sistem', 'role': 'Admin'}


class DetailsInput(Input):
    items: list[dict] = Field(min_length=1, max_length=100)


def _items(subtasks, title):
    items = [({'title': s} if isinstance(s, str) else s) for s in subtasks or []]
    items = [s for s in items if (s.get('title') or '').strip()]
    return items or [{'title': title}]


async def create_details(pid, u, m, items):
    """Each rincian becomes its own Kanban card; nested children become that card's subtasks."""
    ids = []
    status = 'Dikerjakan' if m.get('status') == 'Development' else 'Belum Mulai'
    for it in items:
        t = await create_task(pid, u, title=it['title'].strip(), description=(it.get('description') or '').strip(), status=status,
                              assigned_to=it.get('assigned_to') or m.get('assigned_to') or '', due_date=m.get('due_date'), start_date=m.get('started_date'),
                              priority=m.get('priority') or 'Sedang', source='maintenance', source_id=m['id'], subtasks=it.get('children') or [], tags=[m['kind'], 'Rincian maintenance'])
        ids.append(t['id'])
    return ids


async def split_legacy(project_ids):
    """Old maintenance = 1 card with subtasks: turn each top-level subtask into its own rincian card."""
    if not project_ids: return
    for m in await db.maintenances.find({'project_id': {'$in': project_ids}, 'details_v2': None}, {'_id': 0}).to_list(50000):
        t = await db.tasks.find_one({'id': m.get('task_id')}, {'_id': 0}) if m.get('task_id') else None
        tops = [s for s in (t or {}).get('subtasks') or [] if not s.get('parent_id')]
        if t and len(tops) > 1:
            p = await db.projects.find_one({'id': m['project_id']}, {'_id': 0}) or {}
            subs = t['subtasks']
            def branch(top):
                ids = subtask_descendants(subs, top['id']) - {top['id']}
                return [{**s, 'parent_id': '' if s.get('parent_id') == top['id'] else s['parent_id']} for s in subs if s['id'] in ids]
            first, rest = tops[0], tops[1:]
            await db.tasks.update_one({'id': t['id']}, {'$set': {'title': first['title'], 'subtasks': branch(first), 'updated_at': now()}})
            for top in rest:
                status = fallback_status(p, 'done') if top.get('done') else t['status']
                n = await create_task(m['project_id'], SYSTEM, title=top['title'], description=top.get('description') or '', status=status,
                                      due_date=t.get('due_date'), start_date=t.get('start_date'), priority=t.get('priority') or 'Sedang',
                                      source='maintenance', source_id=m['id'], subtasks=[], tags=t.get('tags') or [m['kind']])
                fields = {'subtasks': branch(top), 'assigned_to': top.get('assigned_to') or t.get('assigned_to', ''),
                          'assignee_ids': [top['assigned_to']] if top.get('assigned_to') else t.get('assignee_ids', [])}
                await db.tasks.update_one({'id': n['id']}, {'$set': fields})
        await db.maintenances.update_one({'id': m['id']}, {'$set': {'details_v2': True}})


async def merge_details(project_ids):
    """Merge old 'rincian' cards back into one Kanban card per maintenance; each rincian becomes a subtask."""
    if not project_ids: return
    for m in await db.maintenances.find({'project_id': {'$in': project_ids}, 'details_v3': None}, {'_id': 0}).to_list(50000):
        ts = await db.tasks.find({'source': 'maintenance', 'source_id': m['id']}, {'_id': 0}).sort('created_at', 1).to_list(500)
        main = next((t for t in ts if t['id'] == m.get('task_id')), ts[0] if ts else None)
        if main and (len(ts) > 1 or main['title'] != m['title']):
            p = await db.projects.find_one({'id': m['project_id']}, {'_id': 0}) or {}
            subs, entries, people = [], [], []
            for t in [main] + [t for t in ts if t['id'] != main['id']]:
                sid = uid()
                subs.append({'id': sid, 'title': t['title'], 'done': kind_of(p, t['status']) == 'done', 'assigned_to': t.get('assigned_to', ''), 'description': t.get('description') or '', 'parent_id': ''})
                subs += [{**x, 'parent_id': x.get('parent_id') or sid} for x in t.get('subtasks') or []]
                entries += t.get('time_entries') or []
                people += assignee_ids(t)
            others = [t['id'] for t in ts if t['id'] != main['id']]
            people = list(dict.fromkeys(people))
            await db.tasks.update_one({'id': main['id']}, {'$set': {'title': m['title'], 'subtasks': subs, 'time_entries': entries,
                                                                     'assignee_ids': people, 'assigned_to': main.get('assigned_to') or (people[0] if people else ''),
                                                                     'tags': [x for x in main.get('tags') or [] if x != 'Rincian maintenance'], 'updated_at': now()}})
            if others:
                for coll in ['project_documents', 'task_comments', 'project_features', 'tickets']:
                    await db[coll].update_many({'task_id': {'$in': others}}, {'$set': {'task_id': main['id']}})
                await db.task_schedules.delete_many({'task_id': {'$in': others}})
                await db.tasks.delete_many({'id': {'$in': others}})
        await db.maintenances.update_one({'id': m['id']}, {'$set': {'details_v2': True, 'details_v3': True, **({'task_id': main['id']} if main else {})}})


async def attach_details(rows):
    ids = [r['id'] for r in rows if not r.get('ticket_id')]
    if not ids: return rows
    tasks = await db.tasks.find({'source': 'maintenance', 'source_id': {'$in': ids}}, {'_id': 0, 'id': 1, 'title': 1, 'status': 1, 'source_id': 1, 'assigned_to': 1, 'assignee_ids': 1, 'created_at': 1}).sort('created_at', 1).to_list(100000)
    people = {i for t in tasks for i in assignee_ids(t)}
    names = {x['id']: x['name'] async for x in db.users.find({'id': {'$in': list(people)}}, {'_id': 0, 'id': 1, 'name': 1})}
    by = {}
    for t in tasks: by.setdefault(t['source_id'], []).append(t)
    projects = {p['id']: p async for p in db.projects.find({'id': {'$in': list({r['project_id'] for r in rows})}}, {'_id': 0})}
    for r in rows:
        if r.get('ticket_id'): continue
        ts = by.get(r['id'], [])
        p = projects.get(r['project_id'], {})
        r['details'] = [{'id': t['id'], 'title': t['title'], 'status': t['status'], 'done': kind_of(p, t['status']) == 'done',
                         'assignees': [names.get(i, 'Pengguna tidak aktif') for i in assignee_ids(t)]} for t in ts]
        pics = list(dict.fromkeys(i for t in ts for i in assignee_ids(t)))
        if pics:
            r['assigned_to'] = pics[0]
            r['assignees'] = [{'id': i, 'name': names.get(i, 'Pengguna tidak aktif')} for i in pics]
    return rows


@router.post('/projects/{pid}/work/maintenances/{wid}/details', response_model=Record)
async def add_details(pid: str, wid: str, data: DetailsInput, u=Depends(current_user)):
    await project_for(u, pid, 'maintenance.write')
    m = await db.maintenances.find_one({'id': wid, 'project_id': pid}, {'_id': 0})
    if not m: raise HTTPException(404, 'Maintenance tidak ditemukan.')
    items = [s for s in data.items if (s.get('title') or '').strip()]
    if not items: raise HTTPException(400, 'Isi minimal satu rincian.')
    build_subtasks(items)
    ids = await create_details(pid, u, m, items)
    if m.get('status') == 'Selesai':
        await db.maintenances.update_one({'id': wid}, {'$set': {'status': 'Development', 'completed_at': None}})
    await log_activity(u, 'buat', 'rincian maintenance', wid, m['title'], pid, {'jumlah': len(ids)})
    return {'id': wid, 'task_ids': ids}
