# Iteration 3: Admin counts as developer in project team validation + PIC backfill revert migration
import os, subprocess, pytest, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0]
BASE_URL = BASE_URL.rstrip('/')


def token(username):
    return subprocess.check_output(['bash', '/app/tests/login_token.sh', username]).decode().strip()


@pytest.fixture(scope='module')
def admin():
    s = requests.Session()
    s.headers['Authorization'] = f'Bearer {token("admin")}'
    return s


@pytest.fixture(scope='module')
def created(admin):
    ids = []
    yield ids
    for pid in ids:
        r = admin.delete(f'{BASE_URL}/api/projects/{pid}')
        print('cleanup', pid, r.status_code)


def payload(team, name):
    client = requests.get(f'{BASE_URL}/api/clients', headers={'Authorization': f'Bearer {token("admin")}'}).json()[0]['id']
    return {'name': f'TEST_{name}', 'client_id': client, 'description': 'test', 'platforms': ['Web'], 'type': 'Kecil',
            'value': 0, 'start_date': '2026-01-01', 'due_date': '2026-02-01', 'assigned_to': team, 'internal_notes': ''}


# Project team validation
def test_admin_only_team_ok(admin, created):
    r = admin.post(f'{BASE_URL}/api/projects', json=payload(['user-admin'], 'admin_only'))
    assert r.status_code == 200, r.text
    created.append(r.json()['id'])
    g = admin.get(f'{BASE_URL}/api/projects/{r.json()["id"]}')
    assert g.status_code == 200
    body = g.json()
    proj = body.get('project', body)
    assert 'user-admin' in proj['assigned_to']


def test_adminproject_only_team_400(admin, created):
    r = admin.post(f'{BASE_URL}/api/projects', json=payload(['user-adminproject'], 'ap_only'))
    if r.status_code == 200: created.append(r.json()['id'])
    assert r.status_code == 400, r.text
    assert 'Developer' in r.json()['detail']


def test_developer_only_team_400(admin, created):
    r = admin.post(f'{BASE_URL}/api/projects', json=payload(['user-developer'], 'dev_only'))
    if r.status_code == 200: created.append(r.json()['id'])
    assert r.status_code == 400, r.text
    assert 'Admin' in r.json()['detail']


def test_patch_to_admin_only_ok(admin, created):
    r = admin.post(f'{BASE_URL}/api/projects', json=payload(['user-adminproject', 'user-developer'], 'patch'))
    assert r.status_code == 200, r.text
    pid = r.json()['id']; created.append(pid)
    p = admin.patch(f'{BASE_URL}/api/projects/{pid}', json=payload(['user-admin'], 'patch'))
    assert p.status_code == 200, p.text
    p2 = admin.patch(f'{BASE_URL}/api/projects/{pid}', json=payload(['user-adminproject'], 'patch'))
    assert p2.status_code == 400, p2.text


# New task without PIC still gets creator as PIC
def test_new_task_gets_creator_pic(admin, created):
    pid = created[0]
    r = admin.post(f'{BASE_URL}/api/projects/{pid}/tasks', json={'title': 'TEST_task_nopic'})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t.get('assigned_to') == 'user-admin' or 'user-admin' in (t.get('assignee_ids') or []), t


# Migration result: 9 unassigned tasks
def test_tasks_by_user_unassigned(admin):
    r = admin.get(f'{BASE_URL}/api/admin/tasks-by-user')
    assert r.status_code == 200
    groups = {g['user_id']: g for g in r.json()}
    assert len(groups['']['tasks']) == 9
    assert groups['']['name'] == 'Belum ditugaskan'
    assert len(groups['user-developer']['tasks']) == 16
