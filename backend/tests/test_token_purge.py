# Token purge (hard delete) endpoints: /api/me/tokens/{id}/purge and /api/admin/tokens/{id}/purge
import os, subprocess, pytest, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    for line in open('/app/frontend/.env'):
        if line.startswith('REACT_APP_BACKEND_URL='): BASE_URL = line.split('=', 1)[1].strip()
BASE_URL = BASE_URL.rstrip('/')
API = f'{BASE_URL}/api'

def _tok(cmd):
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd='/app/backend').stdout
    return next((l for l in out.splitlines() if l.startswith('eyJ')), None)

@pytest.fixture(scope='module')
def admin():
    t = _tok('python3 /root/mktoken.py 2>/dev/null')
    if not t: pytest.skip('no admin token')
    s = requests.Session(); s.headers['Authorization'] = f'Bearer {t}'
    # AI feature must be enabled for token create/list; restore previous state afterwards
    prev = s.get(f'{API}/admin/ai-settings').json().get('enabled')
    s.patch(f'{API}/admin/ai-settings', json={'enabled': True})
    yield s
    s.patch(f'{API}/admin/ai-settings', json={'enabled': bool(prev)})

@pytest.fixture(scope='module')
def dev(admin):
    t = _tok('python3 /app/backend/tests/_mk_role_token.py Developer 2>/dev/null')
    if not t: pytest.skip('no developer user')
    s = requests.Session(); s.headers['Authorization'] = f'Bearer {t}'; return s

def mk(s, name):
    r = s.post(f'{API}/me/tokens', json={'name': name, 'scopes': ['read']})
    assert r.status_code == 200, r.text
    d = r.json(); assert d['token'].startswith('mh_pat_'); return d

def ids(s, path): return [t['id'] for t in s.get(f'{API}{path}').json()]

def mcp_status(raw):
    r = requests.post(f'{API}/mcp', headers={'Authorization': f'Bearer {raw}', 'Accept': 'application/json, text/event-stream'},
                      json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    return r.status_code

class TestPurge:
    def test_purge_active_own_token(self, admin):
        t = mk(admin, 'TEST_purge_active')
        assert mcp_status(t['token']) == 200
        r = admin.delete(f"{API}/me/tokens/{t['id']}/purge")
        assert r.status_code == 200 and r.json()['message'] == 'Token dihapus.'
        assert t['id'] not in ids(admin, '/me/tokens')
        assert t['id'] not in ids(admin, '/admin/tokens')
        assert mcp_status(t['token']) == 401

    def test_purge_revoked_own_token(self, admin):
        t = mk(admin, 'TEST_purge_revoked')
        assert admin.delete(f"{API}/me/tokens/{t['id']}").status_code == 200
        row = next(x for x in admin.get(f'{API}/me/tokens').json() if x['id'] == t['id'])
        assert row['revoked_at']
        assert mcp_status(t['token']) == 401
        assert admin.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 200
        assert t['id'] not in ids(admin, '/me/tokens')

    def test_purge_unknown_404(self, admin):
        assert admin.delete(f'{API}/me/tokens/nope-xyz/purge').status_code == 404
        assert admin.delete(f'{API}/admin/tokens/nope-xyz/purge').status_code == 404

    def test_purge_twice_404(self, admin):
        t = mk(admin, 'TEST_purge_twice')
        assert admin.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 200
        assert admin.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 404

    def test_admin_purge_any_and_revoke(self, admin, dev):
        t = mk(dev, 'TEST_dev_token')
        # non-admin forbidden
        assert dev.delete(f"{API}/admin/tokens/{t['id']}/purge").status_code == 403
        assert dev.get(f'{API}/admin/tokens').status_code == 403
        # admin revoke still works
        assert admin.delete(f"{API}/admin/tokens/{t['id']}").status_code == 200
        assert mcp_status(t['token']) == 401
        # admin cannot purge another user's token via /me route
        assert admin.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 404
        assert admin.delete(f"{API}/admin/tokens/{t['id']}/purge").status_code == 200
        assert t['id'] not in ids(admin, '/admin/tokens')
        assert t['id'] not in ids(dev, '/me/tokens')

    def test_dev_cannot_purge_other_users_token(self, admin, dev):
        t = mk(admin, 'TEST_admin_tok')
        assert dev.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 404
        assert t['id'] in ids(admin, '/me/tokens')
        assert admin.delete(f"{API}/me/tokens/{t['id']}/purge").status_code == 200

    def test_unauth(self):
        assert requests.delete(f'{API}/me/tokens/x/purge').status_code == 401

class TestSetupSh:
    def test_setup_sh(self):
        r = requests.get(f'{BASE_URL}/setup.sh')
        assert r.status_code == 200
        assert len(r.content) > 2_000_000
        open('/tmp/setup.sh', 'wb').write(r.content)
        out = subprocess.run("sed -n '/^__PAYLOAD_BELOW__$/,$p' /tmp/setup.sh | tail -n +2 | base64 -d | tar -xzOf - --wildcards '*frontend/src/components/settings/ApiTokens.jsx'",
                             shell=True, capture_output=True, text=True).stdout
        assert 'deleteToken' in out
