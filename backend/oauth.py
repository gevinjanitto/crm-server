import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from core import db, uid, now, log_activity
from auth import current_user
from ai_settings import require_ai
from api_tokens import public_base, hash_token, issue_token, ai_user, new_secret, iso_in

router = APIRouter()
ACCESS_TTL, REFRESH_TTL, CODE_TTL = 3600, 30 * 86400, 600

class ApproveInput(BaseModel):
    client_id: str
    redirect_uri: str
    code_challenge: str = Field(min_length=20, max_length=200)
    code_challenge_method: str = 'S256'
    state: str = ''
    scope: str = 'read write'
    approve: bool = True

def oauth_error(error, description, status=400): return JSONResponse({'error': error, 'error_description': description}, status_code=status)
def scopes_of(text): return sorted({s for s in (text or 'read').replace(',', ' ').split() if s in ('read', 'write')} | {'read'})

def resource_metadata(request: Request):
    base = public_base(request)
    return {'resource': f'{base}/api/mcp', 'authorization_servers': [f'{base}/api'], 'scopes_supported': ['read', 'write'], 'bearer_methods_supported': ['header'], 'resource_name': 'CRM Maiharta'}

def server_metadata(request: Request):
    base = public_base(request)
    return {'issuer': f'{base}/api', 'authorization_endpoint': f'{base}/api/oauth/authorize', 'token_endpoint': f'{base}/api/oauth/token',
            'registration_endpoint': f'{base}/api/oauth/register', 'revocation_endpoint': f'{base}/api/oauth/revoke',
            'response_types_supported': ['code'], 'grant_types_supported': ['authorization_code', 'refresh_token'], 'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['none', 'client_secret_post', 'client_secret_basic'], 'scopes_supported': ['read', 'write']}

@router.get('/.well-known/oauth-protected-resource')
@router.get('/.well-known/oauth-protected-resource/{rest:path}')
async def protected_resource(request: Request, rest: str = ''): return resource_metadata(request)

@router.get('/.well-known/oauth-authorization-server')
@router.get('/.well-known/oauth-authorization-server/{rest:path}')
@router.get('/.well-known/openid-configuration')
@router.get('/.well-known/openid-configuration/{rest:path}')
async def authorization_server(request: Request, rest: str = ''): return server_metadata(request)

@router.post('/oauth/register')
async def register(request: Request):
    await require_ai()
    try: body = await request.json()
    except Exception: return oauth_error('invalid_client_metadata', 'Body harus JSON.')
    uris = [u for u in body.get('redirect_uris') or [] if isinstance(u, str) and u.startswith(('https://', 'http://localhost', 'http://127.0.0.1'))]
    if not uris: return oauth_error('invalid_redirect_uri', 'redirect_uris wajib berupa URL https.')
    client = {'id': 'mhc_' + secrets.token_urlsafe(16), 'client_name': str(body.get('client_name') or 'Klien MCP')[:80], 'redirect_uris': uris[:10], 'created_at': now()}
    await db.oauth_clients.insert_one(client.copy())
    return JSONResponse({'client_id': client['id'], 'client_id_issued_at': int(datetime.now(timezone.utc).timestamp()), 'client_name': client['client_name'],
                         'redirect_uris': uris, 'grant_types': ['authorization_code', 'refresh_token'], 'response_types': ['code'], 'token_endpoint_auth_method': 'none'}, status_code=201)

async def valid_client(client_id, redirect_uri):
    c = await db.oauth_clients.find_one({'id': client_id}, {'_id': 0})
    if not c: raise HTTPException(400, 'Aplikasi OAuth tidak dikenal.')
    if redirect_uri not in c['redirect_uris']: raise HTTPException(400, 'redirect_uri tidak terdaftar untuk aplikasi ini.')
    return c

@router.get('/oauth/authorize')
async def authorize(request: Request, client_id: str, redirect_uri: str, response_type: str = 'code', code_challenge: str = '', code_challenge_method: str = 'S256', state: str = '', scope: str = 'read write'):
    await require_ai()
    await valid_client(client_id, redirect_uri)
    if response_type != 'code' or code_challenge_method != 'S256' or not code_challenge: raise HTTPException(400, 'Wajib response_type=code dan PKCE S256.')
    query = urlencode({'client_id': client_id, 'redirect_uri': redirect_uri, 'code_challenge': code_challenge, 'code_challenge_method': 'S256', 'state': state, 'scope': scope})
    return RedirectResponse(f'{public_base(request)}/oauth/authorize?{query}', status_code=302)

@router.get('/oauth/client')
async def client_info(client_id: str, redirect_uri: str, u=Depends(current_user)):
    ai_user(u); await require_ai()
    c = await valid_client(client_id, redirect_uri)
    return {'client_name': c['client_name'], 'redirect_host': redirect_uri.split('/')[2] if '//' in redirect_uri else redirect_uri}

@router.post('/oauth/approve')
async def approve(data: ApproveInput, u=Depends(current_user)):
    ai_user(u); await require_ai()
    c = await valid_client(data.client_id, data.redirect_uri)
    sep = '&' if '?' in data.redirect_uri else '?'
    if not data.approve: return {'redirect': f"{data.redirect_uri}{sep}{urlencode({'error': 'access_denied', 'state': data.state})}"}
    code = secrets.token_urlsafe(32)
    await db.oauth_codes.insert_one({'id': hash_token(code), 'client_id': c['id'], 'user_id': u['id'], 'redirect_uri': data.redirect_uri, 'code_challenge': data.code_challenge,
                                     'scopes': scopes_of(data.scope), 'expires_at': iso_in(CODE_TTL), 'created_at': now()})
    await log_activity(u, 'izinkan', 'koneksi OAuth', c['id'], c['client_name'], '', {'scopes': scopes_of(data.scope)})
    return {'redirect': f"{data.redirect_uri}{sep}{urlencode({'code': code, 'state': data.state})}"}

def pkce_ok(verifier, challenge):
    digest = base64.urlsafe_b64encode(hashlib.sha256((verifier or '').encode()).digest()).rstrip(b'=').decode()
    return secrets.compare_digest(digest, challenge)

async def token_response(row, access, refresh):
    return JSONResponse({'access_token': access, 'token_type': 'Bearer', 'expires_in': ACCESS_TTL, 'refresh_token': refresh, 'scope': ' '.join(row['scopes'])}, headers={'Cache-Control': 'no-store'})

@router.post('/oauth/token')
async def token(request: Request):
    await require_ai()
    form = dict(await request.form())
    grant = form.get('grant_type')
    if grant == 'authorization_code':
        code = await db.oauth_codes.find_one({'id': hash_token(form.get('code', ''))}, {'_id': 0})
        if not code or code['expires_at'] < now(): return oauth_error('invalid_grant', 'Kode otorisasi tidak valid atau kedaluwarsa.')
        await db.oauth_codes.delete_one({'id': code['id']})
        if form.get('client_id') and form['client_id'] != code['client_id']: return oauth_error('invalid_grant', 'client_id tidak sesuai.')
        if form.get('redirect_uri') and form['redirect_uri'] != code['redirect_uri']: return oauth_error('invalid_grant', 'redirect_uri tidak sesuai.')
        if not pkce_ok(form.get('code_verifier'), code['code_challenge']): return oauth_error('invalid_grant', 'code_verifier tidak valid.')
        u = await db.users.find_one({'id': code['user_id'], 'active': True}, {'_id': 0})
        if not u: return oauth_error('invalid_grant', 'Akun tidak aktif.')
        c = await db.oauth_clients.find_one({'id': code['client_id']}, {'_id': 0}) or {}
        refresh = new_secret('mh_ort_')
        access, row = await issue_token(u, c.get('client_name', 'OAuth'), code['scopes'], kind='oauth', expires_at=iso_in(ACCESS_TTL),
                                        client_id=code['client_id'], refresh_hash=hash_token(refresh), refresh_expires_at=iso_in(REFRESH_TTL))
        return await token_response(row, access, refresh)
    if grant == 'refresh_token':
        row = await db.api_tokens.find_one({'refresh_hash': hash_token(form.get('refresh_token', '')), 'kind': 'oauth'}, {'_id': 0})
        if not row or row.get('revoked_at') or row.get('refresh_expires_at', '') < now(): return oauth_error('invalid_grant', 'Refresh token tidak valid.')
        access, refresh = new_secret('mh_oat_'), new_secret('mh_ort_')
        await db.api_tokens.update_one({'id': row['id']}, {'$set': {'token_hash': hash_token(access), 'prefix': access[:12], 'refresh_hash': hash_token(refresh),
                                                                    'expires_at': iso_in(ACCESS_TTL), 'refresh_expires_at': iso_in(REFRESH_TTL)}})
        return await token_response(row, access, refresh)
    return oauth_error('unsupported_grant_type', 'grant_type tidak didukung.')

@router.post('/oauth/revoke')
async def revoke_token(request: Request):
    raw = (dict(await request.form())).get('token', '')
    h = hash_token(raw)
    await db.api_tokens.update_many({'$or': [{'token_hash': h}, {'refresh_hash': h}], 'revoked_at': None}, {'$set': {'revoked_at': now()}})
    return JSONResponse({}, status_code=200)
