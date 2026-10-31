"""One-pass event rules; actions do not recursively trigger other rules."""
from fastapi import HTTPException
from core import db, uid, now, project_statuses, validate_assignee
from task_rules import normalize_assignees, ensure_completable
from ticket_status_sync import validate_ticket_move
from notify import notify
from workspace_common import members

PRIORITIES = ['Rendah', 'Sedang', 'Tinggi', 'Mendesak']

async def validate_rule(p, rule):
    statuses = [s['name'] for s in project_statuses(p)]
    if rule['condition_field'] == 'status' and rule['condition_value'] not in statuses: raise HTTPException(400, 'Status kondisi tidak ditemukan.')
    if rule['condition_field'] == 'priority' and rule['condition_value'] not in PRIORITIES: raise HTTPException(400, 'Prioritas kondisi tidak valid.')
    action, value = rule['action'], rule['action_value']
    if action == 'set_status' and value not in statuses: raise HTTPException(400, 'Status aksi tidak ditemukan.')
    if action == 'set_priority' and value not in PRIORITIES: raise HTTPException(400, 'Prioritas aksi tidak valid.')
    if action == 'assign': await validate_assignee(value, p)
    if action == 'notify' and value not in [m['id'] for m in await members(p, clients=False)]: raise HTTPException(400, 'Penerima notifikasi bukan anggota project.')

async def apply_automations(p, task, event, actor):
    rules = await db.workspace_rules.find({'project_id': p['id'], 'enabled': True, 'trigger': event}, {'_id': 0}).sort('created_at', 1).to_list(30)
    state = dict(task)
    for rule in rules:
        field = rule['condition_field']
        if field and task.get(field) != rule['condition_value']: continue
        outcome, message = 'success', ''
        try:
            await validate_rule(p, rule)
            action, value = rule['action'], rule['action_value']; update = {}
            if action == 'set_status': update['status'] = value
            elif action == 'set_priority': update['priority'] = value
            elif action == 'assign':
                update['assignee_ids'] = list(dict.fromkeys(state.get('assignee_ids', []) + [value])); await normalize_assignees(update, p)
            elif action == 'add_tag': update['tags'] = list(dict.fromkeys(state.get('tags', []) + [value]))[:10]
            elif action == 'notify':
                await notify([value], f"Automasi: {rule['name']}", task['title'], 'task', f"/projects/{p['id']}/kanban?task={task['id']}", p['id'], 'task', task['id'], email=False)
            if update:
                await ensure_completable(p, {**state, **update})
                if 'status' in update:
                    from kanban import sync_source
                    await validate_ticket_move(state, update['status'], p)
                    await sync_source(state, update['status'], p, actor)
                    done = [s['name'] for s in project_statuses(p) if s['kind'] == 'done']
                    update['completed_at'] = now() if update['status'] in done else None
                update['updated_at'] = now()
                await db.tasks.update_one({'id': task['id'], 'project_id': p['id']}, {'$set': update})
                state.update(update)
                if action == 'assign': await notify([value], 'Penugasan otomatis', task['title'], 'task', f"/projects/{p['id']}/kanban?task={task['id']}", p['id'], 'task', task['id'], email=False)
        except Exception as e:
            outcome, message = 'failed', str(e.detail if isinstance(e, HTTPException) else 'Aksi tidak dapat diproses.')
        await db.automation_logs.insert_one({'id': uid(), 'project_id': p['id'], 'rule_id': rule['id'], 'rule_name': rule['name'], 'task_id': task['id'], 'task_title': task['title'], 'event': event, 'status': outcome, 'message': message, 'created_at': now()})
    return state