import os, secrets, hashlib, bcrypt, jwt, asyncio, requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from core import db, uid, now, log_activity
from schemas import Login, PasswordChange
from pydantic import BaseModel, Field

router = APIRouter(prefix='/auth')
SECRET = os.environ['JWT_SECRET']
RECAPTCHA_SECRET = os.environ.get('RECAPTCHA_SECRET_KEY', '').strip()
RECAPTCHA_SITE = os.environ.get('RECAPTCHA_SITE_KEY', '').strip()
IDLE_TIMEOUT_SECONDS = 15 * 60

class SessionActivity(BaseModel):
    idle_for_ms: int = Field(default=0, ge=0, lt=IDLE_TIMEOUT_SECONDS * 1000)

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, hashed):
    try: return bcrypt.checkpw(p.encode(), hashed.encode())
    except ValueError: return False
def public_user(u): return {k: u.get(k) for k in ['id','name','username','email','role','client_id','active']} | {'whatsapp_number': u.get('whatsapp_number', ''), 'must_change_password': bool(u.get('must_change_password')), 'welcome_pending': bool(u.get('welcome_pending'))}

async def current_user(request: Request):
    bearer = request.headers.get('Authorization', '')
    token = bearer[7:] if bearer.startswith('Bearer ') else request.cookies.get('maiharta_session')
    if not token: raise HTTPException(401, 'Silakan masuk terlebih dahulu.')
    try:
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        u = await db.users.find_one({'id': payload['sub'], 'active': True}, {'_id': 0})
        session = await db.sessions.find_one({'id': payload['jti'], 'user_id': payload['sub']}, {'_id': 0})
        if not u or not session: raise ValueError()
        current_time = datetime.now(timezone.utc)
        last_activity = session.get('last_activity_at')
        if last_activity is None:
            # One-time migration of sessions created before idle expiry existed.
            last_activity = current_time
            await db.sessions.update_one({'id': session['id'], 'last_activity_at': {'$exists': False}}, {'$set': {'last_activity_at': last_activity}})
        last_activity = last_activity.replace(tzinfo=timezone.utc)
        if (current_time - last_activity).total_seconds() >= IDLE_TIMEOUT_SECONDS:
            await db.sessions.delete_one({'id': session['id']})
            raise HTTPException(401, 'Sesi berakhir karena tidak ada aktivitas selama 15 menit. Silakan masuk kembali.')
        request.state.session_id = session['id']
        request.state.session_last_activity = last_activity.timestamp() * 1000
        return u
    except HTTPException: raise
    except Exception: raise HTTPException(401, 'Sesi berakhir. Silakan masuk kembali.')

@router.get('/captcha')
async def captcha():
    if RECAPTCHA_SECRET and RECAPTCHA_SITE: return {'provider': 'recaptcha', 'site_key': RECAPTCHA_SITE}
    a, b = secrets.randbelow(18) + 2, secrets.randbelow(9) + 1
    cid = uid()
    await db.captchas.insert_one({'id': cid, 'answer': hashlib.sha256(str(a+b).encode()).hexdigest(), 'expires_at': datetime.now(timezone.utc) + timedelta(minutes=5)})
    return {'provider': 'math', 'id': cid, 'question': f'{a} + {b} = ?'}

def verify_recaptcha(token):
    try:
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data={'secret': RECAPTCHA_SECRET, 'response': token}, timeout=8)
        return bool(r.json().get('success'))
    except Exception: return False

async def check_captcha(data):
    if RECAPTCHA_SECRET and RECAPTCHA_SITE:
        if not data.recaptcha_token: return False
        return await asyncio.to_thread(verify_recaptcha, data.recaptcha_token)
    c = await db.captchas.find_one_and_delete({'id': data.captcha_id}, projection={'_id':0})
    return bool(c and c['expires_at'].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) and secrets.compare_digest(c['answer'], hashlib.sha256(data.captcha_answer.encode()).hexdigest()))

@router.post('/login')
async def login(data: Login, request: Request, response: Response):
    key = hashlib.sha256(data.username.lower().encode()).hexdigest()
    attempts = await db.login_attempts.count_documents({'key': key, 'created_at': {'$gt': datetime.now(timezone.utc)-timedelta(minutes=10)}})
    if attempts >= 15: raise HTTPException(429, 'Terlalu banyak percobaan. Coba lagi dalam 10 menit.')
    if not await check_captcha(data):
        await db.login_attempts.insert_one({'key': key, 'created_at': datetime.now(timezone.utc)})
        raise HTTPException(400, 'Verifikasi CAPTCHA gagal atau sudah kedaluwarsa.')
    u = await db.users.find_one({'username': data.username.lower(), 'active': True}, {'_id':0})
    if not u or not verify_password(data.password, u['password_hash']):
        await db.login_attempts.insert_one({'key': key, 'created_at': datetime.now(timezone.utc)})
        raise HTTPException(401, 'Username atau password tidak sesuai.')
    seconds = 604800 if data.remember else 28800
    sid = uid()
    expires = datetime.now(timezone.utc)+timedelta(seconds=seconds)
    await db.sessions.insert_one({'id':sid, 'user_id':u['id'], 'expires_at':expires, 'last_activity_at':datetime.now(timezone.utc)})
    token = jwt.encode({'sub':u['id'], 'jti':sid, 'exp':expires}, SECRET, algorithm='HS256')
    response.set_cookie('maiharta_session',token,httponly=True,secure=True,samesite='none',max_age=seconds,path='/')
    await log_activity(u, 'login', 'sesi', u['id'], u['name'])
    return {'token':token,'user':public_user(u)}

@router.get('/me')
async def me(request: Request, u=Depends(current_user)):
    return {**public_user(u), 'session_last_activity': request.state.session_last_activity}

@router.post('/activity')
async def activity(data: SessionActivity, request: Request, u=Depends(current_user)):
    # Only explicit user interaction renews inactivity, never polling or /me.
    timestamp = datetime.now(timezone.utc) - timedelta(milliseconds=data.idle_for_ms)
    await db.sessions.update_one({'id': request.state.session_id}, {'$max': {'last_activity_at': timestamp}})
    return {'idle_timeout_seconds': IDLE_TIMEOUT_SECONDS}

@router.post('/logout')
async def logout(request: Request, response: Response):
    bearer = request.headers.get('Authorization', '')
    token = bearer[7:] if bearer.startswith('Bearer ') else request.cookies.get('maiharta_session')
    try:
        payload = jwt.decode(token,SECRET,algorithms=['HS256'])
        await db.sessions.delete_one({'id':payload['jti']})
    except Exception: pass
    response.delete_cookie('maiharta_session',path='/',secure=True,samesite='none')
    return {'message':'Anda sudah keluar.'}

@router.post('/welcome-seen')
async def welcome_seen(u=Depends(current_user)):
    await db.users.update_one({'id': u['id']}, {'$set': {'welcome_pending': False, 'welcome_seen_at': now()}})
    return {'message': 'Selamat datang di CRM Maiharta.'}

@router.post('/password')
async def change_password(data: PasswordChange, u=Depends(current_user)):
    if not verify_password(data.current_password,u['password_hash']): raise HTTPException(400,'Password saat ini tidak sesuai.')
    await db.users.update_one({'id':u['id']},{'$set':{'password_hash':hash_password(data.new_password),'must_change_password':False}})
    await db.sessions.delete_many({'user_id':u['id']})
    return {'message':'Password diubah. Silakan masuk kembali.'}