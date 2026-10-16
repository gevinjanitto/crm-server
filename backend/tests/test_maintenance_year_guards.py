"""Tests for maintenance guards, year grouping, and finance for maintenance-based CRM."""
import os, requests, pytest

BASE = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = BASE + '/api'
PASS = 'Maiharta2026!'


def _login(username):
    c = requests.get(f'{API}/auth/captcha').json()
    nums = [int(x) for x in c['question'].replace('?','').replace('=','').split() if x.strip().isdigit()]
    ans = sum(nums)
    r = requests.post(f'{API}/auth/login', json={'username': username, 'password': PASS,
                                                 'captcha_id': c['id'], 'captcha_answer': str(ans)})
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    return r.json()['token']


@pytest.fixture(scope='module')
def admin():
    return _login('admin')


@pytest.fixture(scope='module')
def client_token():
    return _login('client')


@pytest.fixture(scope='module')
def accounting():
    return _login('accounting')


def _h(tok):
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


def _projects(tok):
    r = requests.get(f'{API}/projects', headers=_h(tok))
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Year/finance fields on /api/projects ----------
def test_projects_year_fields_present(admin):
    rows = _projects(admin)
    by_code = {p['code']: p for p in rows}
    assert 'MH-005' in by_code and 'MH-007' in by_code
    m5 = by_code['MH-005']
    assert m5['status'] == 'Selesai'
    assert m5['completion_year'] == '2024'
    assert m5['group_year'] == '2024'
    assert m5['maintenance_year'] == '2026'
    assert m5['maintenance_cost'] == 3500000
    assert m5['maintenance_count'] >= 1
    m7 = by_code['MH-007']
    assert m7['completion_year'] == '2025'
    assert m7['group_year'] == '2025'
    # unfinished projects fall into current year
    for code in ['MH-001','MH-002','MH-003','MH-004','MH-006','MH-008']:
        assert by_code[code]['group_year'] == '2026', f"{code} group_year={by_code[code]['group_year']}"
        assert by_code[code]['completion_year'] in (None, '')


# ---------- Maintenance creation guard ----------
def _mk_work_body(title):
    return {'title': title, 'description': 'test', 'kind': 'Adaptive', 'priority': 'Rendah',
            'assigned_to': '', 'due_date': None, 'started_date': None, 'estimate': 0, 'subtasks': []}


def test_maintenance_blocked_on_unfinished(admin):
    rows = _projects(admin)
    unfinished = next(p for p in rows if p['status'] != 'Selesai')
    r = requests.post(f"{API}/projects/{unfinished['id']}/work/maintenances",
                      headers=_h(admin), json=_mk_work_body('TEST_block'))
    assert r.status_code == 400, r.text
    assert 'Selesai' in r.text


def test_maintenance_ok_on_selesai(admin):
    rows = _projects(admin)
    m5 = next(p for p in rows if p['code'] == 'MH-005')
    r = requests.post(f"{API}/projects/{m5['id']}/work/maintenances",
                      headers=_h(admin), json=_mk_work_body('TEST_ok_maint'))
    assert r.status_code == 200, r.text
    wid = r.json()['id']
    # cleanup
    requests.delete(f"{API}/projects/{m5['id']}/work/maintenances/{wid}", headers=_h(admin))


# ---------- Ticket Diterima guard ----------
def test_ticket_diterima_blocked_on_unfinished(admin, client_token):
    # Client creates a ticket on unfinished project MH-001
    projs = requests.get(f'{API}/ticket-projects', headers=_h(client_token)).json()
    assert projs, 'client sees no projects'
    target = next((p for p in projs if p['code'] in ['MH-001','MH-002','MH-003','MH-004','MH-006','MH-008']), projs[0])
    body = {'project_id': target['id'], 'title': 'TEST_block_ticket', 'description': 'desc test',
            'category': 'Bug / Problem', 'priority': 'Rendah', 'description_html': ''}
    r = requests.post(f'{API}/tickets', headers=_h(client_token), json=body)
    assert r.status_code == 200, r.text
    tid = r.json()['id']
    # Try to move to Diterima via admin triage path (Baru->Ditinjau->Diterima)
    r2 = requests.patch(f'{API}/tickets/{tid}', headers=_h(admin), json={'status': 'Ditinjau'})
    assert r2.status_code == 200, r2.text
    r3 = requests.patch(f'{API}/tickets/{tid}', headers=_h(admin), json={'status': 'Diterima'})
    assert r3.status_code == 400, f'expected 400 got {r3.status_code}: {r3.text}'
    assert 'Selesai' in r3.text


# ---------- Dashboard finance ----------
def test_dashboard_2026_includes_maintenance_value(admin):
    r = requests.get(f'{API}/dashboard?year=2026', headers=_h(admin))
    assert r.status_code == 200
    f = r.json()['finance']
    assert f.get('maintenance_value') == 3500000
    rows = _projects(admin)
    expected = sum(p.get('value', 0) for p in rows if p['group_year'] == '2026' and p['code'] != 'MH-005') + 3500000
    assert f['value'] == expected, f"got {f['value']} expected {expected}"


def test_dashboard_2024_contains_mh005_original(admin):
    r = requests.get(f'{API}/dashboard?year=2024', headers=_h(admin))
    assert r.status_code == 200
    f = r.json()['finance']
    assert f['value'] == 18500000
    assert f.get('maintenance_value', 0) == 0
