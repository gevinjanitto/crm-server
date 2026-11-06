# Iteration 2: WhatsApp Content template reworded to UTILITY (labeled fixed text) + sync/outdated logic
import os, sys, json, asyncio, re
import httpx
import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
import whatsapp_template as wt

HX = 'HX' + 'c' * 32
REAL = httpx.AsyncClient


def _base():
    url = os.environ.get('REACT_APP_BACKEND_URL')
    if not url:
        for line in open('/app/frontend/.env'):
            if line.startswith('REACT_APP_BACKEND_URL='): url = line.split('=', 1)[1].strip()
    return url.rstrip('/')


BASE_URL = _base()


def _factory(handler):
    return lambda *a, **k: REAL(*a, **{**k, 'transport': httpx.MockTransport(handler)})


def _fill(body, variables):
    return re.sub(r'\{\{(\d+)\}\}', lambda m: variables[m.group(1)], body)


@pytest.fixture
def twilio_env(monkeypatch):
    for k, v in {'WHATSAPP_ENABLED': 'true', 'TWILIO_ACCOUNT_SID': 'AC' + 'a' * 32, 'TWILIO_AUTH_TOKEN': 'tok',
                 'TWILIO_WHATSAPP_FROM': 'whatsapp:+14155238886', 'APP_URL': 'https://crm.example.org', 'TWILIO_API_KEY_SID': ''}.items():
        monkeypatch.setenv(k, v)


# --- template text / samples
class TestTemplateBody:
    def test_body_exact(self):
        expected = ('Halo {{1}}, ada pembaruan pada akun CRM Maiharta Anda.\n\nJenis: {{2}}\nJudul: {{3}}\nDetail: {{4}}\nInfo: {{5}}\n\n'
                    'Lihat detailnya di CRM: {{6}}\n\nPesan otomatis ini dikirim karena Anda terdaftar di project tersebut. Atur notifikasi di menu Pengaturan.')
        assert wt.TEMPLATE_BODY == expected

    def test_body_not_start_or_end_with_variable(self):
        assert not wt.TEMPLATE_BODY.startswith('{{') and not wt.TEMPLATE_BODY.rstrip().endswith('}}')
        assert sorted(set(re.findall(r'\{\{(\d+)\}\}', wt.TEMPLATE_BODY))) == ['1', '2', '3', '4', '5', '6']

    def test_samples_match_meaning(self):
        s = wt.SAMPLES
        assert set(s) == {'1', '2', '3', '4', '5', '6'}
        assert s['1'] == 'Budi' and s['2'] == 'Penugasan' and s['6'].startswith('https://')
        assert all(v and '\n' not in v for v in s.values())


# --- template_variables
class TestTemplateVariables:
    def test_variables_mapping(self, twilio_env):
        n = {'kind': 'tiket', 'title': 'Tiket baru', 'message': 'Baris 1\nBaris 2\n\nBaris 3', 'link': '/tickets/abc',
             'actor_name': 'Admin', 'created_at': '2026-01-10T01:00:00+00:00'}
        v = wt.template_variables(n, {'name': 'Budi'}, 'Web A')
        assert set(v) == {'1', '2', '3', '4', '5', '6'}
        assert v['1'] == 'Budi' and v['3'] == 'Tiket baru'
        assert v['4'] == 'Baris 1 · Baris 2 · Baris 3'
        assert 'Project: Web A' in v['5'] and 'Oleh: Admin' in v['5'] and 'WITA' in v['5']
        assert v['6'] == 'https://crm.example.org/tickets/abc'
        assert all(x and '\n' not in x for x in v.values())
        filled = _fill(wt.TEMPLATE_BODY, v)
        assert filled.startswith('Halo Budi, ada pembaruan')
        assert 'Judul: Tiket baru\nDetail: Baris 1 · Baris 2 · Baris 3\nInfo: Project: Web A' in filled
        assert 'Lihat detailnya di CRM: https://crm.example.org/tickets/abc\n' in filled

    def test_variables_empty_fallbacks(self, twilio_env):
        v = wt.template_variables({}, {}, '')
        assert all(x and '\n' not in x for x in v.values())
        assert v['1'] == '-' and v['3'] == 'Pembaruan pekerjaan' and v['6'].endswith('/notifications')

    def test_whatsapp_message_preferred(self, twilio_env):
        v = wt.template_variables({'message': 'm', 'whatsapp_message': 'wa'}, {'name': 'X'})
        assert v['4'] == 'wa'


# --- create_and_submit (mocked httpx)
class TestCreateAndSubmit:
    def test_posts_body_and_utility(self, twilio_env, monkeypatch):
        calls = []
        def handler(req):
            calls.append((req.method, str(req.url), json.loads(req.content or b'{}')))
            if req.url.path.endswith('/Content'):
                return httpx.Response(201, json={'sid': HX})
            return httpx.Response(201, json={'status': 'received'})
        monkeypatch.setattr(wt.httpx, 'AsyncClient', _factory(handler))
        out = asyncio.run(wt.create_and_submit())
        assert out['content_sid'] == HX and out['status'] == 'received' and out['body'] == wt.TEMPLATE_BODY
        assert calls[0][2]['types']['twilio/text']['body'] == wt.TEMPLATE_BODY and calls[0][2]['variables'] == wt.SAMPLES
        assert calls[1][1].endswith(f'/Content/{HX}/ApprovalRequests/whatsapp')
        assert calls[1][2]['category'] == 'UTILITY' and 'allow_category_change' not in calls[1][2]
        assert calls[1][2]['name'] == calls[0][2]['friendly_name']


# --- sync logic (mocked create_and_submit / approval_status, in-process DB)
class FakeDB:
    def __init__(self, row): self.row = row
    async def find_one(self, f, p=None): return dict(self.row) if self.row else None
    async def update_one(self, f, update, upsert=False):
        self.row = {**(self.row or {}), **update.get('$set', {})}
        for k in update.get('$unset', {}): self.row.pop(k, None)


def _run_sync(monkeypatch, row, category='UTILITY'):
    import whatsapp_templates as wts
    fake = FakeDB(row)
    monkeypatch.setattr(wts, 'db', type('D', (), {'app_settings': fake})())
    created = []
    async def fake_create():
        created.append(1)
        return {'content_sid': 'HXNEW', 'name': 'n', 'status': 'received', 'rejection_reason': '', 'body': wt.TEMPLATE_BODY}
    async def fake_status(sid): return {'status': row.get('status', 'pending'), 'rejection_reason': '', 'category': category}
    async def noop(*a, **k): return None
    async def false(): return False
    monkeypatch.setattr(wts, 'create_and_submit', fake_create)
    monkeypatch.setattr(wts, 'approval_status', fake_status)
    monkeypatch.setattr(wts, 'authorize', noop)
    monkeypatch.setattr(wts, 'log_activity', noop)
    monkeypatch.setattr(wts, 'detect_trial', false)
    monkeypatch.setattr(wts, 'sandbox_mode', lambda: False)
    monkeypatch.setattr(wts, 'whatsapp_configuration_error', lambda: '')
    out = asyncio.run(wts.sync({'id': 'admin'}))
    return out, created, fake.row


class TestSyncLogic:
    def test_marketing_same_body_creates_new(self, twilio_env, monkeypatch):
        out, created, row = _run_sync(monkeypatch, {'id': 'whatsapp_template', 'content_sid': 'HXOLD', 'body': wt.TEMPLATE_BODY, 'status': 'pending'}, 'MARKETING')
        assert created == [1] and row['content_sid'] == 'HXNEW'

    def test_old_body_creates_new(self, twilio_env, monkeypatch):
        out, created, row = _run_sync(monkeypatch, {'id': 'whatsapp_template', 'content_sid': 'HXOLD', 'body': '{{1}} old', 'status': 'pending'})
        assert created == [1] and row['content_sid'] == 'HXNEW'

    def test_approved_old_body_keeps_old_and_adds_pending(self, twilio_env, monkeypatch):
        out, created, row = _run_sync(monkeypatch, {'id': 'whatsapp_template', 'content_sid': 'HXOLD', 'body': '{{1}} old', 'status': 'approved'}, 'MARKETING')
        assert created == [1] and row['content_sid'] == 'HXOLD' and row['pending_content_sid'] == 'HXNEW'

    def test_utility_current_body_no_new(self, twilio_env, monkeypatch):
        out, created, row = _run_sync(monkeypatch, {'id': 'whatsapp_template', 'content_sid': 'HXOLD', 'body': wt.TEMPLATE_BODY, 'status': 'pending'})
        assert created == [] and row['content_sid'] == 'HXOLD'

    def test_public_outdated(self):
        import whatsapp_templates as wts
        assert wts._public({'body': 'old {{1}}'})['outdated'] is True
        assert wts._public({'body': wt.TEMPLATE_BODY})['outdated'] is False
        assert wts._public(None)['outdated'] is False


# --- API (public URL)
def _login():
    s = requests.Session()
    c = s.get(f'{BASE_URL}/api/auth/captcha').json()
    q = c['question'].split()
    r = s.post(f'{BASE_URL}/api/auth/login', json={'username': 'admin', 'password': 'Maiharta123!', 'captcha_id': c['id'], 'captcha_answer': str(int(q[0]) + int(q[2]))})
    if r.status_code != 200: pytest.skip('login failed')
    s.headers['Authorization'] = 'Bearer ' + r.json()['token']
    return s


class TestApi:
    def test_get_template_body(self):
        s = _login()
        r = s.get(f'{BASE_URL}/api/admin/whatsapp-template')
        assert r.status_code == 200
        assert r.json()['body'] == wt.TEMPLATE_BODY

    def test_unauth_rejected(self):
        assert requests.get(f'{BASE_URL}/api/admin/whatsapp-template').status_code in (401, 403)

    def test_sync_rejected_when_disabled(self):
        s = _login()
        r = s.post(f'{BASE_URL}/api/admin/whatsapp-template/sync')
        assert r.status_code == 400 and 'WHATSAPP_ENABLED' in r.text


# --- regression imports
def test_regression_imports():
    import notification_delivery, whatsapp_report
    assert notification_delivery.template_variables is wt.template_variables
    assert whatsapp_report.template_variables is wt.template_variables
