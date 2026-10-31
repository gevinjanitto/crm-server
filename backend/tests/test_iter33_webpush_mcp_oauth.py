# Iteration 33: Web Push (/api/push), MCP OAuth-only, PWA static assets, push triggered by in-app notifications
import os
import re
import time
import base64
import secrets
import subprocess
import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0]
BASE_URL = BASE_URL.rstrip('/')
API = f'{BASE_URL}/api'
PASSWORD = 'Preview-Admin-2026'


def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def fake_keys():
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {'p256dh': b64u(pub), 'auth': b64u(secrets.token_bytes(16))}


def login(username='admin'):
    c = requests.get(f'{API}/auth/captcha').json()
    a, b = map(int, re.findall(r'\d+', c['question'])[:2])
    r = requests.post(f'{API}/auth/login', json={'username': username, 'password': PASSWORD, 'captcha_id': c['id'], 'captcha_answer': str(a + b)})
    assert r.status_code == 200, r.text
    return r.json()['token']


@pytest.fixture(scope='module')
def s():
    sess = requests.Session()
    sess.headers['Authorization'] = f'Bearer {login()}'
    yield sess
    # cleanup: remove all subscriptions of admin created by this test
    for ep in getattr(sess, '_eps', []):
        sess.post(f'{API}/push/unsubscribe', json={'endpoint': ep})


def devices(s): return s.get(f'{API}/push/status').json()['devices']


# --- Push public key / status
class TestPushBasics:
    def test_public_key(self):
        r = requests.get(f'{API}/push/public-key')
        assert r.status_code == 200
        d = r.json()
        assert list(d.keys()) == ['public_key']
        assert len(d['public_key']) > 60

    def test_status_requires_auth(self):
        assert requests.get(f'{API}/push/status').status_code == 401

    def test_status(self, s):
        d = s.get(f'{API}/push/status').json()
        assert d['configured'] is True and isinstance(d['devices'], int)


# --- Subscribe / unsubscribe / test
class TestPushSubscribe:
    def test_http_endpoint_rejected(self, s):
        r = s.post(f'{API}/push/subscribe', json={'endpoint': 'http://example.com/push/abcdefghijkl', 'keys': fake_keys()})
        assert r.status_code == 400

    def test_subscribe_unauth(self):
        r = requests.post(f'{API}/push/subscribe', json={'endpoint': 'https://fcm.googleapis.com/fcm/send/x' * 2, 'keys': fake_keys()})
        assert r.status_code == 401

    def test_test_without_devices(self, s):
        # ensure clean
        assert devices(s) == 0, 'admin already has devices'
        r = s.post(f'{API}/push/test')
        assert r.status_code == 400
        assert 'Belum ada perangkat aktif' in r.json()['detail']

    def test_subscribe_dedupe_unsubscribe(self, s):
        ep = 'https://fcm.googleapis.com/fcm/send/TEST_' + secrets.token_hex(12)
        s._eps = [ep]
        keys = fake_keys()
        r = s.post(f'{API}/push/subscribe', json={'endpoint': ep, 'keys': keys, 'device': 'Chrome · Linux'})
        assert r.status_code == 200 and 'aktif' in r.json()['message']
        assert devices(s) == 1
        r = s.post(f'{API}/push/subscribe', json={'endpoint': ep, 'keys': keys})
        assert r.status_code == 200
        assert devices(s) == 1
        r = s.post(f'{API}/push/unsubscribe', json={'endpoint': ep})
        assert r.status_code == 200
        assert devices(s) == 0

    def test_fake_endpoint_auto_removed(self, s):
        ep = 'https://fcm.googleapis.com/fcm/send/TEST_' + secrets.token_hex(12)
        s._eps = [ep]
        assert s.post(f'{API}/push/subscribe', json={'endpoint': ep, 'keys': fake_keys()}).status_code == 200
        assert devices(s) == 1
        r = s.post(f'{API}/push/test')
        print('push test ->', r.status_code, r.text)
        assert r.status_code == 400  # push service rejected -> 0 sent
        assert devices(s) == 0

    def test_in_app_notification_triggers_push(self, s):
        ep = 'https://fcm.googleapis.com/fcm/send/TEST_' + secrets.token_hex(12)
        s._eps = [ep]
        assert s.post(f'{API}/push/subscribe', json={'endpoint': ep, 'keys': fake_keys()}).status_code == 200
        before = subprocess.run('wc -l < /var/log/supervisor/backend.err.log', shell=True, capture_output=True, text=True).stdout.strip()
        r = s.post(f'{API}/account/notifications/test')
        print('account test ->', r.status_code, r.text)
        assert r.status_code in (200, 429)
        if r.status_code == 429: pytest.skip('rate limited')
        time.sleep(4)
        # Fake FCM endpoint should have been hit by push and auto-removed
        assert devices(s) == 0, 'push_notifications was not triggered by in-app notification'
        tail = subprocess.run(f'tail -n +{int(before or 0) + 1} /var/log/supervisor/backend.err.log', shell=True, capture_output=True, text=True).stdout
        assert 'Traceback' not in tail, tail[-2000:]


# --- MCP requires OAuth
class TestMcpOAuth:
    def test_no_auth(self):
        r = requests.post(f'{API}/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        assert r.status_code == 401
        assert 'resource_metadata=' in r.headers.get('www-authenticate', '')

    def test_fake_pat_rejected(self):
        r = requests.post(f'{API}/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Authorization': 'Bearer mh_pat_fake123'})
        assert r.status_code == 401
        assert 'wajib login lewat OAuth' in r.json()['detail']
        assert 'oauth-protected-resource' in r.headers.get('www-authenticate', '')

    def test_real_pat_rejected_on_mcp_but_works_elsewhere(self, s):
        r = s.post(f'{API}/me/tokens', json={'name': 'TEST_mcp_pat', 'scopes': ['read']})
        if r.status_code != 200: pytest.skip(f'AI feature disabled: {r.status_code} {r.text}')
        tok = r.json()
        try:
            m = requests.post(f'{API}/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Authorization': f"Bearer {tok['token']}"})
            assert m.status_code == 401
            assert 'wajib login lewat OAuth' in m.json()['detail']
            assert 'resource_metadata=' in m.headers.get('www-authenticate', '')
        finally:
            s.delete(f"{API}/me/tokens/{tok['id']}/purge")

    def test_oauth_metadata(self):
        r1 = requests.get(f'{API}/.well-known/oauth-protected-resource')
        r2 = requests.get(f'{API}/.well-known/oauth-authorization-server')
        assert r1.status_code == 200 and 'authorization_servers' in r1.json()
        assert r2.status_code == 200 and 'token_endpoint' in r2.json()


# --- PWA static assets
class TestPwaAssets:
    def test_manifest(self):
        r = requests.get(f'{BASE_URL}/manifest.json')
        assert r.status_code == 200
        d = r.json()
        assert d['display'] == 'standalone'
        srcs = [i['src'] for i in d['icons']]
        assert '/assets/app-icon-192.png' in srcs and '/assets/app-icon-512.png' in srcs
        for src in set(srcs):
            ir = requests.get(f'{BASE_URL}{src}')
            assert ir.status_code == 200 and ir.headers['content-type'].startswith('image/png')

    def test_sw(self):
        r = requests.get(f'{BASE_URL}/sw.js')
        assert r.status_code == 200 and "addEventListener('push'" in r.text
        assert 'javascript' in r.headers.get('content-type', '')

    def test_badge_icon(self):
        assert requests.get(f'{BASE_URL}/assets/app-badge-96.png').status_code == 200
