"""Kirim notifikasi akun ke WhatsApp lewat Twilio Messages API (Sandbox atau nomor WhatsApp Business)."""
import os
import re
import json
import httpx
from notification_config import enabled, missing, app_url

TWILIO_API = 'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
SANDBOX_NUMBER = 'whatsapp:+14155238886'
TEMPLATE_ERRORS = {21654, 21655, 63016, 63027}
_ACCOUNT_TYPE = {}


def _sender():
    value = os.environ.get('TWILIO_WHATSAPP_FROM', '').strip().replace(' ', '')
    return value if value.startswith('whatsapp:') else 'whatsapp:' + value


def sandbox_mode():
    """Akun Twilio Trial/Sandbox. TWILIO_WHATSAPP_SANDBOX=true/false, kosong = otomatis (nomor Sandbox atau akun bertipe Trial)."""
    flag = os.environ.get('TWILIO_WHATSAPP_SANDBOX', '').strip().lower()
    if flag in ('1', 'true', 'yes', 'on'):
        return True
    if flag in ('0', 'false', 'no', 'off'):
        return False
    return _sender() == SANDBOX_NUMBER or _ACCOUNT_TYPE.get(os.environ.get('TWILIO_ACCOUNT_SID', '').strip()) == 'Trial'


def trial_content_sid():
    return os.environ.get('TWILIO_CONTENT_SID', '').strip()


async def detect_trial():
    """Baca tipe akun Twilio (Trial/Full) sekali lalu disimpan."""
    sid = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
    if not sid or sid in _ACCOUNT_TYPE or whatsapp_configuration_error():
        return _ACCOUNT_TYPE.get(sid) == 'Trial'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f'https://api.twilio.com/2010-04-01/Accounts/{sid}.json', auth=_auth())
        if response.status_code == 200:
            _ACCOUNT_TYPE[sid] = response.json().get('type') or ''
    except (httpx.HTTPError, ValueError):
        pass
    return _ACCOUNT_TYPE.get(sid) == 'Trial'


def _auth():
    key_sid = os.environ.get('TWILIO_API_KEY_SID', '').strip()
    if key_sid:
        return key_sid, os.environ.get('TWILIO_API_KEY_SECRET', '').strip()
    return os.environ['TWILIO_ACCOUNT_SID'].strip(), os.environ.get('TWILIO_AUTH_TOKEN', '').strip()


def whatsapp_configuration_error():
    if not enabled('WHATSAPP_ENABLED'):
        return 'WhatsApp belum diaktifkan pada server (WHATSAPP_ENABLED=false).'
    absent = missing(['TWILIO_ACCOUNT_SID', 'TWILIO_WHATSAPP_FROM', 'APP_URL'])
    if os.environ.get('TWILIO_API_KEY_SID', '').strip():
        absent += missing(['TWILIO_API_KEY_SECRET'])
    else:
        absent += missing(['TWILIO_AUTH_TOKEN'])
    if absent:
        return 'Konfigurasi Twilio WhatsApp belum lengkap: ' + ', '.join(absent) + '.'
    if not re.fullmatch(r'AC[0-9a-fA-F]{32}', os.environ['TWILIO_ACCOUNT_SID'].strip()):
        return 'TWILIO_ACCOUNT_SID harus diawali AC (lihat Twilio Console → Account Info).'
    if not re.fullmatch(r'whatsapp:\+[1-9][0-9]{7,14}', _sender()):
        return 'TWILIO_WHATSAPP_FROM harus berformat whatsapp:+14155238886 (nomor Sandbox atau nomor WhatsApp Twilio Anda).'
    sid = os.environ.get('TWILIO_CONTENT_SID', '').strip()
    if sid and not re.fullmatch(r'HX[0-9a-fA-F]{32}', sid):
        return 'TWILIO_CONTENT_SID harus diawali HX (Content Template Builder / halaman Try out WhatsApp) atau dikosongkan.'
    try:
        json.loads(os.environ.get('TWILIO_CONTENT_VARIABLES', '').strip() or '{}')
    except ValueError:
        return 'TWILIO_CONTENT_VARIABLES harus berupa JSON, misalnya {"1":"12/1","2":"3pm"}, atau dikosongkan.'
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


def _content(message, content_sid='', variables=None):
    if sandbox_mode():
        # Trial: hanya template bawaan Twilio (ContentSid dari halaman Try out WhatsApp); tanpa ContentSid = teks biasa (Sandbox lama).
        sid = trial_content_sid()
        if not sid:
            return {'Body': message[:1600]}
        form = {'ContentSid': sid}
        variables = os.environ.get('TWILIO_CONTENT_VARIABLES', '').strip()
        if variables:
            form['ContentVariables'] = variables
        return form
    if content_sid and variables:
        return {'ContentSid': content_sid, 'ContentVariables': json.dumps(variables, ensure_ascii=False)}
    sid = os.environ.get('TWILIO_CONTENT_SID', '').strip()
    if not sid:
        return {'Body': message[:1600]}
    flat = re.sub(r'\s*\n+\s*', ' · ', message).replace('\t', ' ')
    return {'ContentSid': sid, 'ContentVariables': json.dumps({'1': re.sub(r' {4,}', '   ', flat)[:1000]}, ensure_ascii=False)}


FRIENDLY_ERRORS = {
    21654: 'Template WhatsApp belum terdaftar/disetujui di Twilio. Buka Pengaturan → Notifikasi akun → Template WhatsApp, tekan "Sinkronkan ke Twilio", lalu tunggu status Disetujui.',
    63016: 'Di luar jendela 24 jam WhatsApp: pesan wajib memakai template yang sudah disetujui. Sinkronkan template di Pengaturan → Notifikasi akun dan tunggu status Disetujui.',
    63015: 'Nomor penerima belum join Twilio Sandbox. Kirim "join <kode-sandbox>" dari WhatsApp penerima ke nomor Sandbox, lalu coba lagi.',
    63027: 'Template WhatsApp tidak ditemukan atau belum disetujui WhatsApp. Periksa status template di Pengaturan → Notifikasi akun.',
    63112: 'Akun WhatsApp Business ditangguhkan Meta. Periksa status akun di Twilio Console.',
    21608: 'Nomor tujuan belum diverifikasi pada akun Twilio Trial.',
    21211: 'Nomor WhatsApp tujuan tidak valid.',
}


def _error_code(response):
    try:
        return response.json().get('code')
    except ValueError:
        return None


def _twilio_error(response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    code, text = body.get('code'), str(body.get('message') or '')[:200]
    if not code:
        return ''
    raw = f'Twilio: HTTP {response.status_code}, kode {code} – {text}'
    if sandbox_mode() and code in TEMPLATE_ERRORS:
        if not trial_content_sid():
            return ('Akun Twilio Trial wajib memakai template bawaan Twilio. Buka Twilio Console → Try it out → Send a WhatsApp message, '
                    'salin nilai ContentSid (HX...) ke TWILIO_CONTENT_SID (dan ContentVariables, bila ada, ke TWILIO_CONTENT_VARIABLES) '
                    f'di backend/.env, lalu restart backend.\n{raw}')
        return ('TWILIO_CONTENT_SID bukan template bawaan Trial atau ContentVariables tidak cocok. Salin ulang ContentSid & ContentVariables '
                f'persis dari halaman Try out WhatsApp.\n{raw}')
    if sandbox_mode() and code in (63015, 21608):
        return ('Akun Trial: nomor penerima harus sudah diverifikasi dan join. Di halaman Try out WhatsApp, verifikasi nomor penerima '
                f'lalu kirim pesan join dari WhatsApp penerima ke {_sender()[9:]}.\n{raw}')
    friendly = FRIENDLY_ERRORS.get(code) or (FRIENDLY_ERRORS[63015] if 'sandbox' in text.lower() else 'Twilio menolak pesan.')
    return f'{friendly}\n{raw}'


async def send_whatsapp(phone, notification_id, recipient_id, project_id='', text='', content_sid='', variables=None):
    problem = whatsapp_configuration_error()
    if problem:
        raise ValueError(problem)
    number = normalize_phone(phone)
    if not number:
        raise ValueError('Nomor WhatsApp belum terdaftar.')
    await detect_trial()
    message = text or ('CRM Maiharta memiliki pembaruan untuk akun atau pekerjaan Anda. '
                       f'Buka {app_url()}/notifications untuk melihat detailnya.')
    form = {'From': _sender(), 'To': 'whatsapp:' + number, **_content(message, content_sid, variables)}
    callback = os.environ.get('TWILIO_STATUS_CALLBACK', '').strip()
    if callback:
        form['StatusCallback'] = callback
    url = TWILIO_API.format(sid=os.environ['TWILIO_ACCOUNT_SID'].strip())
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        response = await client.post(url, data=form, auth=_auth(), headers={'Accept': 'application/json'})
        if response.status_code >= 400 and not sandbox_mode() and 'ContentSid' in form and _error_code(response) in TEMPLATE_ERRORS:
            # Template belum siap: coba sekali lagi sebagai teks biasa (berlaku di Sandbox / jendela 24 jam).
            form = {k: v for k, v in form.items() if k not in ('ContentSid', 'ContentVariables')}
            form['Body'] = message[:1600]
            response = await client.post(url, data=form, auth=_auth(), headers={'Accept': 'application/json'})
    if response.status_code >= 400:
        reason = _twilio_error(response)
        if reason:
            raise ValueError(reason)
    response.raise_for_status()
    body = response.json()
    if body.get('status') in ('failed', 'undelivered'):
        raise ValueError(f"Twilio menolak pesan: {str(body.get('error_message') or body.get('status'))[:200]}")
    return str(body.get('sid') or f'wa-{notification_id}')
