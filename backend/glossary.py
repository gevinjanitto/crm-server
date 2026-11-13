import asyncio
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from pydantic import BaseModel, Field
from core import db, uid, now, authorize, log_activity
from auth import current_user
from rich_text import clean_description
from storage import put_object, get_object, delete_object

router = APIRouter()
ALLOWED_EXT = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.zip', '.rar']
MAX_SIZE = 20 * 1024 * 1024


class GlossaryInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field('', max_length=200000)


def public(g):
    g = {k: v for k, v in g.items() if k != '_id'}
    g['documents'] = [{k: v for k, v in d.items() if k != 'storage_path'} for d in g.get('documents') or []]
    return g


async def get_entry(gid):
    g = await db.glossaries.find_one({'id': gid}, {'_id': 0})
    if not g: raise HTTPException(404, 'Glosarium tidak ditemukan.')
    return g


async def read_file(file, owner):
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED_EXT: raise HTTPException(400, 'Format tidak didukung. Gunakan PDF, Word, Excel, PowerPoint, TXT, CSV, gambar, atau ZIP/RAR.')
    data = await file.read(MAX_SIZE + 1)
    if not data or len(data) > MAX_SIZE: raise HTTPException(400, f'File {file.filename} harus berukuran 1 byte hingga 20 MB.')
    did = uid()
    ctype = file.content_type or 'application/octet-stream'
    try: result = await asyncio.to_thread(put_object, f'crm-maiharta/glossary/{owner}/{did}{ext}', data, ctype)
    except Exception: raise HTTPException(503, 'Penyimpanan dokumen belum dapat dihubungi.')
    name = Path(file.filename).name
    return {'id': did, 'name': name, 'filename': name, 'size': len(data), 'content_type': ctype, 'storage_path': result['path']}


async def remove_stored(path):
    try: await asyncio.to_thread(delete_object, path)
    except Exception: pass


@router.get('/glossary')
async def list_glossary(q: str = '', u=Depends(current_user)):
    await authorize(u, 'glossary.read')
    rows = await db.glossaries.find({}, {'_id': 0}).sort('title', 1).to_list(5000)
    q = q.strip().lower()
    if q: rows = [g for g in rows if q in g['title'].lower() or q in (g.get('description_text') or '').lower()]
    return [public(g) for g in rows]


@router.get('/glossary/{gid}')
async def glossary_detail(gid: str, u=Depends(current_user)):
    await authorize(u, 'glossary.read')
    return public(await get_entry(gid))


@router.post('/glossary')
async def create_glossary(data: GlossaryInput, u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    title = data.title.strip()
    if not title: raise HTTPException(400, 'Judul wajib diisi.')
    html, text, _ = clean_description(data.description)
    g = {'id': uid(), 'title': title, 'description': html, 'description_text': text, 'documents': [], 'created_by': u['name'], 'updated_by': u['name'], 'created_at': now(), 'updated_at': now()}
    await db.glossaries.insert_one(g.copy())
    await log_activity(u, 'buat', 'glosarium', g['id'], title)
    return public(g)


@router.patch('/glossary/{gid}')
async def edit_glossary(gid: str, data: GlossaryInput, u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    await get_entry(gid)
    title = data.title.strip()
    if not title: raise HTTPException(400, 'Judul wajib diisi.')
    html, text, _ = clean_description(data.description)
    await db.glossaries.update_one({'id': gid}, {'$set': {'title': title, 'description': html, 'description_text': text, 'updated_by': u['name'], 'updated_at': now()}})
    await log_activity(u, 'ubah', 'glosarium', gid, title)
    return public(await get_entry(gid))


@router.delete('/glossary/{gid}')
async def delete_glossary(gid: str, u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    g = await get_entry(gid)
    await db.glossaries.delete_one({'id': gid})
    for d in g.get('documents') or []: await remove_stored(d['storage_path'])
    await log_activity(u, 'hapus', 'glosarium', gid, g['title'])
    return {'message': 'Glosarium dihapus.'}


@router.post('/glossary/{gid}/documents')
async def upload_glossary_documents(gid: str, files: list[UploadFile] = File(...), u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    g = await get_entry(gid)
    if not files: raise HTTPException(400, 'Pilih minimal satu dokumen.')
    if len(files) > 20: raise HTTPException(400, 'Maksimal 20 dokumen sekali unggah.')
    docs = []
    for f in files:
        d = await read_file(f, gid)
        docs.append({**d, 'uploaded_by': u['name'], 'created_at': now()})
    await db.glossaries.update_one({'id': gid}, {'$set': {'documents': (g.get('documents') or []) + docs, 'updated_at': now(), 'updated_by': u['name']}})
    await log_activity(u, 'unggah', 'glosarium', gid, g['title'], details={'dokumen': [d['name'] for d in docs]})
    return public(await get_entry(gid))


@router.patch('/glossary/{gid}/documents/{did}')
async def edit_glossary_document(gid: str, did: str, name: str = Form(''), file: UploadFile = File(None), u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    g = await get_entry(gid)
    docs = g.get('documents') or []
    d = next((x for x in docs if x['id'] == did), None)
    if not d: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    name = name.strip()
    if len(name) > 200: raise HTTPException(400, 'Nama dokumen maksimal 200 karakter.')
    if file and file.filename:
        new = await read_file(file, gid)
        await remove_stored(d['storage_path'])
        d.update({k: v for k, v in new.items() if k != 'id'})
    if name: d['name'] = name
    d.update(updated_at=now(), updated_by=u['name'])
    await db.glossaries.update_one({'id': gid}, {'$set': {'documents': docs, 'updated_at': now(), 'updated_by': u['name']}})
    await log_activity(u, 'ubah dokumen', 'glosarium', gid, g['title'], details={'dokumen': d['name']})
    return public(await get_entry(gid))


@router.delete('/glossary/{gid}/documents/{did}')
async def delete_glossary_document(gid: str, did: str, u=Depends(current_user)):
    await authorize(u, 'glossary.write')
    g = await get_entry(gid)
    docs = g.get('documents') or []
    d = next((x for x in docs if x['id'] == did), None)
    if not d: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    await db.glossaries.update_one({'id': gid}, {'$set': {'documents': [x for x in docs if x['id'] != did], 'updated_at': now(), 'updated_by': u['name']}})
    await remove_stored(d['storage_path'])
    await log_activity(u, 'hapus dokumen', 'glosarium', gid, g['title'], details={'dokumen': d['name']})
    return {'message': 'Dokumen dihapus.'}


@router.get('/glossary/{gid}/documents/{did}/download')
async def download_glossary_document(gid: str, did: str, u=Depends(current_user)):
    await authorize(u, 'glossary.read')
    g = await get_entry(gid)
    d = next((x for x in g.get('documents') or [] if x['id'] == did), None)
    if not d: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    try: content = await asyncio.to_thread(get_object, d['storage_path'])
    except Exception: raise HTTPException(503, 'Dokumen belum dapat diunduh.')
    return Response(content, media_type=d['content_type'], headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(d['filename'])}", 'X-Content-Type-Options': 'nosniff'})
