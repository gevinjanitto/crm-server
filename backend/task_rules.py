"""Project-task validation, compatible with legacy single-assignee records."""
from fastapi import HTTPException
from core import db, project_statuses, validate_assignee


def assignee_ids(task):
    return list(dict.fromkeys(([task.get('assigned_to')] if task.get('assigned_to') else []) + (task.get('assignee_ids') or [])))


async def normalize_assignees(update, project):
    if 'assignee_ids' not in update and 'assigned_to' not in update:
        return
    ids = list(dict.fromkeys(update.get('assignee_ids') or [])) if 'assignee_ids' in update else ([update['assigned_to']] if update.get('assigned_to') else [])
    for user_id in ids:
        await validate_assignee(user_id, project)
    update['assignee_ids'] = ids
    update['assigned_to'] = ids[0] if ids else ''


def validate_dates(task):
    start, due = task.get('start_date'), task.get('due_date')
    if start and due and due < start:
        raise HTTPException(400, 'Target selesai tidak boleh sebelum tanggal mulai.')


async def validate_dependencies(pid, tid, ids):
    ids = list(dict.fromkeys(ids))
    if tid in ids:
        raise HTTPException(400, 'Task tidak dapat bergantung pada dirinya sendiri.')
    tasks = await db.tasks.find({'project_id': pid}, {'_id': 0, 'id': 1, 'dependencies': 1}).to_list(10000)
    graph = {t['id']: t.get('dependencies', []) for t in tasks}
    if any(i not in graph for i in ids):
        raise HTTPException(400, 'Dependensi harus berupa task aktif pada project yang sama.')
    graph[tid] = ids
    visited, stack = set(), list(ids)
    while stack:
        node = stack.pop()
        if node == tid:
            raise HTTPException(400, 'Dependensi melingkar tidak diperbolehkan.')
        if node not in visited:
            visited.add(node)
            stack.extend(graph.get(node, []))
    return ids


async def ensure_completable(project, task, completing=()):
    done = [s['name'] for s in project_statuses(project) if s['kind'] == 'done']
    if task.get('status') not in done:
        return
    ids = [i for i in task.get('dependencies', []) if i not in completing]
    blocked = await db.tasks.find({'id': {'$in': ids}, 'project_id': project['id'], 'status': {'$nin': done}}, {'_id': 0, 'title': 1}).to_list(100)
    if blocked:
        raise HTTPException(400, 'Selesaikan task prasyarat terlebih dahulu: ' + ', '.join(t['title'] for t in blocked[:3]))