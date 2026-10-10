import os, asyncio, logging, html
from fastapi import APIRouter, Depends, HTTPException
from core import db, uid, now, MANAGERS, FINANCE
from auth import current_user
from notification_delivery import deliver_notifications

log = logging.getLogger('notify')
router = APIRouter(prefix='/notifications')

async def ids_by_role(*roles): return await db.users.distinct('id', {'role': {'$in': list(roles)}, 'active': True})
async def manager_ids(): return await ids_by_role(*MANAGERS)
async def finance_ids(): return await ids_by_role(*FINANCE)
async def client_ids(client_id):
    if not client_id: return []
    return await db.users.distinct('id', {'role': 'Client', 'client_id': client_id, 'active': True})
async def project_people(p, clients=True):
    ids = list(p.get('assigned_to') or []) + await manager_ids()
    if clients: ids += await client_ids(p.get('client_id'))
    return ids

_bg = set()
def _spawn(coro):
    t = asyncio.create_task(coro); _bg.add(t); t.add_done_callback(_bg.discard)

async def notify(recipients, title, message, kind='info', link='/', project_id='', entity_type='', entity_id='', actor=None, email=True, cc=None, wait_for_delivery=False, external=None):
    ids = {r for r in recipients if r} - ({actor['id']} if actor else set())
    # CC may only refer to registered people with access to this project, never an open relay.
    if cc and project_id:
        project = await db.projects.find_one({'id': project_id}, {'_id': 0})
        if project:
            cc_users = await db.users.find({'email': {'$in': cc}, 'active': True, '$or': [{'role': {'$in': MANAGERS}}, {'id': {'$in': project.get('assigned_to', [])}}, {'role': 'Client', 'client_id': project.get('client_id')}]}, {'_id': 0, 'id': 1}).to_list(30)
            ids.update(x['id'] for x in cc_users)
    users = await db.users.find({'id': {'$in': list(ids)}, 'active': True}, {'_id': 0, 'id': 1, 'notification_preferences': 1}).to_list(500) if ids else []
    docs = [{'id': uid(), 'user_id': x['id'], 'kind': kind, 'title': title, 'message': message, 'link': link or '/', 'project_id': project_id or '', 'entity_type': entity_type, 'entity_id': entity_id, 'actor_name': actor['name'] if actor else 'Sistem', 'read': False, 'created_at': now()} for x in users]
    in_app_ids = {x['id'] for x in users if x.get('notification_preferences', {}).get('in_app', True)}
    in_app_docs = [d.copy() for d in docs if d['user_id'] in in_app_ids]
    if in_app_docs: await db.notifications.insert_many(in_app_docs)
    # Account channel preferences supersede legacy email=False event flags.
    # `external` overrides message/link only for email & WhatsApp (never stored in-app).
    outgoing = [{**d, **external} for d in docs] if external else docs
    if outgoing:
        if wait_for_delivery:
            await deliver_notifications(outgoing)
        else:
            _spawn(deliver_notifications(outgoing))
    return docs

async def notify_assignment(user_id, kind, title, project_id, due_date=None, actor=None):
    p = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
    msg = f"Anda ditugaskan pada {kind}: {title}. Project: {p['name'] if p else '-'}."
    if due_date: msg += f' Target selesai {due_date}.'
    await notify([user_id], f'Penugasan {kind}: {title}', msg, 'penugasan', f'/projects/{project_id}', project_id, kind, '', actor)

def _mine(u): return {'user_id': u['id'], 'read': {'$exists': True}}

@router.get('')
async def my_notifications(unread: bool = False, u=Depends(current_user)):
    q = _mine(u)
    if unread: q['read'] = False
    items = await db.notifications.find(q, {'_id': 0}).sort('created_at', -1).to_list(60)
    return {'items': items, 'unread': await db.notifications.count_documents({**_mine(u), 'read': False})}

@router.get('/unread-count')
async def unread_count(u=Depends(current_user)): return {'unread': await db.notifications.count_documents({**_mine(u), 'read': False})}

@router.post('/read-all')
async def read_all(u=Depends(current_user)):
    await db.notifications.update_many({**_mine(u), 'read': False}, {'$set': {'read': True, 'read_at': now()}})
    return {'message': 'Semua notifikasi ditandai dibaca.'}

@router.post('/{nid}/read')
async def read_one(nid: str, u=Depends(current_user)):
    r = await db.notifications.update_one({'id': nid, 'user_id': u['id']}, {'$set': {'read': True, 'read_at': now()}})
    if not r.matched_count: raise HTTPException(404, 'Notifikasi tidak ditemukan.')
    return {'message': 'Ditandai dibaca.'}

@router.delete('/{nid}')
async def delete_one(nid: str, u=Depends(current_user)):
    r = await db.notifications.delete_one({'id': nid, 'user_id': u['id']})
    if not r.deleted_count: raise HTTPException(404, 'Notifikasi tidak ditemukan.')
    return {'message': 'Notifikasi dihapus.'}

@router.get('/email-logs')
async def email_logs(u=Depends(current_user)):
    if u['role'] != 'Admin': raise HTTPException(403, 'Hanya Admin.')
    return await db.email_logs.find({}, {'_id': 0}).sort('created_at', -1).to_list(100)
