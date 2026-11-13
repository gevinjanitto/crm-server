from fastapi import APIRouter, Depends
from core import db, project_scope, MANAGERS
from auth import current_user
from schemas import Record

router = APIRouter()

@router.get('/notes', response_model=list[Record])
async def all_notes(u=Depends(current_user)):
    projects = await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'name': 1, 'code': 1}).to_list(2000)
    info = {p['id']: p for p in projects}
    q = {'project_id': {'$in': list(info)}}
    if u['role'] not in MANAGERS + ['Developer']: q['visibility'] = 'Client'
    rows = await db.workspace_docs.find(q, {'_id': 0}).sort('updated_at', -1).to_list(2000)
    for r in rows:
        p = info.get(r['project_id'], {})
        r['project_name'], r['project_code'] = p.get('name', ''), p.get('code', '')
    return rows
