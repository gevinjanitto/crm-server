import html
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core import db, now, uid
from auth import current_user
from workspace_collab import clean_content

router = APIRouter()
ALLOWED = ['Admin', 'Admin Project', 'Developer']

class PersonalNoteInput(BaseModel):
    content: str = Field(default='', max_length=100000)

class PersonalDocInput(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    content: str = Field(default='', max_length=150000)
    visibility: str = ''
    version: int = Field(default=0, ge=0)

def owner(u):
    if u['role'] not in ALLOWED: raise HTTPException(403, 'Anda tidak memiliki izin untuk tindakan ini.')
    return u

@router.get('/personal-note')
async def get_note(u=Depends(current_user)):
    doc = await db.personal_notes.find_one({'user_id': owner(u)['id']}, {'_id': 0})
    return doc or {'user_id': u['id'], 'content': '', 'updated_at': None}

@router.put('/personal-note')
async def save_note(data: PersonalNoteInput, u=Depends(current_user)):
    q = {'user_id': owner(u)['id']}
    await db.personal_notes.update_one(q, {'$set': {'content': data.content, 'updated_at': now()}, '$setOnInsert': {'id': u['id'], 'created_at': now()}}, upsert=True)
    return await db.personal_notes.find_one(q, {'_id': 0})

# ---------- multi-dokumen (fitur sama dengan Notes project, tanpa tag @) ----------
async def new_doc(u, title, content):
    doc = {'id': uid(), 'user_id': u['id'], 'title': title, 'content': clean_content(content), 'version': 1, 'created_by': u['id'], 'updated_by': u['name'], 'created_at': now(), 'updated_at': now()}
    await db.personal_docs.insert_one(doc.copy())
    await db.personal_doc_versions.insert_one({**doc, 'doc_id': doc['id'], 'id': uid()})
    return doc

async def migrate_legacy(u):
    old = await db.personal_notes.find_one({'user_id': u['id']}, {'_id': 0})
    if not old or not (old.get('content') or '').strip() or old.get('migrated'): return
    body = ''.join(f'<p>{html.escape(line)}</p>' for line in old['content'].split('\n'))
    await new_doc(u, 'Catatan pribadi', body)
    await db.personal_notes.update_one({'user_id': u['id']}, {'$set': {'migrated': True}})

async def own_doc(u, rid):
    doc = await db.personal_docs.find_one({'id': rid, 'user_id': owner(u)['id']}, {'_id': 0})
    if not doc: raise HTTPException(404, 'Notes tidak ditemukan.')
    return doc

@router.get('/personal-notes')
async def list_docs(u=Depends(current_user)):
    await migrate_legacy(owner(u))
    return await db.personal_docs.find({'user_id': u['id']}, {'_id': 0}).sort('updated_at', -1).to_list(1000)

@router.post('/personal-notes')
async def create_doc(data: PersonalDocInput, u=Depends(current_user)):
    return await new_doc(owner(u), data.title.strip(), data.content)

@router.patch('/personal-notes/{rid}')
async def update_doc(rid: str, data: PersonalDocInput, u=Depends(current_user)):
    doc = await own_doc(u, rid)
    update = {'title': data.title.strip(), 'content': clean_content(data.content), 'version': data.version + 1, 'updated_at': now(), 'updated_by': u['name']}
    result = await db.personal_docs.update_one({'id': rid, 'user_id': u['id'], 'version': data.version}, {'$set': update})
    if not result.modified_count: raise HTTPException(409, 'Notes sudah diperbarui di tab/perangkat lain. Muat ulang sebelum menyimpan.')
    out = {**doc, **update}
    await db.personal_doc_versions.insert_one({**out, 'doc_id': rid, 'id': uid()})
    return out

@router.get('/personal-notes/{rid}/versions')
async def doc_versions(rid: str, u=Depends(current_user)):
    await own_doc(u, rid)
    return await db.personal_doc_versions.find({'doc_id': rid, 'user_id': u['id']}, {'_id': 0}).sort('version', -1).to_list(50)

@router.delete('/personal-notes/{rid}')
async def delete_doc(rid: str, u=Depends(current_user)):
    await own_doc(u, rid)
    await db.personal_docs.delete_one({'id': rid, 'user_id': u['id']})
    await db.personal_doc_versions.delete_many({'doc_id': rid})
    return {'message': 'Notes dihapus.'}
