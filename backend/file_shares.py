import asyncio
import hashlib
import hmac
import mimetypes
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from core import db, uid, now, project_for, log_activity
from auth import current_user, hash_password, verify_password
from storage import get_object

router = APIRouter()
SHARE_ROLES = ['Admin', 'Admin Project', 'Developer', 'Accounting']
MAX_DAYS = 365
MAX_DOCS = 50
MAX_FAILS = 10

class ShareInput(BaseModel):
    document_id: str = ''
    document_ids: List[str] = []
    expires_at: Optional[datetime] = None
    allow_download: bool = True
    password: str = ''

class UnlockInput(BaseModel):
    password: str

async def shareable_document(u, did):
    """Same access rules as the authenticated download endpoint."""
    if u['role'] not in SHARE_ROLES: raise HTTPException(403, 'Anda tidak memiliki izin membagikan dokumen.')
    d = await db.project_documents.find_one({'id': did, 'is_deleted': False}, {'_id': 0})
    if not d: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    await project_for(u, d['project_id'], 'document.read')
    if u['role'] == 'Accounting' and d.get('kind') not in ['Kontrak', 'Penawaran Harga', 'Invoice', 'BAST']: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    return d

def share_ids(s): return s.get('document_ids') or [s['document_id']]

def share_public(s):
    out = {k: v for k, v in s.items() if k not in ('_id', 'password_hash', 'failed_attempts', 'locked_until')}
    out['has_password'] = bool(s.get('password_hash'))
    out['document_ids'] = share_ids(s)
    return out

def alive(s): return not s.get('revoked_at') and (not s.get('expires_at') or s['expires_at'] > now())

async def create_share(u, d, expires_at, allow_download=True, docs=None, password=''):
    docs = docs or [d]
    exp = None
    if expires_at:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        current = datetime.now(timezone.utc)
        if exp <= current + timedelta(minutes=1): raise HTTPException(400, 'Waktu kedaluwarsa harus di masa depan.')
        if exp > current + timedelta(days=MAX_DAYS): raise HTTPException(400, f'Masa berlaku link maksimal {MAX_DAYS} hari.')
        exp = exp.astimezone(timezone.utc).isoformat()
    password = (password or '').strip()
    if password and len(password) < 4: raise HTTPException(400, 'Password link minimal 4 karakter.')
    if len(password.encode()) > 72: raise HTTPException(400, 'Password link maksimal 72 karakter.')
    name = docs[0]['name'] if len(docs) == 1 else f"{len(docs)} dokumen: " + ', '.join(x['name'] for x in docs[:3]) + ('…' if len(docs) > 3 else '')
    s = {'id': uid(), 'token': secrets.token_urlsafe(18), 'document_id': docs[0]['id'], 'document_ids': [x['id'] for x in docs], 'project_id': d['project_id'], 'task_id': d.get('task_id', ''),
         'name': name, 'document_type': docs[0].get('document_type') or 'file' if len(docs) == 1 else 'bundle', 'expires_at': exp, 'allow_download': bool(allow_download),
         'password_hash': hash_password(password) if password else '', 'views': 0, 'downloads': 0, 'created_at': now(), 'created_by': u['id'], 'created_by_name': u['name'], 'revoked_at': None}
    await db.file_shares.insert_one(s.copy())
    await log_activity(u, 'bagikan link', 'dokumen', docs[0]['id'], name, d['project_id'], {'kedaluwarsa': exp or 'tanpa batas', 'download': s['allow_download'], 'password': bool(password), 'jumlah': len(docs)})
    return s

@router.post('/shares')
async def new_share(data: ShareInput, u=Depends(current_user)):
    ids = list(dict.fromkeys(data.document_ids or ([data.document_id] if data.document_id else [])))
    if not ids: raise HTTPException(400, 'Pilih minimal satu dokumen.')
    if len(ids) > MAX_DOCS: raise HTTPException(400, f'Maksimal {MAX_DOCS} dokumen per link.')
    docs = [await shareable_document(u, i) for i in ids]
    if len({x['project_id'] for x in docs}) > 1: raise HTTPException(400, 'Dokumen harus dari project yang sama.')
    return share_public(await create_share(u, docs[0], data.expires_at, data.allow_download, docs, data.password))

@router.get('/shares')
async def list_shares(document_id: str, u=Depends(current_user)):
    d = await shareable_document(u, document_id)
    rows = await db.file_shares.find({'project_id': d['project_id'], 'revoked_at': None}, {'_id': 0}).sort('created_at', -1).to_list(500)
    return [share_public(r) for r in rows if document_id in share_ids(r) and alive(r)][:100]

@router.delete('/shares/{sid}')
async def revoke_share(sid: str, u=Depends(current_user)):
    s = await db.file_shares.find_one({'id': sid, 'revoked_at': None}, {'_id': 0})
    if not s: raise HTTPException(404, 'Link tidak ditemukan.')
    if u['role'] not in SHARE_ROLES: raise HTTPException(403, 'Anda tidak memiliki izin membagikan dokumen.')
    await project_for(u, s['project_id'], 'document.read')
    await db.file_shares.update_one({'id': sid}, {'$set': {'revoked_at': now(), 'revoked_by': u['id']}})
    await log_activity(u, 'cabut link', 'dokumen', s['document_id'], s['name'], s['project_id'])
    return {'message': 'Link berbagi dicabut.'}

def access_key(s):
    return hmac.new(os.environ['JWT_SECRET'].encode(), f"{s['token']}:{s['password_hash']}".encode(), hashlib.sha256).hexdigest()[:40]

def check_access(s, k):
    if s.get('password_hash') and not hmac.compare_digest(k or '', access_key(s)):
        raise HTTPException(401, 'Link ini dilindungi password.')

async def live_share(token, k=''):
    s = await db.file_shares.find_one({'token': token}, {'_id': 0})
    if not s or s.get('revoked_at'): raise HTTPException(404, 'Link tidak ditemukan atau sudah dicabut.')
    if s.get('expires_at') and s['expires_at'] <= now(): raise HTTPException(410, 'Link ini sudah kedaluwarsa.')
    check_access(s, k)
    docs = [x for x in await db.project_documents.find({'id': {'$in': share_ids(s)}, 'is_deleted': False}, {'_id': 0}).to_list(MAX_DOCS)]
    order = share_ids(s)
    docs.sort(key=lambda x: order.index(x['id']))
    if not docs: raise HTTPException(404, 'File sudah tidak tersedia.')
    return s, docs

def file_info(d):
    if d.get('document_type') == 'link':
        return {'id': d['id'], 'name': d['name'], 'document_type': 'link', 'url': d.get('url', ''), 'kind': d.get('kind')}
    fname = d.get('filename') or d['name']
    return {'id': d['id'], 'document_type': 'file', 'name': d['name'], 'filename': fname, 'size': d.get('size', 0),
            'content_type': mimetypes.guess_type(fname)[0] or d.get('content_type', ''), 'kind': d.get('kind')}

@router.post('/public/shares/{token}/unlock')
async def share_unlock(token: str, data: UnlockInput):
    s = await db.file_shares.find_one({'token': token}, {'_id': 0})
    if not s or s.get('revoked_at'): raise HTTPException(404, 'Link tidak ditemukan atau sudah dicabut.')
    if s.get('expires_at') and s['expires_at'] <= now(): raise HTTPException(410, 'Link ini sudah kedaluwarsa.')
    if not s.get('password_hash'): return {'key': ''}
    if s.get('locked_until') and s['locked_until'] > now(): raise HTTPException(429, 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.')
    if len(data.password.encode()) > 72 or not verify_password(data.password, s['password_hash']):
        fails = s.get('failed_attempts', 0) + 1
        upd = {'failed_attempts': 0, 'locked_until': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()} if fails >= MAX_FAILS else {'failed_attempts': fails}
        await db.file_shares.update_one({'id': s['id']}, {'$set': upd})
        await asyncio.sleep(0.6)
        raise HTTPException(400, 'Password salah.')
    await db.file_shares.update_one({'id': s['id']}, {'$set': {'failed_attempts': 0}})
    return {'key': access_key(s)}

@router.get('/public/shares/{token}')
async def share_info(token: str, k: str = ''):
    s, docs = await live_share(token, k)
    await db.file_shares.update_one({'id': s['id']}, {'$inc': {'views': 1}})
    files = [file_info(d) for d in docs]
    meta = {'expires_at': s.get('expires_at'), 'allow_download': s['allow_download'], 'shared_by': s['created_by_name'], 'created_at': s['created_at'],
            'has_password': bool(s.get('password_hash')), 'files': files}
    first = dict(files[0])
    if first['document_type'] == 'link' and len(files) == 1: meta['allow_download'] = False
    return {**first, **meta}

@router.get('/public/shares/{token}/file')
async def share_file(token: str, download: bool = False, doc: str = '', k: str = ''):
    s, docs = await live_share(token, k)
    d = next((x for x in docs if x['id'] == doc), None) if doc else docs[0]
    if not d: raise HTTPException(404, 'File tidak ditemukan pada link ini.')
    if d.get('document_type') == 'link': raise HTTPException(400, 'Dokumen ini berupa link, buka melalui halaman berbagi.')
    if download and not s['allow_download']: raise HTTPException(403, 'Pemilik link hanya mengizinkan melihat file.')
    try: content = await asyncio.to_thread(get_object, d['storage_path'])
    except Exception: raise HTTPException(503, 'File belum dapat dimuat.')
    if download: await db.file_shares.update_one({'id': s['id']}, {'$inc': {'downloads': 1}})
    mode = 'attachment' if download else 'inline'
    fname = d.get('filename') or d['name']
    media = mimetypes.guess_type(fname)[0] or 'application/octet-stream'
    if media.startswith('text/'): media += '; charset=utf-8'
    return Response(content, media_type=media, headers={'Content-Disposition': f"{mode}; filename*=UTF-8''{quote(fname)}", 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})
