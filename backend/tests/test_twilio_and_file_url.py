import os, sys, asyncio
from urllib.parse import parse_qs
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import whatsapp

SID = 'AC' + 'a' * 32
REAL = httpx.AsyncClient


def _factory(handler):
    return lambda *a, **k: REAL(*a, **{**k, 'transport': httpx.MockTransport(handler)})


def _env(monkeypatch, content=''):
    for k, v in {'WHATSAPP_ENABLED': 'true', 'TWILIO_ACCOUNT_SID': SID, 'TWILIO_AUTH_TOKEN': 'tok', 'TWILIO_WHATSAPP_FROM': 'whatsapp:+14155238886',
                 'APP_URL': 'https://crm.example.org', 'TWILIO_CONTENT_SID': content, 'TWILIO_API_KEY_SID': ''}.items():
        monkeypatch.setenv(k, v)


def test_twilio_body_message(monkeypatch):
    _env(monkeypatch)
    seen = {}
    def handler(req):
        seen['url'], seen['auth'], seen['form'] = str(req.url), req.headers['authorization'], parse_qs(req.content.decode())
        return httpx.Response(201, json={'sid': 'SM123', 'status': 'queued'})
    monkeypatch.setattr(whatsapp.httpx, 'AsyncClient', _factory(handler))
    assert asyncio.run(whatsapp.send_whatsapp('0812 3456 7890', 'n1', 'u1', '', 'Halo\nDunia')) == 'SM123'
    assert seen['url'] == f'https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json'
    assert seen['auth'].startswith('Basic ')
    assert seen['form']['To'] == ['whatsapp:+6281234567890'] and seen['form']['From'] == ['whatsapp:+14155238886']
    assert seen['form']['Body'] == ['Halo\nDunia']


def test_twilio_template_and_sandbox_error(monkeypatch):
    _env(monkeypatch, 'HX' + 'b' * 32)
    seen = {}
    def ok(req):
        seen['form'] = parse_qs(req.content.decode())
        return httpx.Response(201, json={'sid': 'SM9', 'status': 'queued'})
    monkeypatch.setattr(whatsapp.httpx, 'AsyncClient', _factory(ok))
    asyncio.run(whatsapp.send_whatsapp('+6281234567890', 'n1', 'u1', '', 'A\nB'))
    assert 'Body' not in seen['form'] and seen['form']['ContentVariables'] == ['{"1": "A · B"}']
    monkeypatch.setattr(whatsapp.httpx, 'AsyncClient', _factory(lambda r: httpx.Response(400, json={'code': 63015, 'message': 'x'})))
    with pytest.raises(ValueError, match='Sandbox'):
        asyncio.run(whatsapp.send_whatsapp('+6281234567890', 'n1', 'u1'))


def test_twilio_config_errors(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setenv('TWILIO_WHATSAPP_FROM', '+14155238886')
    assert whatsapp.whatsapp_configuration_error() == ''
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', '')
    assert 'TWILIO_AUTH_TOKEN' in whatsapp.whatsapp_configuration_error()
