"""Transactional email langsung via Gmail API (Google Cloud) dengan template milik server."""
import os
import re
import time
import base64
import ipaddress
import httpx
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html.parser import HTMLParser
from urllib.parse import urlparse
from notification_config import enabled, missing, app_url

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)
GMAIL_KEYS = ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN', 'GMAIL_SENDER']
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
_token = {'value': '', 'exp': 0.0}


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


def email_configuration_error():
    if not enabled('EMAIL_ENABLED'):
        return 'Email belum diaktifkan pada server (EMAIL_ENABLED=false).'
    absent = missing(GMAIL_KEYS + ['APP_URL'])
    if absent:
        return 'Konfigurasi Gmail API belum lengkap: ' + ', '.join(absent) + '.'
    if '@' not in os.environ['GMAIL_SENDER']:
        return 'GMAIL_SENDER harus alamat Gmail pengirim, misalnya cvmaiharta@gmail.com.'
    try:
        app_url()
    except ValueError as error:
        return str(error)
    return ''


def email_configured():
    return not email_configuration_error()


async def send_email(to, subject, html, notification_id, text=''):
    problem = email_configuration_error()
    if problem:
        raise ValueError(problem)
    _assert_safe_email(subject, html)
    return await send_email_gmail(to, subject, html, notification_id, text)


async def _access_token(client):
    if _token['value'] and _token['exp'] > time.time() + 60:
        return _token['value']
    r = await client.post(TOKEN_URL, data={'client_id': os.environ['GMAIL_CLIENT_ID'].strip(), 'client_secret': os.environ['GMAIL_CLIENT_SECRET'].strip(),
                                           'refresh_token': os.environ['GMAIL_REFRESH_TOKEN'].strip(), 'grant_type': 'refresh_token'})
    if r.status_code != 200:
        err = (r.json() if r.headers.get('content-type', '').startswith('application/json') else {}).get('error', f'HTTP {r.status_code}')
        raise ValueError(f'Google menolak refresh token ({err}). Buat ulang GMAIL_REFRESH_TOKEN sesuai panduan.')
    body = r.json()
    _token.update(value=body['access_token'], exp=time.time() + int(body.get('expires_in', 3600)))
    return _token['value']


def _mime(to, subject, html, notification_id, text):
    sender = os.environ['GMAIL_SENDER'].strip()
    msg = EmailMessage()
    msg['From'] = formataddr((os.environ.get('MAIL_SENDER_NAME', '').strip() or 'CRM Maiharta', sender))
    msg['To'] = to
    msg['Subject'] = subject
    msg['Message-ID'] = make_msgid(domain=sender.split('@')[-1])
    msg['X-CRM-Notification-ID'] = notification_id
    msg['List-Unsubscribe'] = f"<{app_url()}/settings>"
    msg.set_content(text or 'Buka email ini dengan aplikasi yang mendukung HTML.')
    msg.add_alternative(html, subtype='html')
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def send_email_gmail(to, subject, html, notification_id, text=''):
    """Kirim langsung ke Gmail API (HTTPS) memakai OAuth refresh token akun Gmail pengirim."""
    raw = _mime(to, subject, html, notification_id, text)
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for _ in range(2):
            token = await _access_token(client)
            response = await client.post(SEND_URL, json={'raw': raw}, headers={'Authorization': f'Bearer {token}'})
            if response.status_code != 401: break
            _token.update(value='', exp=0)
    if response.status_code >= 400:
        try: detail = response.json().get('error', {}).get('message', '')
        except ValueError: detail = ''
        if detail: raise ValueError(f'Gmail API menolak (HTTP {response.status_code}): {detail[:200]}')
    response.raise_for_status()
    provider_id = (response.json() or {}).get('id')
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError('Gmail tidak mengembalikan ID pesan.')
    return provider_id
