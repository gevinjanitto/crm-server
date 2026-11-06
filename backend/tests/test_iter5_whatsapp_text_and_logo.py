"""Iteration 5 backend verification: whatsapp_text content, email_html uses logo-mark-white.png, asset served."""
import os
import re
import sys
import requests

sys.path.insert(0, '/app/backend')
from email_template import whatsapp_text, email_html  # noqa: E402

def _read_frontend_env():
    for line in open('/app/frontend/.env'):
        if line.startswith('REACT_APP_BACKEND_URL='):
            return line.split('=', 1)[1].strip()
    raise RuntimeError('REACT_APP_BACKEND_URL missing')


BASE = os.environ.get('REACT_APP_BACKEND_URL') or _read_frontend_env()
BASE = BASE.rstrip('/')
FRONTEND = BASE  # ingress serves /assets from frontend


NOTIF = {
    'id': 'n1',
    'kind': 'penugasan',
    'title': 'Anda ditugaskan: Perbaikan modul billing',
    'message': 'Silakan periksa detail penugasan dan tenggat waktunya.',
    'actor_name': 'Admin',
    'created_at': '2026-01-15T10:30:00+00:00',
    'link': '/tasks/abc',
    'project_id': 'p1',
}
USER = {'id': 'u1', 'name': 'Budi', 'email': 'budi@example.com'}


# whatsapp_text structure
def test_whatsapp_text_header_and_kind():
    text = whatsapp_text(NOTIF, USER, 'Project Alpha')
    assert text.startswith('*CRM Maiharta* | Penugasan'), text[:80]


def test_whatsapp_text_greeting_and_title_message():
    text = whatsapp_text(NOTIF, USER, 'Project Alpha')
    assert 'Halo Budi,' in text
    assert '*Anda ditugaskan: Perbaikan modul billing*' in text
    assert 'Silakan periksa detail penugasan dan tenggat waktunya.' in text


def test_whatsapp_text_details_lines():
    text = whatsapp_text(NOTIF, USER, 'Project Alpha')
    assert 'Project: *Project Alpha*' in text
    assert 'Oleh: *Admin*' in text
    assert re.search(r'Waktu: \*\d{2}/\d{2}/\d{4} \d{2}:\d{2} WITA\*', text), text


def test_whatsapp_text_link_and_settings():
    text = whatsapp_text(NOTIF, USER, 'Project Alpha')
    assert 'Lihat di CRM:' in text
    app_url = os.environ.get('APP_URL', '').rstrip('/')
    if app_url:
        assert (app_url + '/tasks/abc') in text
        assert (app_url + '/settings') in text


def test_whatsapp_text_length_cap():
    big = dict(NOTIF, message='x' * 10000)
    assert len(whatsapp_text(big, USER, 'P')) <= 3900


def test_whatsapp_text_kind_fallback():
    text = whatsapp_text(dict(NOTIF, kind='weird_kind'), USER, '')
    assert '| Weird_kind' in text


# email_html uses white logo (no white background)
def test_email_html_uses_white_logo_mark():
    html = email_html(NOTIF, USER, 'Project Alpha')
    assert '/assets/logo-mark-white.png' in html
    assert '/assets/logo-mark.png' not in html.replace('logo-mark-white.png', '')


# asset is served
def test_logo_mark_white_served():
    r = requests.get(f'{FRONTEND}/assets/logo-mark-white.png', timeout=15)
    assert r.status_code == 200, r.status_code
    assert r.headers.get('content-type', '').startswith('image/'), r.headers.get('content-type')
    assert len(r.content) > 500


def test_barong_id_asset_served():
    r = requests.get(f'{FRONTEND}/assets/barong-id.webp', timeout=15)
    assert r.status_code == 200
    assert 'image' in r.headers.get('content-type', '')


# whatsapp.send_whatsapp forwards text argument
def test_send_whatsapp_signature_accepts_text():
    import inspect
    from whatsapp import send_whatsapp
    sig = inspect.signature(send_whatsapp)
    assert 'text' in sig.parameters


# notification_delivery passes whatsapp_text to send_whatsapp
def test_notification_delivery_uses_whatsapp_text():
    import notification_delivery
    src = open(notification_delivery.__file__).read()
    assert 'whatsapp_text(' in src
    assert 'send_whatsapp(' in src
