"""Photos in task descriptions and files attached to task comments."""
import asyncio
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from core import db, uid, now, log_activity
from auth import current_user
from schemas import Record
from storage import put_object, get_object, delete_object
from kanban import task_for, one, check_comment, save_comment, can_edit

router = APIRouter(prefix='/projects/{pid}/tasks/{tid}')
IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
DOC_TYPES = {'.pdf': 'application/pdf', '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
             '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             '.ppt': 'application/vnd.ms-powerpoint', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
             '.txt': 'text/plain', '.csv': 'text/csv', '.zip': 'application/zip', '.rar': 'application/vnd.rar'}
MAX_SIZE = 10 * 1024 * 1024
MAX_FILES = 5
MAX_IMAGES = 20


async def store_files(files, folder, allowed, u):
    if len(files) > MAX_FILES: raise HTTPException(400, f'Maksimal {MAX_FILES} berkas sekali kirim.')
    exts = [Path(f.filename or '').suffix.lower() for f in files]
    bad = next((e for e in exts if e not in allowed), None)
    if bad is not None: raise HTTPException(400, f"Format {bad or 'berkas'} tidak didukung.")
    blobs = [await f.read(MAX_SIZE + 1) for f in files]
    if any(not b or len(b) > MAX_SIZE for b in blobs): raise HTTPException(400, 'Setiap berkas maksimal 10 MB.')
    saved = []
    for f, ext, data in zip(files, exts, blobs):
        fid = uid()
        try: stored = await asyncio.to_thread(put_object, f'crm-maiharta/{folder}/{fid}{ext}', data, allowed[ext])
        except Exception:
            remove_files(saved)
            raise HTTPException(503, 'Penyimpanan berkas belum dapat dihubungi.')
        saved.append({'id': fid, 'name': Path(f.filename).name[:200], 'size': len(data), 'content_type': allowed[ext], 'is_image': ext in IMAGE_TYPES,
                      'storage_path': stored['path'], 'uploaded_by': u['name'], 'created_at': now()})
    return saved


def remove_files(files):
    for a in files or []:
        try: delete_object(a['storage_path'])
        except Exception: pass


async def file_response(a):
    try: content = await asyncio.to_thread(get_object, a['storage_path'])
    except Exception: raise HTTPException(503, 'Berkas belum dapat diunduh.')
    mode = 'inline' if a.get('is_image') else 'attachment'
    return Response(content, media_type=a['content_type'], headers={'Content-Disposition': f"{mode}; filename*=UTF-8''{quote(a['name'])}", 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=3600'})


@router.post('/images', response_model=Record)
async def upload_images(pid: str, tid: str, files: list[UploadFile] = File(...), u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.write')
    existing = t.get('description_images') or []
    if len(existing) + len(files) > MAX_IMAGES: raise HTTPException(400, f'Maksimal {MAX_IMAGES} foto per deskripsi task.')
    added = await store_files(files, f'tasks/{tid}/images', IMAGE_TYPES, u)
    await db.tasks.update_one({'id': tid}, {'$set': {'description_images': existing + added, 'updated_at': now()}})
    await log_activity(u, 'unggah', 'foto task', tid, t['title'], pid, {'foto': [a['name'] for a in added]})
    return await one(tid, u)


@router.get('/images/{iid}')
async def get_image(pid: str, tid: str, iid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid)
    image = next((a for a in t.get('description_images') or [] if a['id'] == iid), None)
    if not image: raise HTTPException(404, 'Foto tidak ditemukan.')
    return await file_response(image)


@router.delete('/images/{iid}', response_model=Record)
async def delete_image(pid: str, tid: str, iid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.write')
    images = t.get('description_images') or []
    image = next((a for a in images if a['id'] == iid), None)
    if not image: raise HTTPException(404, 'Foto tidak ditemukan.')
    await db.tasks.update_one({'id': tid}, {'$set': {'description_images': [a for a in images if a['id'] != iid], 'updated_at': now()}})
    remove_files([image])
    return await one(tid, u)


def subtask_of(t, sid):
    s = next((x for x in t.get('subtasks') or [] if x['id'] == sid), None)
    if not s: raise HTTPException(404, 'Subtask tidak ditemukan.')
    return s


@router.post('/subtasks/{sid}/images', response_model=Record)
async def upload_subtask_images(pid: str, tid: str, sid: str, files: list[UploadFile] = File(...), u=Depends(current_user)):
    p, t = await task_for(u, pid, tid, 'task.progress'); can_edit(u, t)
    s = subtask_of(t, sid)
    existing = s.get('images') or []
    if len(existing) + len(files) > MAX_IMAGES: raise HTTPException(400, f'Maksimal {MAX_IMAGES} foto per deskripsi subtask.')
    s['images'] = existing + await store_files(files, f'tasks/{tid}/subtasks/{sid}', IMAGE_TYPES, u)
    await db.tasks.update_one({'id': tid}, {'$set': {'subtasks': t['subtasks'], 'updated_at': now()}})
    return await one(tid, u)


@router.get('/subtasks/{sid}/images/{iid}')
async def get_subtask_image(pid: str, tid: str, sid: str, iid: str, u=Depends(current_user)):
    p, t = await task_for(u, pid, tid)
    image = next((a for a in subtask_of(t, sid).get('images') or [] if a['id'] == iid), None)
    if not image: raise HTTPException(404, 'Foto tidak ditemukan.')
    return await file_response(image)


@router.post('/comments/upload', response_model=Record)
async def comment_with_files(pid: str, tid: str, message: str = Form(''), assigned_to: str = Form(''), files: list[UploadFile] = File(...), u=Depends(current_user)):
    p, t = await task_for(u, pid, tid)
    message = message.strip()
    if len(message) > 3000: raise HTTPException(400, 'Komentar maksimal 3000 karakter.')
    by_id, mention_ids = await check_comment(p, u, message, assigned_to)
    attachments = await store_files(files, f'tasks/{tid}/comments', {**IMAGE_TYPES, **DOC_TYPES}, u)
    return await save_comment(pid, tid, u, message, assigned_to, by_id, mention_ids, attachments)


@router.get('/comments/{cid}/attachments/{aid}')
async def comment_file(pid: str, tid: str, cid: str, aid: str, u=Depends(current_user)):
    await task_for(u, pid, tid)
    c = await db.task_comments.find_one({'id': cid, 'task_id': tid}, {'_id': 0})
    a = next((x for x in (c or {}).get('attachments') or [] if x['id'] == aid), None)
    if not a: raise HTTPException(404, 'Lampiran tidak ditemukan.')
    return await file_response(a)
