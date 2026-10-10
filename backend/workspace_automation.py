from datetime import timezone
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from core import db, uid, now
from auth import current_user
from schemas import Record
from workspace_models import AutomationInput, ScheduleInput
from workspace_common import access, record
from workspace_engine import validate_rule

router = APIRouter(prefix='/projects/{pid}/workspace')

@router.get('/automations')
async def rules(pid: str, u=Depends(current_user)):
    await access(u, pid, internal=True)
    return {'rules': await db.workspace_rules.find({'project_id': pid}, {'_id': 0}).sort('created_at', 1).to_list(30),
            'logs': await db.automation_logs.find({'project_id': pid}, {'_id': 0}).sort('created_at', -1).to_list(30),
            'schedules': await db.task_schedules.find({'project_id': pid}, {'_id': 0}).to_list(500),
            'last_run': await db.cron_runs.find_one({'status': 'completed', 'project_id': {'$in': [pid, None]}}, {'_id': 0}, sort=[('finished_at', -1)])}

@router.post('/automations', response_model=Record)
async def create_rule(pid: str, data: AutomationInput, u=Depends(current_user)):
    p = await access(u, pid, write=True)
    if await db.workspace_rules.count_documents({'project_id': pid}) >= 30: raise HTTPException(400, 'Maksimal 30 aturan per project.')
    await validate_rule(p, data.model_dump())
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(), 'created_at': now()}
    await db.workspace_rules.insert_one(doc.copy())
    return doc

@router.patch('/automations/{rid}', response_model=Record)
async def edit_rule(pid: str, rid: str, data: AutomationInput, u=Depends(current_user)):
    p = await access(u, pid, write=True)
    old = await record('workspace_rules', pid, rid)
    await validate_rule(p, data.model_dump())
    await db.workspace_rules.update_one({'id': rid}, {'$set': data.model_dump()})
    return {**old, **data.model_dump()}

@router.delete('/automations/{rid}')
async def delete_rule(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True); await record('workspace_rules', pid, rid)
    await db.workspace_rules.delete_one({'id': rid})
    return {'message': 'Aturan dihapus.'}

@router.get('/tasks/{tid}/schedule')
async def get_schedule(pid: str, tid: str, u=Depends(current_user)):
    await access(u, pid, internal=True); await record('tasks', pid, tid)
    return await db.task_schedules.find_one({'project_id': pid, 'task_id': tid}, {'_id': 0})

@router.post('/tasks/{tid}/schedule', response_model=Record)
async def save_schedule(pid: str, tid: str, data: ScheduleInput, u=Depends(current_user)):
    await access(u, pid, write=True); task = await record('tasks', pid, tid)
    doc = {'id': tid, 'task_id': tid, 'task_title': task['title'], 'project_id': pid, **data.model_dump(mode='json'),
           'next_run': data.next_run.astimezone(timezone.utc).isoformat(), 'end_at': data.end_at.astimezone(timezone.utc).isoformat() if data.end_at else None, 'updated_at': now(), 'created_by': u['id']}
    await db.task_schedules.update_one({'id': tid}, {'$set': doc, '$unset': {'lease_until': '', 'error': ''}}, upsert=True)
    return doc

@router.delete('/tasks/{tid}/schedule')
async def remove_schedule(pid: str, tid: str, u=Depends(current_user)):
    await access(u, pid, write=True)
    await db.task_schedules.delete_one({'task_id': tid, 'project_id': pid})
    return {'message': 'Pengulangan dihentikan.'}

@router.post('/run-due')
async def run_due(pid: str, background_tasks: BackgroundTasks, u=Depends(current_user)):
    from workspace_scheduler import enqueue_run
    await access(u, pid, write=True)
    rid = uid()
    await enqueue_run(rid, background_tasks, pid)
    return {'id': rid, 'message': 'Pemeriksaan jadwal dimulai.'}