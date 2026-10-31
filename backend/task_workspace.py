"""Additive task workspace endpoints; no changes to other CRM modules."""
from typing import Literal
from pydantic import Field
from fastapi import APIRouter, Depends, HTTPException
from core import db, uid, now, project_for, log_activity
from auth import current_user
from schemas import Input, Record, Priority
from kanban import task_for, create_task, enrich, fallback_status
from task_rules import assignee_ids

router = APIRouter()


class ViewFilters(Input):
    list_id: str = Field(default='', max_length=100)
    sprint_id: str = Field(default='', max_length=100)
    milestone: bool = False
    q: str = Field(default='', max_length=200)
    assignee: str = Field(default='', max_length=100)
    priority: str = Field(default='', pattern=r'^(|Rendah|Sedang|Tinggi|Mendesak)$')
    tag: str = Field(default='', max_length=200)
    status: str = Field(default='', max_length=40)
    mine: bool = False
    overdue: bool = False


class SavedView(Input):
    name: str = Field(min_length=1, max_length=60)
    view: Literal['board', 'list', 'calendar', 'timeline', 'dashboard'] = 'list'
    filters: ViewFilters = Field(default_factory=ViewFilters)


@router.get('/projects/{pid}/task-views', response_model=list[Record])
async def views(pid: str, u=Depends(current_user)):
    await project_for(u, pid, 'task.read')
    return await db.task_views.find({'project_id': pid, 'user_id': u['id']}, {'_id': 0}).sort('created_at', 1).to_list(100)


@router.post('/projects/{pid}/task-views', response_model=Record)
async def save_view(pid: str, data: SavedView, u=Depends(current_user)):
    await project_for(u, pid, 'task.read')
    if await db.task_views.count_documents({'project_id': pid, 'user_id': u['id']}) >= 30:
        raise HTTPException(400, 'Maksimal 30 tampilan pribadi per project.')
    doc = {'id': uid(), 'project_id': pid, 'user_id': u['id'], **data.model_dump(), 'created_at': now()}
    await db.task_views.insert_one(doc.copy())
    return doc


@router.delete('/projects/{pid}/task-views/{vid}')
async def delete_view(pid: str, vid: str, u=Depends(current_user)):
    await project_for(u, pid, 'task.read')
    result = await db.task_views.delete_one({'id': vid, 'project_id': pid, 'user_id': u['id']})
    if not result.deleted_count:
        raise HTTPException(404, 'Tampilan tidak ditemukan.')
    return {'message': 'Tampilan dihapus.'}


@router.post('/projects/{pid}/tasks/{tid}/duplicate', response_model=Record)
async def duplicate_task(pid: str, tid: str, u=Depends(current_user)):
    project, task = await task_for(u, pid, tid, 'task.write')
    # Copies are independent manual tasks: no live timers, comments or source links.
    active_ids = await db.users.distinct('id', {'id': {'$in': project.get('assigned_to', [])}, 'active': True, 'role': 'Developer'})
    ids = [i for i in assignee_ids(task) if i in active_ids]
    dependencies = await db.tasks.distinct('id', {'id': {'$in': task.get('dependencies', [])}, 'project_id': pid})
    copied = await create_task(pid, u, title=task['title'][:190] + ' (salinan)',
                               description=task.get('description', ''), status=fallback_status(project),
                               assigned_to=ids[0] if ids else '', assignee_ids=ids,
                               priority=task.get('priority', 'Sedang'), due_date=task.get('due_date'),
                               start_date=task.get('start_date'), tags=task.get('tags', []),
                               estimate_hours=task.get('estimate_hours', 0),
                               subtasks=[s['title'] for s in task.get('subtasks', [])], dependencies=dependencies,
                               list_id=task.get('list_id', ''), milestone=task.get('milestone', False), custom_fields=task.get('custom_fields', {}))
    await log_activity(u, 'duplikasi', 'task', copied['id'], copied['title'], pid, {'source_task_id': tid})
    return (await enrich([copied], u))[0]