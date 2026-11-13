# Superadmin role, admin notification scoping, custom share slugs + recipient, share report.
# Module-level tests (no classes) so xdist loadscope keeps everything on one worker (shared fixtures).
import os, uuid, time, requests, pytest
from datetime import date, timedelta

def _base():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if not v:
        for line in open('/app/frontend/.env'):
            if line.startswith('REACT_APP_BACKEND_URL='): v = line.split('=', 1)[1].strip()
    return v.rstrip('/')

BASE = _base()
API = BASE + '/api'
PW = 'Maiharta123!'
RUN = uuid.uuid4().hex[:6]


def login(username, password=PW):
    c = requests.get(f'{API}/auth/captcha').json()
    ans = str(eval(c['question'].split('=')[0]))
    r = requests.post(f'{API}/auth/login', json={'username': username, 'password': password, 'captcha_id': c['id'], 'captcha_answer': ans})
    assert r.status_code == 200, r.text
    s = requests.Session(); s.headers['Authorization'] = 'Bearer ' + r.json()['token']
    return s


@pytest.fixture(scope='module')
def sa(): return login('admin')

@pytest.fixture(scope='module')
def ap(): return login('adminproject')

@pytest.fixture(scope='module')
def client_s(): return login('client')

@pytest.fixture(scope='module')
def state(): return {'projects': [], 'shares': []}

@pytest.fixture(scope='module')
def admin2(sa, state):
    r = sa.post(f'{API}/users', json={'name': 'TEST Admin Dua', 'username': f'test_admin2_{RUN}', 'email': f'test_admin2_{RUN}@example.com', 'role': 'Admin'})
    assert r.status_code == 200, r.text
    u = r.json()
    assert u['is_superadmin'] is False
    s = login(u['username'], u['default_password'])
    yield {'user': u, 's': s}
    # cleanup projects + user
    for pid in state['projects']:
        sa.post(f'{API}/projects/{pid}/status', json={'status': 'Project Masuk'})
        sa.delete(f'{API}/projects/{pid}')
    for sid in state['shares']:
        sa.delete(f'{API}/shares/{sid}')
    d = sa.delete(f"{API}/users/{u['id']}")
    assert d.status_code == 200, d.text


# ---- Superadmin identity ----
def test_me_superadmin(sa):
    me = sa.get(f'{API}/auth/me').json()
    assert me['username'] == 'admin' and me['role'] == 'Admin' and me['is_superadmin'] is True

def test_exactly_one_superadmin(sa, admin2):
    rows = sa.get(f'{API}/users').json()
    supers = [u for u in rows if u.get('is_superadmin')]
    assert [u['username'] for u in supers] == ['admin']

def test_admin2_me_not_superadmin(admin2):
    me = admin2['s'].get(f'{API}/auth/me').json()
    assert me['role'] == 'Admin' and me['is_superadmin'] is False

# ---- Guards ----
def test_admin2_cannot_patch_superadmin(admin2):
    r = admin2['s'].patch(f'{API}/users/user-admin', json={'name': 'Hacked Name'})
    assert r.status_code == 403
    r = admin2['s'].patch(f'{API}/users/user-admin', json={'active': False})
    assert r.status_code == 403
    r = admin2['s'].patch(f'{API}/users/user-admin', json={'role': 'Developer'})
    assert r.status_code == 403

def test_admin2_cannot_delete_superadmin(admin2, sa):
    r = admin2['s'].delete(f'{API}/users/user-admin')
    assert r.status_code == 403
    me = sa.get(f'{API}/auth/me').json()
    assert me['name'] != 'Hacked Name' and me['is_superadmin'] is True

def test_admin2_cannot_set_is_superadmin(admin2):
    r = admin2['s'].patch(f"{API}/users/{admin2['user']['id']}", json={'is_superadmin': True})
    assert r.status_code in (400, 422)

def test_superadmin_can_edit_admin2(sa, admin2):
    r = sa.patch(f"{API}/users/{admin2['user']['id']}", json={'name': 'TEST Admin Dua Edit'})
    assert r.status_code == 200 and r.json()['name'] == 'TEST Admin Dua Edit'

# ---- Notification scoping ----
def _mk_project(sa, state, team):
    today = date.today()
    r = sa.post(f'{API}/projects', json={'name': f'TEST_Notif {RUN} {len(state["projects"])}', 'client_id': 'client-1', 'platforms': ['Web'],
                                         'start_date': today.isoformat(), 'due_date': (today + timedelta(days=30)).isoformat(), 'assigned_to': team})
    assert r.status_code == 200, r.text
    state['projects'].append(r.json()['id'])
    return r.json()['id']

def _notifs(s, pid):
    return [n for n in s.get(f'{API}/notifications').json()['items'] if n['project_id'] == pid]

def test_notification_scoping(sa, ap, admin2, state):
    a2 = admin2['user']['id']
    p_out = _mk_project(sa, state, ['user-developer', 'user-adminproject'])
    p_in = _mk_project(sa, state, ['user-developer', 'user-adminproject', a2])
    for pid in (p_out, p_in):
        r = ap.post(f'{API}/projects/{pid}/status', json={'status': 'Scope Dirinci'})
        assert r.status_code == 200, r.text
    time.sleep(1.5)
    out_n = _notifs(admin2['s'], p_out)
    in_n = _notifs(admin2['s'], p_in)
    assert out_n == [], f'admin2 not assigned still got: {[n["title"] for n in out_n]}'
    assert any('Status project' in n['title'] for n in in_n), [n['title'] for n in in_n]
    # superadmin receives all project notifications
    assert any('Status project' in n['title'] for n in _notifs(sa, p_out))
    assert any('Status project' in n['title'] for n in _notifs(sa, p_in))

def test_admin_project_unassigned_no_notification(sa, admin2, state):
    # Admin Project behaviour unchanged: not assigned -> no notification
    a2 = admin2['s']
    pid = _mk_project(sa, state, ['user-developer', admin2['user']['id']])
    r = a2.post(f'{API}/projects/{pid}/status', json={'status': 'Scope Dirinci'})
    assert r.status_code == 200, r.text
    time.sleep(1.5)
    ap = login('adminproject')
    assert _notifs(ap, pid) == []
    assert any('Status project' in n['title'] for n in _notifs(sa, pid))

# ---- Share slug + recipient ----
def test_share_custom_slug(sa, state, admin2):
    slug_raw = f'Proposal Klien B {RUN}'
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': slug_raw, 'recipient': 'TEST Bu Sari'})
    assert r.status_code == 200, r.text
    s = r.json(); state['shares'].append(s['id'])
    assert s['token'] == f'proposal-klien-b-{RUN}'
    assert s['recipient'] == 'TEST Bu Sari' and s['custom_slug'] is True
    pub = requests.get(f"{API}/public/shares/{s['token']}")
    assert pub.status_code == 200 and pub.json()['name'] == 'Proposal A'
    state['slug'] = s['token']; state['slug_id'] = s['id']

def test_share_duplicate_slug_409(sa, state):
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': state['slug']})
    assert r.status_code == 409
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': 'proposal-klien-a'})
    assert r.status_code == 409

@pytest.mark.parametrize('bad', ['ab', 'Halo!!', '../etc', 'x' * 61, 'ñame-ok'])
def test_share_invalid_slug_400(sa, bad):
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': bad})
    assert r.status_code in (400, 422), (bad, r.status_code, r.text)

def test_share_empty_slug_random(sa, state):
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': '', 'password': 'rahasia1'})
    assert r.status_code == 200
    s = r.json(); state['shares'].append(s['id'])
    assert len(s['token']) >= 20 and s['custom_slug'] is False and s['has_password'] is True
    # password regression
    assert requests.get(f"{API}/public/shares/{s['token']}").status_code == 401
    assert requests.post(f"{API}/public/shares/{s['token']}/unlock", json={'password': 'salah123'}).status_code == 400
    k = requests.post(f"{API}/public/shares/{s['token']}/unlock", json={'password': 'rahasia1'}).json()['key']
    assert requests.get(f"{API}/public/shares/{s['token']}", params={'k': k}).status_code == 200

def test_public_page_slug(state):
    r = requests.get(f"{BASE}/s/{state['slug']}")
    assert r.status_code == 200 and '<div id="root"' in r.text

# ---- Report ----
def test_report_and_revoke(sa, state):
    sid = state['slug_id']
    assert sa.delete(f'{API}/shares/{sid}').status_code == 200
    assert requests.get(f"{API}/public/shares/{state['slug']}").status_code == 404
    rows = sa.get(f'{API}/shares/report', params={'project_id': 'project-1'}).json()
    me = next(r for r in rows if r['id'] == sid)
    assert me['status'] == 'Dicabut' and me['recipient'] == 'TEST Bu Sari'
    assert all('password_hash' not in r for r in rows)
    assert any(r['token'] == 'proposal-klien-a' and r['status'] == 'Aktif' for r in rows)
    # revoked slug still reserved
    r = sa.post(f'{API}/shares', json={'document_id': 'a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8', 'slug': state['slug']})
    assert r.status_code == 409

def test_report_client_403(client_s):
    r = client_s.get(f'{API}/shares/report', params={'project_id': 'project-1'})
    assert r.status_code == 403

def test_report_developer_scope():
    dev = login('developer')
    assert dev.get(f'{API}/shares/report', params={'project_id': 'project-1'}).status_code == 200
    assert dev.get(f'{API}/shares/report', params={'project_id': 'project-7'}).status_code in (403, 404)

def test_bulk_share_slug(sa, state):
    r = sa.post(f'{API}/shares', json={'document_ids': ['a11fb8f2-aac5-4c09-87db-a6ab3ce9bdd8'], 'slug': f'bundle-{RUN}', 'recipient': 'TEST X'})
    assert r.status_code == 200
    state['shares'].append(r.json()['id'])
    assert r.json()['token'] == f'bundle-{RUN}'
