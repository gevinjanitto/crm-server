"""Salin template WhatsApp aplikasi ke Twilio Content API dan ajukan persetujuan WhatsApp."""
import re
from datetime import datetime, timezone
import httpx
from email_template import KIND_LABELS, _details, _cta, _link
from whatsapp import _auth

CONTENT_API = 'https://content.twilio.com/v1/Content'
SETTING_ID = 'whatsapp_template'
# Struktur sama dengan whatsapp_text(); hanya isi dinamis menjadi variabel {{n}} di sisi Twilio.
TEMPLATE_BODY = ('*CRM Maiharta* | {{1}}\n\nHalo {{2}},\n\n*{{3}}*\n{{4}}\n\n{{5}}\n\n{{6}}\n\n'
                 '_Pesan otomatis CRM Maiharta. Atur notifikasi di menu Pengaturan._')
SAMPLES = {'1': 'Penugasan', '2': 'Budi', '3': 'Tugas baru untuk Anda', '4': 'Anda ditugaskan pada pekerjaan Desain Landing Page.',
           '5': 'Project: Website Maiharta · Oleh: Admin · Waktu: 01/06/2026 09:00 WITA', '6': 'Lihat di CRM: https://crm.example.com/notifications'}
STATUS_LABELS = {'approved': 'Disetujui', 'pending': 'Menunggu persetujuan', 'received': 'Menunggu persetujuan',
                 'rejected': 'Ditolak', 'paused': 'Dijeda WhatsApp', 'disabled': 'Dinonaktifkan WhatsApp', 'unsubmitted': 'Belum diajukan'}


def _flat(value, limit=900):
    text = re.sub(r'\s*\n+\s*', ' · ', str(value or '')).replace('\t', ' ')
    return re.sub(r' {4,}', '   ', text).strip()[:limit] or '-'


def template_variables(notification, user, project_name=''):
    kind = KIND_LABELS.get(notification.get('kind', ''), (notification.get('kind') or 'Info').capitalize())
    details = ' · '.join(f'{k}: {v}' for k, v in _details(notification, project_name))
    return {'1': _flat(kind), '2': _flat(user.get('name')), '3': _flat(notification.get('title') or 'Pembaruan pekerjaan'),
            '4': _flat(notification.get('whatsapp_message') or notification.get('message')), '5': _flat(details),
            '6': _flat(f'{_cta(notification)}: {_link(notification)}')}


async def _twilio(method, url, json=None):
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.request(method, url, json=json, auth=_auth(), headers={'Accept': 'application/json'})
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        raise ValueError(f"Twilio Content API menolak (HTTP {response.status_code}, kode {body.get('code')}): {str(body.get('message') or '')[:200]}")
    return body


async def create_and_submit():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    name = f'crm_maiharta_notifikasi_{stamp}'
    content = await _twilio('POST', CONTENT_API, {'friendly_name': name, 'language': 'id', 'variables': SAMPLES,
                                                  'types': {'twilio/text': {'body': TEMPLATE_BODY}}})
    sid = content['sid']
    approval = await _twilio('POST', f'{CONTENT_API}/{sid}/ApprovalRequests/whatsapp', {'name': name, 'category': 'UTILITY'})
    return {'content_sid': sid, 'name': name, 'status': approval.get('status') or 'received',
            'rejection_reason': approval.get('rejection_reason') or '', 'body': TEMPLATE_BODY}


async def approval_status(sid):
    body = await _twilio('GET', f'{CONTENT_API}/{sid}/ApprovalRequests')
    wa = body.get('whatsapp') or {}
    return {'status': wa.get('status') or 'unsubmitted', 'rejection_reason': wa.get('rejection_reason') or ''}
