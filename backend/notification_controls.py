from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core import db, now, authorize, log_activity, DEFAULT_CLIENT_PASSWORD
from auth import current_user, hash_password
from notify import notify
from notification_delivery import global_pause, PAUSE_ID

router = APIRouter()


class ChannelSwitch(BaseModel):
    email: bool = False
    whatsapp: bool = False


@router.get('/admin/notification-pause')
async def get_pause(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    return await global_pause()


@router.put('/admin/notification-pause')
async def set_pause(data: ChannelSwitch, u=Depends(current_user)):
    await authorize(u, 'user.manage')
    await db.app_settings.update_one({'id': PAUSE_ID}, {'$set': {**data.model_dump(), 'updated_at': now(), 'updated_by': u['id']}}, upsert=True)
    await log_activity(u, 'ubah', 'notifikasi', PAUSE_ID, 'Jeda notifikasi semua akun', '', data.model_dump())
    return data.model_dump()


@router.put('/users/{user_id}/notification-mute')
async def set_user_mute(user_id: str, data: ChannelSwitch, u=Depends(current_user)):
    await authorize(u, 'user.manage')
    row = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1})
    if not row: raise HTTPException(404, 'User tidak ditemukan.')
    await db.users.update_one({'id': user_id}, {'$set': {'notification_mute': data.model_dump()}})
    await log_activity(u, 'ubah', 'user', user_id, row['name'], '', {'notification_mute': data.model_dump()})
    return data.model_dump()


@router.post('/users/{user_id}/reset-password')
async def reset_password(user_id: str, u=Depends(current_user)):
    await authorize(u, 'user.manage')
    if user_id == u['id']: raise HTTPException(400, 'Ganti password akun sendiri melalui Pengaturan.')
    row = await db.users.find_one({'id': user_id}, {'_id': 0})
    if not row: raise HTTPException(404, 'User tidak ditemukan.')
    if not row.get('active'): raise HTTPException(400, 'Aktifkan akun terlebih dahulu sebelum reset password.')
    await db.users.update_one({'id': user_id}, {'$set': {'password_hash': hash_password(DEFAULT_CLIENT_PASSWORD), 'must_change_password': True, 'password_reset_at': now()}})
    await db.sessions.delete_many({'user_id': user_id})
    await log_activity(u, 'ubah', 'user', user_id, row['name'], '', {'reset_password_default': True})
    first_login = ' Setelah masuk, Anda akan diminta membuat password baru (minimal 10 karakter).'
    message = f"{u['name']} dari CV Maiharta telah mengembalikan password akun CRM Maiharta Anda ke password default. Masuk memakai username dan password di bawah ini." + first_login
    wa = f"Password akun CRM Maiharta Anda telah dikembalikan ke default. Username: {row['username']}. Password: {DEFAULT_CLIENT_PASSWORD}." + first_login
    title = 'Password akun CRM Maiharta Anda telah direset'
    docs = await notify([user_id], title, 'Password akun Anda telah dikembalikan ke default oleh Admin.' + first_login, 'akun', '/', '', 'user', user_id, u,
                 wait_for_delivery=True,
                 external={'message': message, 'whatsapp_message': wa, 'credentials': [('Username', row['username']), ('Password', DEFAULT_CLIENT_PASSWORD)], 'force_external': True})
    sent = await db.notification_deliveries.find({'notification_id': {'$in': [d['id'] for d in docs]}, 'status': 'accepted'}, {'_id': 0, 'channel': 1}).to_list(5)
    return {'message': f"Password {row['name']} dikembalikan ke default.", 'default_password': DEFAULT_CLIENT_PASSWORD, 'channels': sorted({d['channel'] for d in sent})}
