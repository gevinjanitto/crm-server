"""Send authorized account notifications to an authenticated n8n → WAHA workflow."""
import os
import re
from urllib.parse import urlparse
import httpx
from notification_config import enabled, missing, https_url, app_url


def whatsapp_configuration_error():
    if not enabled('WHATSAPP_ENABLED'):
        return 'WhatsApp belum diaktifkan pada server (WHATSAPP_ENABLED=false).'
    absent = missing(['N8N_WAHA_WEBHOOK_URL', 'N8N_WAHA_WEBHOOK_SECRET', 'APP_URL'])
    if absent:
        return 'Konfigurasi belum lengkap: ' + ', '.join(absent) + '.'
    url = os.environ['N8N_WAHA_WEBHOOK_URL'].strip()
    if not https_url(url) or not urlparse(url).path.startswith('/webhook/'):
        return 'Gunakan URL HTTPS produksi n8n /webhook/, bukan /webhook-test/.'
    if len(os.environ['N8N_WAHA_WEBHOOK_SECRET']) < 32:
        return 'Secret webhook n8n minimal 32 karakter.'
    try:
        app_url()
    except ValueError as error:
        return str(error)
    return ''


def whatsapp_configured():
    return not whatsapp_configuration_error()


def normalize_phone(value):
    number = re.sub(r'[\s().-]', '', value or '')
    if number.startswith('08'):
        number = '+62' + number[1:]
    elif number.startswith('62'):
        number = '+' + number
    if number and not re.fullmatch(r'\+[1-9][0-9]{7,14}', number):
        raise ValueError('Nomor WhatsApp harus berformat internasional, misalnya +628123456789.')
    return number


async def send_whatsapp(phone, notification_id, recipient_id, project_id='', text=''):
    problem = whatsapp_configuration_error()
    if problem:
        raise ValueError(problem)
    number = normalize_phone(phone)
    if not number:
        raise ValueError('Nomor WhatsApp belum terdaftar.')
    payload = {
        'notification_id': notification_id, 'recipient_id': recipient_id,
        'project_id': project_id, 'phone_e164': number,
        'text': text or ('CRM Maiharta memiliki pembaruan untuk akun atau pekerjaan Anda. '
                         f'Buka {app_url()}/notifications untuk melihat detailnya.'),
    }
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        response = await client.post(os.environ['N8N_WAHA_WEBHOOK_URL'].strip(), json=payload,
                                     headers={'X-CRM-Webhook-Secret': os.environ['N8N_WAHA_WEBHOOK_SECRET']})
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get('ok') is not True or body.get('status') != 'accepted':
        raise ValueError('Workflow n8n belum mengonfirmasi penerimaan oleh WAHA.')
    if body.get('notification_id') != notification_id:
        raise ValueError('ID konfirmasi n8n tidak sesuai.')
    provider_id = body.get('message_id')
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError('WAHA tidak mengembalikan ID pesan.')
    return provider_id