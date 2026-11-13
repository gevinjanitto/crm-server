"""Laporan pesan WhatsApp langsung dari Twilio Messages API + kirim ulang manual."""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core import db, uid, now, authorize, log_activity
from auth import current_user
from whatsapp import send_whatsapp, whatsapp_configuration_error, _auth, _sender
from whatsapp_template import SETTING_ID as WA_TEMPLATE_ID, template_variables, approval_status
from email_template import whatsapp_text
from notification_delivery import approved_template_sid, project_title

router = APIRouter(prefix='/admin/whatsapp-report')
API_ROOT = 'https://api.twilio.com'
FAILED = {'failed', 'undelivered'}
ERROR_HELP = {
    63049: 'Meta tidak mengirim pesan karena template dikategorikan MARKETING dan penerima sudah mencapai batas pesan marketing dari bisnis. Pastikan template berkategori UTILITY (sinkronkan ulang template), lalu kirim ulang.',
    63016: 'Di luar jendela 24 jam: wajib memakai template WhatsApp yang sudah disetujui.',
    63024: 'Nomor penerima tidak valid / tidak memakai WhatsApp.',
    63003: 'Nomor penerima tidak dapat dijangkau WhatsApp.',
    63032: 'Penerima memblokir atau berhenti berlangganan pesan dari bisnis ini.',
    63018: 'Batas kecepatan pengiriman WhatsApp terlampaui. Kirim ulang beberapa saat lagi.',
    63038: 'Batas harian pesan akun WhatsApp Business tercapai.',
    63015: 'Nomor penerima belum join Twilio Sandbox.',
    30008: 'Kesalahan tidak diketahui dari operator/WhatsApp. Coba kirim ulang.',
}


class ResendInput(BaseModel):
    message_sid: str = ''
    delivery_id: str = ''


async def _twilio_get(path, params=None):
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(API_ROOT + path, params=params, auth=_auth(), headers={'Accept': 'application/json'})
    except httpx.HTTPError as e:
        raise HTTPException(502, f'Tidak dapat menghubungi Twilio ({type(e).__name__}).')
    if r.status_code >= 400:
        raise HTTPException(502, f'Twilio menolak permintaan (HTTP {r.status_code}).')
    return r.json()


def _row(m, delivery, users, resent):
    code = int(m['error_code']) if m.get('error_code') else 0
    user = users.get((delivery or {}).get('user_id'), {})
    return {'sid': m['sid'], 'date': m.get('date_created'), 'from': m.get('from'), 'to': m.get('to'), 'status': m.get('status'),
            'error_code': code, 'error_message': m.get('error_message') or '', 'error_help': ERROR_HELP.get(code, ''),
            'body': (m.get('body') or '')[:500], 'recipient_name': user.get('name', ''),
            'notification_title': ((delivery or {}).get('notification') or {}).get('title', ''),
            'resent_sid': resent.get(m['sid'], ''), 'can_resend': m.get('status') in FAILED}


async def _template_category():
    row = await db.app_settings.find_one({'id': WA_TEMPLATE_ID}, {'_id': 0}) or {}
    if not row.get('content_sid'): return ''
    try: return (await approval_status(row['content_sid'])).get('category', '')
    except ValueError: return ''


@router.get('')
async def report(status: str = '', page_uri: str = '', u=Depends(current_user)):
    await authorize(u, 'user.manage')
    problem = whatsapp_configuration_error()
    if problem: return {'configuration_note': problem, 'messages': [], 'next_page': '', 'template_category': '', 'crm_failures': await _crm_failures()}
    sid = os.environ['TWILIO_ACCOUNT_SID'].strip()
    base = f'/2010-04-01/Accounts/{sid}/Messages.json'
    if page_uri and not page_uri.startswith(base): raise HTTPException(400, 'Halaman tidak valid.')
    data = await _twilio_get(page_uri) if page_uri else await _twilio_get(base, {'From': _sender(), 'PageSize': 100})
    msgs = data.get('messages') or []
    if status == 'failed': msgs = [m for m in msgs if m.get('status') in FAILED]
    sids = [m['sid'] for m in msgs]
    deliveries = {d['provider_id']: d for d in await db.notification_deliveries.find({'provider_id': {'$in': sids}}, {'_id': 0}).to_list(500)} if sids else {}
    uids = list({d['user_id'] for d in deliveries.values()})
    users = {x['id']: x for x in await db.users.find({'id': {'$in': uids}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(500)} if uids else {}
    resent = {r['original_sid']: r['new_sid'] for r in await db.whatsapp_resends.find({'original_sid': {'$in': sids}}, {'_id': 0}).to_list(500)} if sids else {}
    return {'configuration_note': '', 'messages': [_row(m, deliveries.get(m['sid']), users, resent) for m in msgs],
            'next_page': data.get('next_page_uri') or '', 'template_category': await _template_category(), 'crm_failures': await _crm_failures()}


async def _crm_failures():
    rows = await db.notification_deliveries.find({'channel': 'whatsapp', 'status': 'failed'}, {'_id': 0}).sort('created_at', -1).to_list(100)
    rows = [r for r in rows if not r.get('resent_at')]
    uids = list({r['user_id'] for r in rows})
    users = {x['id']: x for x in await db.users.find({'id': {'$in': uids}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(500)} if uids else {}
    return [{'id': r['id'], 'date': r.get('created_at'), 'recipient_name': users.get(r['user_id'], {}).get('name', ''), 'reason': r.get('reason', ''),
             'notification_title': (r.get('notification') or {}).get('title', '')} for r in rows]


async def _notification_for(delivery):
    return delivery.get('notification') or await db.notifications.find_one({'id': delivery['notification_id']}, {'_id': 0})


async def _resend_notification(delivery):
    notification = await _notification_for(delivery)
    user = await db.users.find_one({'id': delivery['user_id'], 'active': True}, {'_id': 0})
    if not notification or not user: return None
    if not user.get('whatsapp_number'): raise HTTPException(400, 'Nomor WhatsApp penerima belum terdaftar.')
    name = await project_title(notification.get('project_id'))
    sid = await approved_template_sid()
    variables = template_variables(notification, user, name) if sid else None
    new_sid = await send_whatsapp(user['whatsapp_number'], notification['id'], user['id'], notification.get('project_id', ''), whatsapp_text(notification, user, name), sid, variables)
    await db.notification_deliveries.insert_one({'id': uid(), 'notification_id': notification['id'], 'user_id': user['id'], 'channel': 'whatsapp', 'provider': 'whatsapp_api',
                                                 'status': 'accepted', 'provider_id': new_sid, 'created_at': now(), 'reason': '', 'notification': notification, 'resent_from': delivery['id']})
    return new_sid


@router.post('/resend')
async def resend(data: ResendInput, u=Depends(current_user)):
    await authorize(u, 'user.manage')
    problem = whatsapp_configuration_error()
    if problem: raise HTTPException(400, problem)
    query = {'provider_id': data.message_sid} if data.message_sid else {'id': data.delivery_id}
    if not data.message_sid and not data.delivery_id: raise HTTPException(400, 'Pesan tidak ditentukan.')
    delivery = await db.notification_deliveries.find_one({**query, 'channel': 'whatsapp'}, {'_id': 0})
    try:
        new_sid = await _resend_notification(delivery) if delivery else None
        if not new_sid:
            if not data.message_sid: raise HTTPException(404, 'Notifikasi asli tidak ditemukan.')
            sid = os.environ['TWILIO_ACCOUNT_SID'].strip()
            m = await _twilio_get(f'/2010-04-01/Accounts/{sid}/Messages/{data.message_sid}.json')
            new_sid = await send_whatsapp(m['to'].replace('whatsapp:', ''), data.message_sid, '', '', m.get('body') or '')
    except ValueError as e:
        raise HTTPException(502, str(e))
    if data.message_sid:
        await db.whatsapp_resends.insert_one({'id': uid(), 'original_sid': data.message_sid, 'new_sid': new_sid, 'by': u['name'], 'created_at': now()})
    if delivery: await db.notification_deliveries.update_one({'id': delivery['id']}, {'$set': {'resent_at': now(), 'resent_sid': new_sid}})
    await log_activity(u, 'kirim ulang', 'whatsapp', data.message_sid or data.delivery_id, '', details={'new_sid': new_sid})
    return {'message': 'Pesan WhatsApp dikirim ulang.', 'new_sid': new_sid}
