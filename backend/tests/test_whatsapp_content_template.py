import os, sys, json, asyncio
from urllib.parse import parse_qs
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import whatsapp
import whatsapp_template as wt

SID = 'AC' + 'a' * 32
HX = 'HX' + 'c' * 32
REAL = httpx.AsyncClient


def _factory(handler):
    return lambda *a, **k: REAL(*a, **{**k, 'transport': httpx.MockTransport(handler)})


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k, v in {'WHATSAPP_ENABLED': 'true', 'TWILIO_ACCOUNT_SID': SID, 'TWILIO_AUTH_TOKEN': 'tok', 'TWILIO_WHATSAPP_FROM': 'whatsapp:+14155238886',
                 'APP_URL': 'https://crm.example.org', 'TWILIO_CONTENT_SID': '', 'TWILIO_API_KEY_SID': ''}.items():
        monkeypatch.setenv(k, v)


def test_send_with_synced_template_uses_content_sid_and_all_variables(monkeypatch):
    seen = {}
    def handler(req):
        seen['form'] = parse_qs(req.content.decode())
        return httpx.Response(201, json={'sid': 'SM1', 'status': 'queued'})
    monkeypatch.setattr(whatsapp.httpx, 'AsyncClient', _factory(handler))
    variables = wt.template_variables({'kind': 'tiket', 'title': 'Tiket baru', 'message': 'Baris 1\nBaris 2', 'link': '/tickets'}, {'name': 'Budi'}, 'Web A')
    asyncio.run(whatsapp.send_whatsapp('+6281234567890', 'n1', 'u1', '', 'teks', HX, variables))
    assert seen['form']['ContentSid'] == [HX] and 'Body' not in seen['form']
    sent = json.loads(seen['form']['ContentVariables'][0])
    assert set(sent) == {'1', '2', '3', '4', '5', '6'} and sent['4'] == 'Baris 1 · Baris 2'
    assert sent['6'] == 'Lihat di CRM: https://crm.example.org/tickets'
    assert all('\n' not in v and v for v in sent.values())


def test_21654_is_explained_in_indonesian(monkeypatch):
    monkeypatch.setattr(whatsapp.httpx, 'AsyncClient', _factory(lambda r: httpx.Response(400, json={'code': 21654, 'message': 'ContentSid Required'})))
    with pytest.raises(ValueError) as err:
        asyncio.run(whatsapp.send_whatsapp('+6281234567890', 'n1', 'u1', '', 'teks'))
    friendly, raw = str(err.value).split('\n')
    assert 'Sinkronkan ke Twilio' in friendly and 'kode 21654' in raw and 'ContentSid Required' in raw


def test_create_and_submit_calls_content_api(monkeypatch):
    calls = []
    def handler(req):
        calls.append((req.method, str(req.url), json.loads(req.content or b'{}')))
        if req.url.path.endswith('/Content'):
            return httpx.Response(201, json={'sid': HX})
        return httpx.Response(201, json={'status': 'received'})
    monkeypatch.setattr(wt.httpx, 'AsyncClient', _factory(handler))
    out = asyncio.run(wt.create_and_submit())
    assert out['content_sid'] == HX and out['status'] == 'received'
    assert calls[0][1] == 'https://content.twilio.com/v1/Content' and calls[0][2]['types']['twilio/text']['body'] == wt.TEMPLATE_BODY
    assert calls[0][2]['language'] == 'id' and set(calls[0][2]['variables']) == {'1', '2', '3', '4', '5', '6'}
    assert calls[1][1] == f'https://content.twilio.com/v1/Content/{HX}/ApprovalRequests/whatsapp' and calls[1][2]['category'] == 'UTILITY'


def test_approval_status(monkeypatch):
    monkeypatch.setattr(wt.httpx, 'AsyncClient', _factory(lambda r: httpx.Response(200, json={'whatsapp': {'status': 'approved', 'rejection_reason': ''}})))
    assert asyncio.run(wt.approval_status(HX)) == {'status': 'approved', 'rejection_reason': ''}
