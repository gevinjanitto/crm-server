from fastapi import APIRouter, Depends, HTTPException
from core import db, now, authorize, log_activity, MANAGERS
from auth import current_user
from schemas import Record

router = APIRouter()

@router.get('/audit', response_model=list[Record])
async def audit(entity_type: str = '', user_id: str = '', q: str = '', limit: int = 200, u=Depends(current_user)):
    await authorize(u, 'audit.read')
    query = {}
    if entity_type: query['entity_type'] = entity_type
    if user_id: query['user_id'] = user_id
    if q: query['$or'] = [{'name': {'$regex': q, '$options': 'i'}}, {'user_name': {'$regex': q, '$options': 'i'}}, {'action': {'$regex': q, '$options': 'i'}}]
    return await db.activity_logs.find(query, {'_id': 0}).sort('created_at', -1).to_list(min(limit, 1000))

@router.get('/trash', response_model=list[Record])
async def trash(u=Depends(current_user)):
    await authorize(u, 'trash.read')
    rows = await db.trash.find({}, {'_id': 0, 'data': 0, 'related': 0}).sort('deleted_at', -1).to_list(1000)
    return rows

@router.post('/trash/{tid}/restore')
async def restore(tid: str, u=Depends(current_user)):
    await authorize(u, 'trash.write')
    t = await db.trash.find_one({'id': tid}, {'_id': 0})
    if not t: raise HTTPException(404, 'Item arsip tidak ditemukan.')
    if t['collection'] != 'projects' and t.get('project_id') and not await db.projects.find_one({'id': t['project_id']}, {'_id': 0, 'id': 1}):
        raise HTTPException(400, 'Project induk sudah dihapus. Pulihkan project terlebih dahulu.')
    exists = await db[t['collection']].find_one({'id': t['entity_id']}, {'_id': 0, 'id': 1})
    if exists and t['collection'] != 'project_documents': raise HTTPException(400, 'Item dengan id ini sudah ada.')
    if not exists: await db[t['collection']].insert_one({**t['data'], 'restored_at': now()})
    for r in t.get('related', []):
        for d in r['docs']:
            if not await db[r['collection']].find_one({'id': d['id']}, {'_id': 0, 'id': 1}): await db[r['collection']].insert_one(dict(d))
    if t['collection'] == 'project_documents': await db.project_documents.update_one({'id': t['entity_id']}, {'$set': {'is_deleted': False}})
    if t['collection'] == 'tasks': await db.project_documents.update_many({'task_id': t['entity_id']}, {'$set': {'is_deleted': False}})
    await db.trash.delete_one({'id': tid})
    await log_activity(u, 'pulihkan', t['entity_type'], t['entity_id'], t['name'], t.get('project_id', ''))
    return {'message': f"{t['entity_type']} \"{t['name']}\" dipulihkan."}

@router.delete('/trash/{tid}')
async def purge(tid: str, u=Depends(current_user)):
    if u['role'] != 'Admin': raise HTTPException(403, 'Hanya Admin yang dapat menghapus permanen.')
    t = await db.trash.find_one({'id': tid}, {'_id': 0})
    if not t: raise HTTPException(404, 'Item arsip tidak ditemukan.')
    await db.trash.delete_one({'id': tid})
    await log_activity(u, 'hapus permanen', t['entity_type'], t['entity_id'], t['name'], t.get('project_id', ''))
    return {'message': 'Dihapus permanen.'}
