"""Platform-managed schedules with immediate acknowledgement and durable dedupe."""
import os, secrets, logging
from datetime import datetime, timezone, timedelta, date
from uuid import uuid5, NAMESPACE_URL
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from docstore import DuplicateKeyError
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from core import db, now, project_statuses
from notify import notify
from task_rules import assignee_ids

router = APIRouter()
log = logging.getLogger('project.scheduler')

class CronEnvelope(BaseModel):
    event: Literal['schedule.triggered']
    schedule_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=128)
    dispatch_time: str

async def enqueue_run(rid, background_tasks, pid=None):
    try: await db.cron_runs.insert_one({'id': rid, 'status': 'queued', 'project_id': pid, 'created_at': now()})
    except DuplicateKeyError: return False
    background_tasks.add_task(process_run, rid, pid)
    return True

@router.post('/cron/project-workspace')
async def cron_tick(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    expected = os.environ.get('WEBHOOK_CRON_SECRET')
    token = request.headers.get('authorization', '')
    if not expected or not token.startswith('Bearer ') or not secrets.compare_digest(token[7:], expected): raise HTTPException(401, 'Tidak diizinkan.')
    try: envelope = CronEnvelope.model_validate(await request.json())
    except (ValidationError, ValueError): raise HTTPException(400, 'Envelope tidak valid.')
    rid = request.headers.get('x-webhook-id') or envelope.run_id
    if not 1 <= len(rid) <= 128: raise HTTPException(400, 'Run ID tidak valid.')
    accepted = await enqueue_run(rid, background_tasks)
    return {'accepted': accepted, 'duplicate': not accepted}

async def repeat_task(schedule, clock):
    from kanban import create_task, fallback_status
    pid, tid, occurrence = schedule['project_id'], schedule['task_id'], schedule['next_run']
    p = await db.projects.find_one({'id': pid}, {'_id': 0})
    task = await db.tasks.find_one({'id': tid, 'project_id': pid}, {'_id': 0})
    if not p or not task:
        await db.task_schedules.update_one({'id': schedule['id']}, {'$set': {'enabled': False, 'error': 'Task sumber tidak ditemukan.'}}); return 0
    at = datetime.fromisoformat(occurrence)
    if schedule.get('end_at') and at > datetime.fromisoformat(schedule['end_at']):
        await db.task_schedules.update_one({'id': schedule['id']}, {'$set': {'enabled': False}}); return 0
    generated_id = str(uuid5(NAMESPACE_URL, f'maiharta:{tid}:{occurrence}'))
    ids = await db.users.distinct('id', {'id': {'$in': list(set(assignee_ids(task)) & set(p.get('assigned_to', [])))}, 'active': True, 'role': 'Developer'})
    duration = max(0, (date.fromisoformat(task['due_date']) - date.fromisoformat(task['start_date'])).days) if task.get('start_date') and task.get('due_date') else 0
    fields = set(await db.workspace_fields.distinct('id', {'project_id': pid}))
    list_id = task.get('list_id', '') if await db.workspace_nodes.count_documents({'id': task.get('list_id'), 'project_id': pid}) else ''
    await create_task(pid, {'id': 'system', 'name': 'Jadwal Project'}, title=task['title'], description=task.get('description', ''), status=fallback_status(p), priority=task.get('priority', 'Sedang'),
        assignee_ids=ids, assigned_to=ids[0] if ids else '', tags=task.get('tags', []), estimate_hours=task.get('estimate_hours', 0), subtasks=[s['title'] for s in task.get('subtasks', [])],
        list_id=list_id, custom_fields={k: v for k, v in task.get('custom_fields', {}).items() if k in fields}, milestone=task.get('milestone', False), task_id=generated_id,
        start_date=at.date().isoformat(), due_date=(at.date() + timedelta(days=duration)).isoformat())
    step = {'daily': relativedelta(days=1), 'weekly': relativedelta(weeks=1), 'monthly': relativedelta(months=1)}[schedule['frequency']]
    nxt = at + step
    while nxt <= clock: nxt += step
    enabled = not schedule.get('end_at') or nxt <= datetime.fromisoformat(schedule['end_at'])
    await db.task_schedules.update_one({'id': schedule['id'], 'next_run': occurrence}, {'$set': {'next_run': nxt.isoformat(), 'last_run': now(), 'last_task_id': generated_id, 'enabled': enabled}, '$unset': {'lease_until': '', 'error': ''}})
    return 1

async def remind(task, clock):
    p = await db.projects.find_one({'id': task['project_id']}, {'_id': 0})
    if not p or task['status'] in [s['name'] for s in project_statuses(p) if s['kind'] == 'done']: return 0
    event = f"reminder:{task['id']}:{task['reminder_at']}"
    try: await db.scheduler_events.insert_one({'id': event, 'created_at': now()})
    except DuplicateKeyError: return 0
    try:
        ids = list(set(assignee_ids(task) + [task.get('created_by', '')]))
        await notify(ids, f"Pengingat: {task['title']}", 'Jadwal pengingat task telah tiba.', 'pengingat', f"/projects/{task['project_id']}/kanban?task={task['id']}", task['project_id'], 'task', task['id'], email=False)
        await db.tasks.update_one({'id': task['id'], 'reminder_at': task['reminder_at']}, {'$set': {'reminder_sent_at': now()}})
    except Exception:
        await db.scheduler_events.delete_one({'id': event}); raise
    return 1

async def process_run(rid, pid=None):
    clock = datetime.now(timezone.utc); lock_id = 'project-workspace'
    try:
        await db.scheduler_locks.update_one({'id': lock_id, '$or': [{'until': {'$lt': now()}}, {'until': {'$exists': False}}]}, {'$set': {'id': lock_id, 'owner': rid, 'until': (clock + timedelta(minutes=10)).isoformat()}}, upsert=True)
    except DuplicateKeyError:
        await db.cron_runs.update_one({'id': rid}, {'$set': {'status': 'skipped', 'finished_at': now()}}); return
    totals = {'created': 0, 'reminded': 0, 'failed': 0}
    await db.cron_runs.update_one({'id': rid}, {'$set': {'status': 'running'}})
    try:
        q = {'project_id': pid} if pid else {}
        schedules = await db.task_schedules.find({**q, 'enabled': True, 'next_run': {'$lte': clock.isoformat()}}, {'_id': 0}).to_list(500)
        for schedule in schedules:
            try: totals['created'] += await repeat_task(schedule, clock)
            except Exception:
                totals['failed'] += 1
                await db.task_schedules.update_one({'id': schedule['id']}, {'$set': {'error': 'Jadwal gagal; akan dicoba pada pemeriksaan berikutnya.'}})
                log.exception('Schedule processing failed')
        reminders = await db.tasks.find({**q, 'reminder_at': {'$type': 'string', '$lte': clock.isoformat()}, 'reminder_sent_at': None}, {'_id': 0}).to_list(1000)
        for task in reminders:
            try: totals['reminded'] += await remind(task, clock)
            except Exception: totals['failed'] += 1; log.exception('Reminder processing failed')
        if not pid:
            from reminders import check_due_reminders
            totals['reminded'] += await check_due_reminders()
        await db.cron_runs.update_one({'id': rid}, {'$set': {'status': 'completed', 'finished_at': now(), **totals}})
    except Exception:
        await db.cron_runs.update_one({'id': rid}, {'$set': {'status': 'failed', 'finished_at': now()}})
        log.exception('Workspace schedule job failed')
    finally: await db.scheduler_locks.delete_one({'id': lock_id, 'owner': rid})