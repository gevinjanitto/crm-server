from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
from core import db, now, log_activity
from auth import current_user
from mailer import email_configured, email_configuration_error
from whatsapp import whatsapp_configured, whatsapp_configuration_error, normalize_phone

router = APIRouter(prefix='/account/notifications')
DEFAULT_PREFERENCES = {'in_app': True, 'email': True, 'whatsapp': False}


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    in_app: bool = True
    email: bool = True
    whatsapp: bool = False
    whatsapp_number: str = Field(default='', max_length=30)

    @model_validator(mode='after')
    def validate_phone(self):
        self.whatsapp_number = normalize_phone(self.whatsapp_number)
        if self.whatsapp and not self.whatsapp_number: raise ValueError('Isi nomor WhatsApp sebelum mengaktifkan notifikasi.')
        return self


class PreferencesResponse(NotificationPreferences):
    registered_email: str
    email_configured: bool
    whatsapp_configured: bool
    email_provider: str = 'Gmail via n8n'
    whatsapp_provider: str = 'n8n + WAHA'
    email_configuration_note: str = ''
    whatsapp_configuration_note: str = ''


def public_settings(user):
    return {**DEFAULT_PREFERENCES, **user.get('notification_preferences', {}), 'whatsapp_number': user.get('whatsapp_number', ''), 'registered_email': user.get('email', ''), 'email_configured': email_configured(), 'whatsapp_configured': whatsapp_configured(), 'email_configuration_note': email_configuration_error(), 'whatsapp_configuration_note': whatsapp_configuration_error()}


@router.get('', response_model=PreferencesResponse)
async def get_preferences(u=Depends(current_user)):
    return public_settings(u)


@router.patch('', response_model=PreferencesResponse)
async def save_preferences(data: NotificationPreferences, u=Depends(current_user)):
    updates = {'notification_preferences': data.model_dump(exclude={'whatsapp_number'}), 'whatsapp_number': data.whatsapp_number}
    if data.whatsapp and (not u.get('notification_preferences', {}).get('whatsapp') or u.get('whatsapp_number') != data.whatsapp_number):
        updates.update(whatsapp_opt_in_at=now(), whatsapp_opt_in_source='account_settings')
    if not data.whatsapp: updates['whatsapp_opt_out_at'] = now()
    await db.users.update_one({'id': u['id']}, {'$set': updates})
    await log_activity(u, 'ubah preferensi', 'notifikasi', u['id'], '', details=data.model_dump(exclude={'whatsapp_number'}))
    return public_settings({**u, **updates})


class DeliveryResponse(BaseModel):
    id: str
    channel: str
    status: str
    created_at: str
    reason: str = ''


@router.get('/deliveries', response_model=list[DeliveryResponse])
async def deliveries(u=Depends(current_user)):
    return await db.notification_deliveries.find({'user_id': u['id']}, {'_id': 0}).sort('created_at', -1).to_list(20)


@router.post('/test')
async def test_notification(u=Depends(current_user)):
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    result = await db.users.update_one({'id': u['id'], '$or': [{'notification_test_at': {'$exists': False}}, {'notification_test_at': {'$lt': cutoff}}]}, {'$set': {'notification_test_at': now()}})
    if not result.modified_count: raise HTTPException(429, 'Tunggu satu menit sebelum mengirim uji berikutnya.')
    from notify import notify
    docs = await notify([u['id']], 'Uji notifikasi', 'Pengaturan notifikasi akun Anda telah diuji.', 'akun', '/settings', entity_type='akun', entity_id=u['id'], wait_for_delivery=True)
    query = {'notification_id': {'$in': [doc['id'] for doc in docs]}, 'user_id': u['id']}
    accepted = await db.notification_deliveries.count_documents({**query, 'status': 'accepted'})
    skipped = await db.notification_deliveries.count_documents({**query, 'status': 'skipped'})
    failed = await db.notification_deliveries.count_documents({**query, 'status': {'$in': ['failed', 'unknown']}})
    return {'message': f'Uji selesai: {accepted} diterima layanan, {skipped} tidak dikirim, {failed} gagal/perlu diperiksa.'}

@router.get('/daily-stats')
async def daily_stats(u=Depends(current_user)):
    if u['role'] != 'Admin': raise HTTPException(403, 'Hanya Admin.')
    midnight = datetime.now(ZoneInfo('Asia/Makassar')).replace(hour=0, minute=0, second=0, microsecond=0)
    since = midnight.astimezone(timezone.utc).isoformat()
    counts = {'email': 0, 'whatsapp': 0}
    async for row in db.notification_deliveries.aggregate([{'$match': {'status': 'accepted', 'created_at': {'$gte': since}}}, {'$group': {'_id': '$channel', 'n': {'$sum': 1}}}]):
        counts[row['_id']] = row['n']
    return {**counts, 'email_daily_limit': 500, 'since': midnight.isoformat()}
