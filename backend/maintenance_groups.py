import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from core import db, uid, now, project_for, log_activity
from auth import current_user
from schemas import Input, Record
from project_years import _year, current_year

router = APIRouter()
GROUPED_TICKETS = ['Diterima', 'Dikerjakan', 'Selesai', 'Ditutup']


class GroupInput(Input):
    name: str = Field(min_length=3, max_length=120)


def _name_year(name):
    m = re.search(r'(19|20)\d{2}', name)
    return m.group(0) if m else current_year()


async def year_group(pid, year, u=None):
    """Default group "Maintenance {year}" for a project, created when missing."""
    g = await db.maintenance_groups.find_one({'project_id': pid, 'year': year, 'auto': True}, {'_id': 0})
    if g: return g
    g = {'id': uid(), 'project_id': pid, 'name': f'Maintenance {year}', 'year': year, 'auto': True,
         'created_at': now(), 'created_by': (u or {}).get('id', '')}
    await db.maintenance_groups.insert_one(g.copy())
    return g


async def resolve_group(pid, group_id, year, u=None):
    if group_id:
        g = await db.maintenance_groups.find_one({'id': group_id, 'project_id': pid}, {'_id': 0})
        if not g: raise HTTPException(400, 'Grup maintenance tidak ditemukan pada project ini.')
        return g
    return await year_group(pid, year or current_year(), u)


async def ensure_groups(project_ids):
    """Assign ungrouped maintenance items and accepted tickets to their yearly group."""
    if not project_ids: return
    valid = set(await db.maintenance_groups.distinct('id', {'project_id': {'$in': project_ids}}))
    for m in await db.maintenances.find({'project_id': {'$in': project_ids}, 'group_id': {'$nin': list(valid)}}, {'_id': 0}).to_list(50000):
        g = await year_group(m['project_id'], _year(m.get('entry_date')) or _year(m.get('created_at')) or current_year())
        await db.maintenances.update_one({'id': m['id']}, {'$set': {'group_id': g['id']}})
    q = {'project_id': {'$in': project_ids}, 'status': {'$in': GROUPED_TICKETS}, 'maintenance_group_id': {'$nin': list(valid)}}
    for t in await db.tickets.find(q, {'_id': 0}).to_list(50000):
        g = await year_group(t['project_id'], _year(t.get('accepted_at')) or _year(t.get('created_at')) or current_year())
        await db.tickets.update_one({'id': t['id']}, {'$set': {'maintenance_group_id': g['id']}})


async def attach_groups(rows):
    ids = list({r['group_id'] for r in rows if r.get('group_id')})
    names = {g['id']: g for g in await db.maintenance_groups.find({'id': {'$in': ids}}, {'_id': 0}).to_list(5000)} if ids else {}
    for r in rows:
        g = names.get(r.get('group_id'))
        r['group_name'] = g['name'] if g else None
        r['group_year'] = g['year'] if g else None
    return rows


@router.get('/projects/{pid}/maintenance-groups', response_model=list[Record])
async def list_groups(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'maintenance.read')
    await ensure_groups([pid])
    rows = await db.maintenance_groups.find({'project_id': pid}, {'_id': 0}).to_list(500)
    for g in rows:
        g['count'] = await db.maintenances.count_documents({'group_id': g['id']}) + await db.tickets.count_documents({'maintenance_group_id': g['id']})
    return sorted(rows, key=lambda g: (g.get('year', ''), g.get('created_at', '')), reverse=True)


@router.post('/projects/{pid}/maintenance-groups', response_model=Record)
async def create_group(pid: str, data: GroupInput, u=Depends(current_user)):
    await project_for(u, pid, 'maintenance.write')
    name = data.name.strip()
    if await db.maintenance_groups.find_one({'project_id': pid, 'name': name}, {'_id': 0}): raise HTTPException(400, 'Nama grup maintenance sudah dipakai.')
    g = {'id': uid(), 'project_id': pid, 'name': name, 'year': _name_year(name), 'auto': False, 'created_at': now(), 'created_by': u['id']}
    await db.maintenance_groups.insert_one(g.copy())
    await log_activity(u, 'buat', 'grup maintenance', g['id'], name, pid)
    return {**g, 'count': 0}


@router.patch('/projects/{pid}/maintenance-groups/{gid}', response_model=Record)
async def rename_group(pid: str, gid: str, data: GroupInput, u=Depends(current_user)):
    await project_for(u, pid, 'maintenance.write')
    g = await db.maintenance_groups.find_one({'id': gid, 'project_id': pid}, {'_id': 0})
    if not g: raise HTTPException(404, 'Grup maintenance tidak ditemukan.')
    name = data.name.strip()
    if await db.maintenance_groups.find_one({'project_id': pid, 'name': name, 'id': {'$ne': gid}}, {'_id': 0}): raise HTTPException(400, 'Nama grup maintenance sudah dipakai.')
    update = {'name': name, 'year': _name_year(name) if re.search(r'(19|20)\d{2}', name) else g['year']}
    await db.maintenance_groups.update_one({'id': gid}, {'$set': update})
    await log_activity(u, 'ubah', 'grup maintenance', gid, name, pid)
    return {**g, **update}


@router.delete('/projects/{pid}/maintenance-groups/{gid}')
async def delete_group(pid: str, gid: str, u=Depends(current_user)):
    await project_for(u, pid, 'maintenance.write')
    if not await db.maintenance_groups.find_one({'id': gid, 'project_id': pid}, {'_id': 0}): raise HTTPException(404, 'Grup maintenance tidak ditemukan.')
    if await db.maintenances.count_documents({'group_id': gid}) or await db.tickets.count_documents({'maintenance_group_id': gid}):
        raise HTTPException(400, 'Grup masih berisi maintenance. Pindahkan isinya terlebih dahulu.')
    await db.maintenance_groups.delete_one({'id': gid, 'project_id': pid})
    return {'message': 'Grup maintenance dihapus.'}
