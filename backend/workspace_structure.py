from fastapi import APIRouter, Depends, HTTPException
from core import db, uid, now, MANAGERS
from auth import current_user
from schemas import Record, TaskInput
from workspace_models import NodeInput, FieldInput, Named, ApplyTemplate
from workspace_common import access, record, members

router = APIRouter(prefix='/projects/{pid}/workspace')

@router.get('/meta')
async def meta(pid: str, u=Depends(current_user)):
    p = await access(u, pid)
    fields = await db.workspace_fields.find({'project_id': pid}, {'_id': 0}).to_list(100)
    if u['role'] not in MANAGERS + ['Developer']: fields = [f for f in fields if f['visibility'] == 'Client']
    return {'nodes': await db.workspace_nodes.find({'project_id': pid}, {'_id': 0}).sort('created_at', 1).to_list(500),
            'fields': fields, 'people': await members(p),
            'sprints': await db.workspace_sprints.find({'project_id': pid}, {'_id': 0}).sort('start_date', -1).to_list(100),
            'templates': await db.task_templates.find({'project_id': pid}, {'_id': 0, 'data': 0}).to_list(100) if u['role'] in MANAGERS else []}

async def valid_parent(pid, data):
    if data.kind == 'space':
        if data.parent_id: raise HTTPException(400, 'Space berada di tingkat teratas.')
        return
    if not data.parent_id: raise HTTPException(400, 'Pilih Space atau Folder induk.')
    parent = await record('workspace_nodes', pid, data.parent_id)
    if parent['kind'] not in (['space'] if data.kind == 'folder' else ['space', 'folder']):
        raise HTTPException(400, 'Susunan harus Space → Folder → List, atau Space → List.')

@router.post('/nodes', response_model=Record)
async def create_node(pid: str, data: NodeInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    await valid_parent(pid, data)
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(), 'created_at': now()}
    await db.workspace_nodes.insert_one(doc.copy())
    return doc

@router.patch('/nodes/{rid}', response_model=Record)
async def edit_node(pid: str, rid: str, data: NodeInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    old = await record('workspace_nodes', pid, rid)
    if old['kind'] != data.kind: raise HTTPException(400, 'Jenis struktur tidak dapat diubah.')
    await valid_parent(pid, data)
    await db.workspace_nodes.update_one({'id': rid}, {'$set': data.model_dump()})
    return {**old, **data.model_dump()}

@router.delete('/nodes/{rid}')
async def delete_node(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True)
    await record('workspace_nodes', pid, rid)
    if await db.workspace_nodes.count_documents({'parent_id': rid}) or await db.tasks.count_documents({'project_id': pid, 'list_id': rid}):
        raise HTTPException(400, 'Pindahkan task dan hapus struktur di dalamnya terlebih dahulu.')
    await db.workspace_nodes.delete_one({'id': rid})
    return {'message': 'Struktur dihapus.'}

@router.post('/fields', response_model=Record)
async def create_field(pid: str, data: FieldInput, u=Depends(current_user)):
    await access(u, pid, write=True)
    if await db.workspace_fields.count_documents({'project_id': pid}) >= 30: raise HTTPException(400, 'Maksimal 30 field per project.')
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(), 'created_at': now()}
    await db.workspace_fields.insert_one(doc.copy())
    return doc

@router.delete('/fields/{rid}')
async def delete_field(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True)
    await record('workspace_fields', pid, rid)
    await db.workspace_fields.delete_one({'id': rid})
    await db.tasks.update_many({'project_id': pid}, {'$unset': {f'custom_fields.{rid}': ''}})
    await db.task_templates.update_many({'project_id': pid}, {'$unset': {f'data.custom_fields.{rid}': ''}})
    return {'message': 'Field dihapus.'}

@router.post('/tasks/{tid}/template', response_model=Record)
async def save_template(pid: str, tid: str, data: Named, u=Depends(current_user)):
    await access(u, pid, write=True)
    task = await record('tasks', pid, tid)
    payload = {k: task[k] for k in ['title', 'description', 'priority', 'tags', 'estimate_hours', 'milestone', 'custom_fields'] if k in task}
    payload['subtasks'] = [s['title'] for s in task.get('subtasks', [])]
    doc = {'id': uid(), 'project_id': pid, 'name': data.name, 'data': payload, 'created_at': now(), 'created_by': u['name']}
    await db.task_templates.insert_one(doc.copy())
    return doc

@router.post('/templates/{rid}/apply', response_model=Record)
async def apply_template(pid: str, rid: str, data: ApplyTemplate, u=Depends(current_user)):
    from kanban import add_task, fallback_status
    p = await access(u, pid, write=True)
    template = await record('task_templates', pid, rid)
    return await add_task(pid, TaskInput(**template['data'], status=fallback_status(p), list_id=data.list_id), u)

@router.delete('/templates/{rid}')
async def delete_template(pid: str, rid: str, u=Depends(current_user)):
    await access(u, pid, write=True)
    await record('task_templates', pid, rid)
    await db.task_templates.delete_one({'id': rid})
    return {'message': 'Template dihapus.'}