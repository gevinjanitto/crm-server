"""Iteration 32: welcome email credentials, client dashboard ticket_stats, admin alert on delivery failure."""
import os
import re
import sys
import asyncio
import pytest

# Single shared event loop for in-process async tests to avoid docstore pool
# leakage ("Event loop is closed") between asyncio.run() invocations.
_LOOP = asyncio.new_event_loop()

def _run(coro):
    return _LOOP.run_until_complete(coro)
import requests

def _read_backend_url():
    v = os.environ.get('REACT_APP_BACKEND_URL', '').strip()
    if v:
        return v.rstrip('/')
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL'):
                    return line.split('=', 1)[1].strip().strip('"').rstrip('/')
    except OSError:
        pass
    return ''

BASE_URL = _read_backend_url()
sys.path.insert(0, '/app/backend')


# ---------- HTTP helpers ----------
def _login(username, password='Maiharta2026!'):
    s = requests.Session()
    cap = s.get(f'{BASE_URL}/api/auth/captcha', timeout=10).json()
    # math captcha: parse question "a + b = ?"
    m = re.match(r'(\d+)\s*\+\s*(\d+)', cap['question'])
    answer = str(int(m.group(1)) + int(m.group(2)))
    r = s.post(f'{BASE_URL}/api/auth/login', json={
        'username': username, 'password': password,
        'captcha_id': cap['id'], 'captcha_answer': answer,
    }, timeout=10)
    assert r.status_code == 200, f'login {username} failed: {r.status_code} {r.text}'
    tok = r.json()['token']
    s.headers.update({'Authorization': f'Bearer {tok}'})
    return s


@pytest.fixture(scope='module')
def admin():
    return _login('admin')


@pytest.fixture(scope='module')
def client():
    return _login('client')


# ---------- Dashboard ticket_stats ----------
class TestDashboardTicketStats:
    def test_client_has_ticket_stats(self, client):
        r = client.get(f'{BASE_URL}/api/dashboard', timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert 'ticket_stats' in d
        ts = d['ticket_stats']
        for k in ('total', 'open', 'in_progress', 'closed', 'waiting_client', 'rejected'):
            assert k in ts, f'missing {k}'
            assert isinstance(ts[k], int)
        # Seed: client-1 has 3 tickets, verify total matches sum
        assert ts['total'] == ts['open'] + ts['in_progress'] + ts['closed']
        # Seed note says 3 tickets exist
        assert ts['total'] >= 1

    def test_admin_has_no_ticket_stats(self, admin):
        r = admin.get(f'{BASE_URL}/api/dashboard', timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert 'ticket_stats' not in d
        # Admin KPIs still present
        for k in ('total', 'active', 'completed', 'open_tickets'):
            assert k in d


# ---------- User creation (admin creates Developer) ----------
class TestAdminCreateUser:
    created_ids = []

    def test_create_user_returns_default_password(self, admin):
        import time
        suffix = f'TEST_{int(time.time())}'
        payload = {
            'username': suffix.lower(),
            'name': f'{suffix} Dev',
            'email': f'{suffix.lower()}@example.com',
            'role': 'Developer',
            'whatsapp_number': '',
        }
        r = admin.post(f'{BASE_URL}/api/users', json=payload, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data['default_password'] == '12345678'
        assert data['username'] == payload['username']
        assert data['role'] == 'Developer'
        TestAdminCreateUser.created_ids.append(data['id'])

    def test_create_client_entity_still_works(self, admin):
        import time
        tag = f'TEST_CLI_{int(time.time())}'
        payload = {'name': tag, 'contact': tag + ' Owner',
                   'email': f'{tag.lower()}@example.com', 'phone': '', 'address': ''}
        r = admin.post(f'{BASE_URL}/api/clients', json=payload, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['name'] == tag
        # Account auto-created with default password 12345678
        acct = body.get('account') or {}
        if acct.get('created'):
            assert acct['password'] == '12345678'
            # Track newly created client user for cleanup
            u = admin.get(f'{BASE_URL}/api/users', timeout=10).json()
            match = [x for x in u if x['username'] == acct['username']]
            if match:
                TestAdminCreateUser.created_ids.append(match[0]['id'])
        TestAdminCreateUser._client_id = body['id']

    def test_cleanup(self, admin):
        for uid_ in TestAdminCreateUser.created_ids:
            admin.delete(f'{BASE_URL}/api/users/{uid_}', timeout=10)
        cid = getattr(TestAdminCreateUser, '_client_id', None)
        if cid:
            admin.delete(f'{BASE_URL}/api/clients/{cid}', timeout=10)


# ---------- In-process email template + delivery alerts ----------
class TestEmailTemplate:
    def test_credentials_in_html_and_text(self):
        from email_template import email_html, email_text
        notif = {'id': 'n1', 'kind': 'sambutan', 'title': 'Selamat datang', 'message': 'Isi pesan',
                 'credentials': [('Username', 'u'), ('Password awal', '12345678')],
                 'link': '/', 'created_at': '2026-01-01T00:00:00+00:00', 'actor_name': 'Admin'}
        user = {'name': 'Pengguna'}
        html = email_html(notif, user)
        text = email_text(notif, user)
        assert 'Username' in html and '>u<' in html
        assert 'Password awal' in html and '12345678' in html
        assert 'Username: u' in text
        assert 'Password awal: 12345678' in text

    def test_assert_safe_email_passes(self):
        os.environ.setdefault('APP_URL', 'https://crm.example.com')
        from email_template import email_html, email_subject
        from mailer import _assert_safe_email
        notif = {'id': 'n1', 'kind': 'sambutan', 'title': 'Selamat datang', 'message': 'Isi pesan',
                 'credentials': [('Username', 'u'), ('Password awal', '12345678')],
                 'link': '/', 'created_at': '2026-01-01T00:00:00+00:00', 'actor_name': 'Admin'}
        user = {'name': 'Pengguna'}
        _assert_safe_email(email_subject(notif), email_html(notif, user))


# ---------- alert_admins + deliver_notifications monkeypatch ----------
def test_alert_admins_fires_on_wa_failure(monkeypatch):
    """When send_whatsapp raises, alert_admins should send to admin email+WA with reason+content."""
    import notification_delivery as nd
    import mailer, whatsapp
    from core import db
    import importlib

    captured = {'emails': [], 'whatsapps': []}

    async def fake_send_email(to, subject, html, nid, text=''):
        captured['emails'].append({'to': to, 'subject': subject, 'text': text, 'html': html})
        return 'email-provider-id'

    async def fake_send_whatsapp_ok(phone, nid, rid, pid='', text=''):
        captured['whatsapps'].append({'to': phone, 'text': text})
        return 'wa-provider-id'

    async def fake_send_whatsapp_fail(phone, nid, rid, pid='', text=''):
        raise ValueError('WAHA down (simulated)')

    # Enable channels and set admin WA env + non-example admin email so alert reaches both
    os.environ['EMAIL_ENABLED'] = 'true'
    os.environ['WHATSAPP_ENABLED'] = 'true'
    os.environ['ADMIN_WHATSAPP_NUMBER'] = '+6281234567890'
    os.environ['ADMIN_EMAIL'] = 'admin-alert@maiharta.io'

    monkeypatch.setattr(mailer, 'email_configuration_error', lambda: '')
    monkeypatch.setattr(whatsapp, 'whatsapp_configuration_error', lambda: '')
    monkeypatch.setattr(nd, 'email_configuration_error', lambda: '')
    monkeypatch.setattr(nd, 'whatsapp_configuration_error', lambda: '')
    monkeypatch.setattr(nd, 'send_email', fake_send_email)
    # First call (user WA) fails; later calls (admin WA) succeed
    calls = {'n': 0}
    async def wa_router(phone, nid, rid, pid='', text=''):
        calls['n'] += 1
        if calls['n'] == 1:
            raise ValueError('WAHA down (simulated)')
        return await fake_send_whatsapp_ok(phone, nid, rid, pid, text)
    monkeypatch.setattr(nd, 'send_whatsapp', wa_router)

    async def run():
        # Build a target user with WA opted-in + non-example email so WA delivery is attempted
        from core import uid, now
        target = {'id': uid(), 'username': 'tst_fake', 'name': 'Target User', 'role': 'Developer',
                  'email': 'target_real@maiharta.io', 'whatsapp_number': '+6287700000001',
                  'whatsapp_opt_in_at': now(), 'active': True,
                  'notification_preferences': {'in_app': True, 'email': True, 'whatsapp': True},
                  'password_hash': 'x', 'created_at': now()}
        await db.users.insert_one(target.copy())
        notif = {'id': uid(), 'user_id': target['id'], 'kind': 'tiket',
                 'title': 'Tiket diperbarui', 'message': 'Pesan uji WA',
                 'link': '/notifications', 'project_id': '', 'actor_name': 'Sistem',
                 'created_at': now()}
        try:
            await nd.deliver_notifications([notif])
            # Verify an admin alert email was sent containing failure reason + original message
            alert_emails = [e for e in captured['emails'] if 'gagal' in e['subject'].lower()]
            assert alert_emails, f'Expected admin alert email, got {[e["subject"] for e in captured["emails"]]}'
            admin_mail = alert_emails[-1]
            combined = admin_mail['text'] + admin_mail['html']
            assert 'WAHA down' in combined
            assert 'Pesan uji WA' in combined
            # Admin WA alert too
            assert any('WAHA down' in w['text'] and 'Pesan uji WA' in w['text']
                       for w in captured['whatsapps']), 'Expected admin WA alert'
        finally:
            await db.users.delete_one({'id': target['id']})

    _run(run())


def test_alert_admins_silent_on_success(monkeypatch):
    import notification_delivery as nd
    import mailer, whatsapp
    from core import db, uid, now

    captured_admin = {'alerts': 0}

    async def fake_send_email(to, subject, html, nid, text=''):
        if 'gagal' in subject.lower():
            captured_admin['alerts'] += 1
        return 'ok'

    async def fake_send_whatsapp(phone, nid, rid, pid='', text=''):
        if 'gagal' in text.lower():
            captured_admin['alerts'] += 1
        return 'ok'

    os.environ['EMAIL_ENABLED'] = 'true'
    os.environ['WHATSAPP_ENABLED'] = 'true'
    monkeypatch.setattr(nd, 'email_configuration_error', lambda: '')
    monkeypatch.setattr(nd, 'whatsapp_configuration_error', lambda: '')
    monkeypatch.setattr(nd, 'send_email', fake_send_email)
    monkeypatch.setattr(nd, 'send_whatsapp', fake_send_whatsapp)

    async def run():
        target = {'id': uid(), 'username': 'tst_ok', 'name': 'Target OK', 'role': 'Developer',
                  'email': 'target_ok@maiharta.io', 'whatsapp_number': '+6287700000002',
                  'whatsapp_opt_in_at': now(), 'active': True,
                  'notification_preferences': {'in_app': True, 'email': True, 'whatsapp': True},
                  'password_hash': 'x', 'created_at': now()}
        await db.users.insert_one(target.copy())
        notif = {'id': uid(), 'user_id': target['id'], 'kind': 'info',
                 'title': 'Info', 'message': 'Isi info', 'link': '/notifications',
                 'project_id': '', 'actor_name': 'Sistem', 'created_at': now()}
        try:
            await nd.deliver_notifications([notif])
            assert captured_admin['alerts'] == 0, 'No admin alert should fire on success'
        finally:
            await db.users.delete_one({'id': target['id']})

    _run(run())
