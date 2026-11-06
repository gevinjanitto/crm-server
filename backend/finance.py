from fastapi import APIRouter, Depends, HTTPException
from core import db, uid, now, authorize, project_for, log_event
from auth import current_user
from schemas import Record, CostTypeInput, CostTypeUpdate, ExpenseInput
from notify import notify, finance_ids

router = APIRouter()

@router.get('/cost-types', response_model=list[Record])
async def cost_types(u=Depends(current_user)):
    await authorize(u, 'costtype.read')
    rows = await db.cost_types.find({}, {'_id': 0}).sort('name', 1).to_list(500)
    for r in rows: r['usage'] = await db.expenses.count_documents({'cost_type_id': r['id']})
    return rows

@router.post('/cost-types', response_model=Record)
async def add_cost_type(data: CostTypeInput, u=Depends(current_user)):
    await authorize(u, 'costtype.write')
    if await db.cost_types.find_one({'name': {'$regex': f'^{data.name}$', '$options': 'i'}}): raise HTTPException(409, 'Jenis biaya sudah ada.')
    row = {**data.model_dump(), 'id': uid(), 'active': True, 'created_at': now()}
    await db.cost_types.insert_one(row.copy())
    return row

@router.patch('/cost-types/{cid}', response_model=Record)
async def edit_cost_type(cid: str, data: CostTypeUpdate, u=Depends(current_user)):
    await authorize(u, 'costtype.write')
    update = data.model_dump(exclude_none=True)
    r = await db.cost_types.find_one_and_update({'id': cid}, {'$set': update}, projection={'_id': 0}, return_document=True)
    if not r: raise HTTPException(404, 'Jenis biaya tidak ditemukan.')
    if 'name' in update or 'group' in update:
        await db.expenses.update_many({'cost_type_id': cid}, {'$set': {'cost_type_name': r['name'], 'cost_group': r['group']}})
        for pid in await db.expenses.distinct('project_id', {'cost_type_id': cid}): await recalc_costs(pid)
    return r

@router.delete('/cost-types/{cid}')
async def delete_cost_type(cid: str, u=Depends(current_user)):
    await authorize(u, 'costtype.write')
    if await db.expenses.count_documents({'cost_type_id': cid}): raise HTTPException(400, 'Jenis biaya masih dipakai pada pengeluaran project. Nonaktifkan saja.')
    r = await db.cost_types.delete_one({'id': cid})
    if not r.deleted_count: raise HTTPException(404, 'Jenis biaya tidak ditemukan.')
    return {'message': 'Jenis biaya dihapus.'}

async def recalc_costs(pid, reset_group=None):
    totals = {}
    async for g in db.expenses.aggregate([{'$match': {'project_id': pid}}, {'$group': {'_id': '$cost_group', 'total': {'$sum': '$amount'}}}]): totals[g['_id']] = g['total']
    if reset_group and reset_group not in totals: totals[reset_group] = 0
    fields = {'Development': 'development_cost', 'Server': 'server_cost', 'Lainnya': 'other_cost'}
    update = {fields[g]: v for g, v in totals.items()}
    if update: await db.projects.update_one({'id': pid}, {'$set': {**update, 'updated_at': now()}})

@router.get('/projects/{pid}/expenses', response_model=list[Record])
async def expenses(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'cost.read')
    return await db.expenses.find({'project_id': pid}, {'_id': 0}).sort('date', -1).to_list(2000)

@router.post('/projects/{pid}/expenses', response_model=Record)
async def add_expense(pid: str, data: ExpenseInput, u=Depends(current_user)):
    await project_for(u, pid, 'expense.write')
    ct = await db.cost_types.find_one({'id': data.cost_type_id, 'active': True}, {'_id': 0})
    if not ct: raise HTTPException(400, 'Jenis biaya tidak valid atau nonaktif.')
    row = {**data.model_dump(mode='json'), 'id': uid(), 'project_id': pid, 'cost_type_name': ct['name'], 'cost_group': ct['group'], 'created_by': u['name'], 'created_at': now()}
    await db.expenses.insert_one(row.copy())
    await recalc_costs(pid)
    await log_event(pid, u, f"Pengeluaran dicatat: {ct['name']}")
    p = await db.projects.find_one({'id': pid}, {'_id': 0, 'name': 1})
    await notify(await finance_ids(), f"Pengeluaran baru: {ct['name']}", f"{u['name']} mencatat pengeluaran Rp {data.amount:,.0f} ({ct['name']}) pada project {p['name'] if p else ''}.", 'keuangan', f'/projects/{pid}', pid, 'pengeluaran', row['id'], u, email=False)
    return row

@router.delete('/projects/{pid}/expenses/{eid}')
async def delete_expense(pid: str, eid: str, u=Depends(current_user)):
    await project_for(u, pid, 'expense.write')
    r = await db.expenses.find_one_and_delete({'id': eid, 'project_id': pid}, projection={'_id': 0})
    if not r: raise HTTPException(404, 'Pengeluaran tidak ditemukan.')
    await recalc_costs(pid, r['cost_group'])
    return {'message': 'Pengeluaran dihapus.'}
