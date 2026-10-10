from fastapi import APIRouter, Depends
from core import db, now, project_scope, project_statuses
from auth import current_user

router = APIRouter(prefix='/inbox')


async def inbox_rows(u):
    scope = project_scope(u)
    pids = None if not scope else set(await db.projects.distinct('id', scope))
    comments = await db.task_comments.find({}, {'_id': 0}).sort('created_at', -1).to_list(5000)
    if pids is not None: comments = [c for c in comments if c.get('project_id') in pids]
    tasks = {t['id']: t for t in await db.tasks.find({'id': {'$in': list({c['task_id'] for c in comments})}}, {'_id': 0, 'id': 1, 'title': 1, 'status': 1, 'project_id': 1, 'assigned_to': 1, 'assignee_ids': 1, 'created_by': 1}).to_list(3000)} if comments else {}
    projects = {p['id']: p for p in await db.projects.find({'id': {'$in': list({t['project_id'] for t in tasks.values()})}}, {'_id': 0, 'id': 1, 'name': 1, 'task_statuses': 1}).to_list(1000)} if tasks else {}
    reads = {r['task_id']: r['seen_at'] for r in await db.inbox_reads.find({'user_id': u['id']}, {'_id': 0}).to_list(5000)}
    rows = {}
    for c in comments:
        t = tasks.get(c['task_id'])
        if not t or t['project_id'] not in projects: continue
        row = rows.get(t['id'])
        if row is None:
            p = projects[t['project_id']]
            status = next((s for s in project_statuses(p) if s['name'] == t.get('status')), {})
            rows[t['id']] = row = {'task_id': t['id'], 'task_title': t['title'], 'task_status': t.get('status', ''), 'status_color': status.get('color', '#87909e'), 'status_kind': status.get('kind', 'todo'),
                                   'project_id': p['id'], 'project_name': p['name'], 'comment_id': c['id'], 'author_name': c['author_name'], 'mine': c.get('author_id') == u['id'], 'message': c['message'], 'created_at': c['created_at'], 'count': 0, 'unread': 0}
        row['count'] += 1
        if c.get('author_id') != u['id'] and c['created_at'] > reads.get(t['id'], ''): row['unread'] += 1
    return list(rows.values())


@router.get('')
async def inbox(u=Depends(current_user)):
    rows = await inbox_rows(u)
    return {'items': rows, 'unread': sum(1 for r in rows if r['unread'])}


@router.post('/{tid}/read')
async def mark_read(tid: str, u=Depends(current_user)):
    await db.inbox_reads.update_one({'id': f"{u['id']}:{tid}"}, {'$set': {'id': f"{u['id']}:{tid}", 'user_id': u['id'], 'task_id': tid, 'seen_at': now()}}, upsert=True)
    return {'message': 'Ditandai dibaca.'}
