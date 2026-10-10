import json
import bleach
from fastapi import APIRouter, Depends, HTTPException
from docstore import DuplicateKeyError
from core import db, uid, now, MANAGERS
from auth import current_user
from schemas import Record
from workspace_models import DocInput, WhiteboardInput, CommentResolve
from workspace_common import access, record
from whiteboard_data import clean_nodes

router = APIRouter(prefix='/projects/{pid}/workspace')
TAGS = ['p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'hr', 'a']

def clean_content(content):
    return bleach.clean(content, tags=TAGS, attributes={'a': ['href', 'title', 'target', 'rel']}, protocols=['http', 'https', 'mailto'], strip=True)

async def visible_doc(pid, rid, u, write=False):
    await access(u, pid, internal=write)
    doc = await record('workspace_docs', pid, rid)
    if u['role'] not in MANAGERS + ['Developer'] and doc['visibility'] != 'Client': raise HTTPException(404, 'Dokumen tidak ditemukan.')
    return doc

@router.get('/docs', response_model=list[Record])
async def docs(pid: str, u=Depends(current_user)):
    await access(u, pid)
    q = {'project_id': pid}
    if u['role'] not in MANAGERS + ['Developer']: q['visibility'] = 'Client'
    return await db.workspace_docs.find(q, {'_id': 0}).sort('updated_at', -1).to_list(200)

@router.post('/docs', response_model=Record)
async def create_doc(pid: str, data: DocInput, u=Depends(current_user)):
    await access(u, pid, internal=True)
    doc = {'id': uid(), 'project_id': pid, **data.model_dump(exclude={'version'}), 'content': clean_content(data.content), 'version': 1, 'created_by': u['id'], 'updated_by': u['name'], 'created_at': now(), 'updated_at': now()}
    await db.workspace_docs.insert_one(doc.copy())
    await db.doc_versions.insert_one({**doc, 'doc_id': doc['id'], 'id': uid()})
    return doc

@router.patch('/docs/{rid}', response_model=Record)
async def update_doc(pid: str, rid: str, data: DocInput, u=Depends(current_user)):
    doc = await visible_doc(pid, rid, u, write=True)
    update = {**data.model_dump(exclude={'version'}), 'content': clean_content(data.content), 'version': data.version + 1, 'updated_at': now(), 'updated_by': u['name']}
    result = await db.workspace_docs.update_one({'id': rid, 'version': data.version}, {'$set': update})
    if not result.modified_count: raise HTTPException(409, 'Dokumen sudah diperbarui anggota lain. Muat ulang sebelum menyimpan agar perubahan tidak tertimpa.')
    out = {**doc, **update}
    await db.doc_versions.insert_one({**out, 'doc_id': rid, 'id': uid()})
    return out

@router.get('/docs/{rid}/versions', response_model=list[Record])
async def doc_versions(pid: str, rid: str, u=Depends(current_user)):
    await visible_doc(pid, rid, u, write=True)
    return await db.doc_versions.find({'doc_id': rid, 'project_id': pid}, {'_id': 0}).sort('version', -1).to_list(50)

@router.delete('/docs/{rid}')
async def delete_doc(pid: str, rid: str, u=Depends(current_user)):
    doc = await visible_doc(pid, rid, u, write=True)
    if u['role'] not in MANAGERS and doc['created_by'] != u['id']: raise HTTPException(403, 'Hanya pembuat dokumen atau pengelola yang dapat menghapus.')
    await db.workspace_docs.delete_one({'id': rid})
    await db.doc_versions.delete_many({'doc_id': rid})
    return {'message': 'Dokumen dihapus.'}

@router.get('/whiteboard', response_model=Record)
async def whiteboard(pid: str, u=Depends(current_user)):
    await access(u, pid, internal=True)
    return await db.workspace_boards.find_one({'project_id': pid}, {'_id': 0}) or {'id': pid, 'project_id': pid, 'name': 'Whiteboard project', 'nodes': [], 'edges': [], 'version': 0}

@router.patch('/whiteboard', response_model=Record)
async def save_board(pid: str, data: WhiteboardInput, u=Depends(current_user)):
    await access(u, pid, internal=True)
    if len(json.dumps(data.model_dump())) > 500000: raise HTTPException(400, 'Whiteboard terlalu besar.')
    nodes, seen = await clean_nodes(pid, data.nodes)
    edges = []
    edge_ids = set()
    for e in data.edges:
        if not isinstance(e.get('id'), str) or e['id'] in edge_ids or e.get('source') not in seen or e.get('target') not in seen or e['source'] == e['target']:
            raise HTTPException(400, 'Koneksi whiteboard tidak valid.')
        edge_ids.add(e['id'])
        edges.append({'id': e['id'], 'source': e['source'], 'target': e['target'], 'type': 'smoothstep'})
    doc = {'id': pid, 'project_id': pid, 'name': data.name, 'nodes': nodes, 'edges': edges, 'version': data.version + 1, 'updated_at': now(), 'updated_by': u['name']}
    if data.version == 0:
        try: await db.workspace_boards.insert_one(doc.copy())
        except DuplicateKeyError: raise HTTPException(409, 'Whiteboard sudah berubah. Muat ulang terlebih dahulu.')
    else:
        result = await db.workspace_boards.update_one({'project_id': pid, 'version': data.version}, {'$set': doc})
        if not result.modified_count: raise HTTPException(409, 'Whiteboard sudah diperbarui anggota lain. Muat ulang sebelum menyimpan.')
    return doc

@router.patch('/tasks/{tid}/comments/{cid}', response_model=Record)
async def resolve_comment(pid: str, tid: str, cid: str, data: CommentResolve, u=Depends(current_user)):
    await access(u, pid)
    comment = await db.task_comments.find_one({'id': cid, 'task_id': tid, 'project_id': pid}, {'_id': 0})
    if not comment: raise HTTPException(404, 'Komentar tidak ditemukan.')
    if not comment.get('assigned_to'): raise HTTPException(400, 'Komentar ini tidak memiliki penanggung jawab.')
    if u['role'] not in MANAGERS and u['id'] not in [comment['author_id'], comment['assigned_to']]: raise HTTPException(403, 'Hanya penerima, penulis, atau pengelola yang dapat menyelesaikan komentar.')
    update = {'resolved': data.resolved, 'resolved_at': now() if data.resolved else None, 'resolved_by': u['name'] if data.resolved else ''}
    await db.task_comments.update_one({'id': cid}, {'$set': update})
    return {**comment, **update}