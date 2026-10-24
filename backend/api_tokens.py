import time
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from core import db, uid, now, log_activity
from auth import current_user
from ai_settings import require_ai, AI_ROLES

router = APIRouter()
PAT_PREFIX, OAUTH_PREFIX = 'mh_pat_', 'mh_oat_'
MAX_TOKENS, RATE_PER_MINUTE = 10, 60
_hits = {}

class TokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[Literal['read', 'write']] = Field(default_factory=lambda: ['read'], min_length=1)
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)

def hash_token(raw): return hashlib.sha256(raw.encode()).hexdigest()
def iso_in(seconds): return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
def new_secret(prefix): return prefix + secrets.token_urlsafe(32)
def public_token(t): return {k: v for k, v in t.items() if k not in ('token_hash', 'refresh_hash', '_id')}

def public_base(request: Request):
    proto = request.headers.get('x-forwarded-proto', request.url.scheme).split(',')[0].strip()
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.netloc
    return f'{proto}://{host}'

def ai_user(u):
    if u['role'] not in AI_ROLES: raise HTTPException(403, 'Fitur AI hanya untuk tim internal (Admin, Admin Project, Developer).')
    return u

def rate_limit(key):
    minute = int(time.time() // 60)
    count = _hits.get(key, (minute, 0))
    count = (minute, count[1] + 1) if count[0] == minute else (minute, 1)
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if v[0] != minute]: _hits.pop(k, None)
    _hits[key] = count
    if count[1] > RATE_PER_MINUTE: raise HTTPException(429, 'Terlalu banyak permintaan. Coba lagi dalam satu menit.')

def unauthorized(request, message):
    meta = f'{public_base(request)}/api/.well-known/oauth-protected-resource'
    return HTTPException(401, message, headers={'WWW-Authenticate': f'Bearer resource_metadata="{meta}"'})

async def token_principal(request: Request):
    """Resolve a PAT (mh_pat_) or OAuth access token (mh_oat_) into (user, scopes)."""
    bearer = request.headers.get('Authorization', '')
    raw = bearer[7:].strip() if bearer.startswith('Bearer ') else ''
    if not raw.startswith((PAT_PREFIX, OAUTH_PREFIX)): raise unauthorized(request, 'Token akses tidak ada atau tidak valid.')
    await require_ai()
    row = await db.api_tokens.find_one({'token_hash': hash_token(raw)}, {'_id': 0})
    if not row or row.get('revoked_at'): raise unauthorized(request, 'Token tidak valid atau sudah dicabut.')
    if row.get('expires_at') and row['expires_at'] < now(): raise unauthorized(request, 'Token sudah kedaluwarsa.')
    u = await db.users.find_one({'id': row['user_id'], 'active': True}, {'_id': 0})
    if not u: raise unauthorized(request, 'Akun pemilik token tidak aktif.')
    ai_user(u)
    rate_limit(row['id'])
    await db.api_tokens.update_one({'id': row['id']}, {'$set': {'last_used_at': now()}})
    return u, row.get('scopes') or ['read']

async def any_principal(request: Request):
    """PAT/OAuth token, or the normal CRM login session (full scopes)."""
    bearer = request.headers.get('Authorization', '')
    if bearer.startswith(f'Bearer {PAT_PREFIX}') or bearer.startswith(f'Bearer {OAUTH_PREFIX}'): return await token_principal(request)
    u = ai_user(await current_user(request))
    await require_ai()
    return u, ['read', 'write']

async def issue_token(user, name, scopes, kind='pat', expires_at=None, **extra):
    raw = new_secret(PAT_PREFIX if kind == 'pat' else OAUTH_PREFIX)
    row = {'id': uid(), 'user_id': user['id'], 'name': name, 'kind': kind, 'token_hash': hash_token(raw), 'prefix': raw[:12],
           'scopes': sorted(set(scopes) | {'read'}), 'created_at': now(), 'last_used_at': None, 'expires_at': expires_at, 'revoked_at': None, **extra}
    await db.api_tokens.insert_one(row.copy())
    return raw, row

@router.get('/me/tokens')
async def my_tokens(u=Depends(current_user)):
    ai_user(u); await require_ai()
    rows = await db.api_tokens.find({'user_id': u['id']}, {'_id': 0}).sort('created_at', -1).to_list(200)
    return [public_token(r) for r in rows]

@router.post('/me/tokens')
async def create_token(data: TokenInput, u=Depends(current_user)):
    ai_user(u); await require_ai()
    rows = await db.api_tokens.find({'user_id': u['id'], 'kind': 'pat', 'revoked_at': None}, {'_id': 0, 'expires_at': 1}).to_list(1000)
    active = sum(1 for r in rows if not r.get('expires_at') or r['expires_at'] >= now())
    if active >= MAX_TOKENS: raise HTTPException(400, f'Maksimal {MAX_TOKENS} token aktif per akun. Cabut token lama terlebih dahulu.')
    expires = iso_in(data.expires_days * 86400) if data.expires_days else None
    raw, row = await issue_token(u, data.name.strip(), data.scopes, expires_at=expires)
    await log_activity(u, 'buat', 'token API', row['id'], row['name'], '', {'scopes': row['scopes'], 'expires_at': expires})
    return {**public_token(row), 'token': raw}

async def revoke(u, q):
    row = await db.api_tokens.find_one(q, {'_id': 0})
    if not row: raise HTTPException(404, 'Token tidak ditemukan.')
    if not row.get('revoked_at'): await db.api_tokens.update_one({'id': row['id']}, {'$set': {'revoked_at': now()}})
    await log_activity(u, 'cabut', 'token API', row['id'], row['name'], '', {'pemilik': row['user_id']})
    return {'message': 'Token dicabut.'}

@router.delete('/me/tokens/{tid}')
async def revoke_my_token(tid: str, u=Depends(current_user)):
    ai_user(u)
    return await revoke(u, {'id': tid, 'user_id': u['id']})

@router.get('/admin/tokens')
async def admin_tokens(u=Depends(current_user)):
    if u['role'] != 'Admin': raise HTTPException(403, 'Anda tidak memiliki izin untuk tindakan ini.')
    rows = await db.api_tokens.find({}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    users = {x['id']: x['name'] for x in await db.users.find({'id': {'$in': list({r['user_id'] for r in rows})}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(1000)}
    return [{**public_token(r), 'user_name': users.get(r['user_id'], '')} for r in rows]

@router.delete('/admin/tokens/{tid}')
async def admin_revoke_token(tid: str, u=Depends(current_user)):
    if u['role'] != 'Admin': raise HTTPException(403, 'Anda tidak memiliki izin untuk tindakan ini.')
    return await revoke(u, {'id': tid})
