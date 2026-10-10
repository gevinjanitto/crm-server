"""Transactional email via n8n (Gmail API) using fixed server-owned templates."""
import os
import re
import ipaddress
import httpx
from html.parser import HTMLParser
from urllib.parse import urlparse
from notification_config import enabled, missing, app_url, https_url

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


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
    absent = missing(['N8N_EMAIL_WEBHOOK_URL', 'N8N_WAHA_WEBHOOK_SECRET', 'APP_URL'])
    if absent:
        return 'Konfigurasi belum lengkap: ' + ', '.join(absent) + '.'
    url = os.environ['N8N_EMAIL_WEBHOOK_URL'].strip()
    if not https_url(url) or not urlparse(url).path.startswith('/webhook/'):
        return 'N8N_EMAIL_WEBHOOK_URL harus URL HTTPS produksi n8n /webhook/, bukan /webhook-test/.'
    if len(os.environ['N8N_WAHA_WEBHOOK_SECRET']) < 32:
        return 'Secret webhook n8n minimal 32 karakter.'
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
    return await send_email_n8n(to, subject, html, notification_id, text)


async def send_email_n8n(to, subject, html, notification_id, text=''):
    """Gmail via n8n (Gmail API lewat HTTPS, aman untuk Railway Hobby yang memblokir SMTP)."""
    payload = {'notification_id': notification_id, 'to': to, 'subject': subject, 'html': html, 'text': text,
               'unsubscribe_url': app_url() + '/settings',
               'sender_name': os.environ.get('MAIL_SENDER_NAME', '').strip() or 'CRM Maiharta'}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.post(os.environ['N8N_EMAIL_WEBHOOK_URL'].strip(), json=payload,
                                     headers={'X-CRM-Webhook-Secret': os.environ['N8N_WAHA_WEBHOOK_SECRET']})
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get('ok') is not True or body.get('status') != 'accepted':
        raise ValueError('Workflow n8n belum mengonfirmasi pengiriman Gmail.')
    if body.get('notification_id') != notification_id:
        raise ValueError('ID konfirmasi n8n tidak sesuai.')
    provider_id = body.get('message_id')
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError('Gmail tidak mengembalikan ID pesan.')
    return provider_id
