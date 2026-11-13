# Tests for link-document sharing, file shares, and setup.sh download
import os
import subprocess
from datetime import datetime, timedelta, timezone
import pytest
import requests

def _base():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if not v:
        for line in open('/app/frontend/.env'):
            if line.startswith('REACT_APP_BACKEND_URL='):
                v = line.split('=', 1)[1].strip()
    return v.rstrip('/')

BASE_URL = _base()
FILE_DOC = '36c5f808-48ce-456f-b17e-e2a68c5676a5'
LINK_DOC = 'a007cc4d-d3a5-43d1-bc86-286110ef8a0a'

@pytest.fixture(scope='module')
def client():
    out = subprocess.run('cd /app/backend && python3 /root/mktoken.py 2>/dev/null | grep "^eyJ"', shell=True, capture_output=True, text=True).stdout.strip()
    if not out: pytest.skip('no admin token')
    s = requests.Session(); s.headers['Authorization'] = f'Bearer {out}'
    created = []
    s.created = created
    yield s
    for sid in created: s.delete(f'{BASE_URL}/api/shares/{sid}')

def _exp(h=24): return (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()

# Link-document sharing
class TestLinkShare:
    def test_create_link_share_and_public_info(self, client):
        r = client.post(f'{BASE_URL}/api/shares', json={'document_id': LINK_DOC, 'expires_at': _exp(), 'allow_download': True})
        assert r.status_code == 200, r.text
        s = r.json(); client.created.append(s['id'])
        assert s['document_type'] == 'link' and isinstance(s['token'], str) and '_id' not in s
        info = requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}').json()
        assert info['document_type'] == 'link'
        assert info['url'] == 'https://www.figma.com/file/abc'
        assert info['allow_download'] is False
        assert info['name'] == 'Desain Figma'
        f = requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}/file')
        assert f.status_code == 400
        lst = client.get(f'{BASE_URL}/api/shares', params={'document_id': LINK_DOC}).json()
        assert any(x['id'] == s['id'] for x in lst)

    def test_revoke_link_share(self, client):
        s = client.post(f'{BASE_URL}/api/shares', json={'document_id': LINK_DOC, 'expires_at': _exp()}).json()
        assert client.delete(f'{BASE_URL}/api/shares/{s["id"]}').status_code == 200
        assert requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}').status_code == 404

    def test_past_expiry_rejected(self, client):
        r = client.post(f'{BASE_URL}/api/shares', json={'document_id': LINK_DOC, 'expires_at': _exp(-1)})
        assert r.status_code == 400

    def test_unauth_create(self):
        r = requests.post(f'{BASE_URL}/api/shares', json={'document_id': LINK_DOC, 'expires_at': _exp()})
        assert r.status_code in (401, 403)

# File-document sharing regression
class TestFileShare:
    def test_file_share_info_file_download(self, client):
        s = client.post(f'{BASE_URL}/api/shares', json={'document_id': FILE_DOC, 'expires_at': _exp(), 'allow_download': True}).json()
        client.created.append(s['id'])
        info = requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}').json()
        assert info['document_type'] == 'file' and info['content_type'] == 'application/pdf'
        f = requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}/file')
        assert f.status_code == 200 and f.content[:4] == b'%PDF' and 'inline' in f.headers['content-disposition']
        d = requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}/file?download=true')
        assert d.status_code == 200 and 'attachment' in d.headers['content-disposition']

    def test_view_only_blocks_download(self, client):
        s = client.post(f'{BASE_URL}/api/shares', json={'document_id': FILE_DOC, 'expires_at': _exp(), 'allow_download': False}).json()
        client.created.append(s['id'])
        assert requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}/file').status_code == 200
        assert requests.get(f'{BASE_URL}/api/public/shares/{s["token"]}/file?download=true').status_code == 403

    def test_bad_token(self):
        assert requests.get(f'{BASE_URL}/api/public/shares/nope-token-xyz').status_code == 404

# Fixed demo share tokens from review request
class TestKnownTokens:
    def test_known_tokens(self):
        a = requests.get(f'{BASE_URL}/api/public/shares/OE9KG8qoJWHm3F-2pUwuuRUy')
        assert a.status_code == 200 and a.json()['document_type'] == 'file'
        b = requests.get(f'{BASE_URL}/api/public/shares/GTxk_VTgkPjH0BCUcphupw8p')
        assert b.status_code == 200 and b.json()['document_type'] == 'link'

# setup.sh download
def test_setup_sh():
    r = requests.get(f'{BASE_URL}/setup.sh')
    assert r.status_code == 200
    assert len(r.content) > 3_000_000
    assert r.content.startswith(b'#!')
    assert b'__PAYLOAD_BELOW__' in r.content
