"""Kanban end-to-end backend tests for MaiHarta CRM."""
import os, re, time
from pathlib import Path
import pytest
import requests
from dotenv import dotenv_values

ENV_FRONTEND = dotenv_values(Path(__file__).parents[2] / 'frontend' / '.env')
ENV_BACKEND = dotenv_values(Path(__file__).parents[1] / '.env')
BASE = (os.environ.get('REACT_APP_BACKEND_URL') or ENV_FRONTEND.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
API = f"{BASE}/api"
PASSWORD = ENV_BACKEND.get('SEED_PASSWORD', '')
PID = 'project-1'


def _login(username):
    if not BASE:
        pytest.skip('REACT_APP_BACKEND_URL missing')
    if not PASSWORD:
        pytest.skip('SEED_PASSWORD missing')
    s = requests.Session()
    s.headers['Content-Type'] = 'application/json'
    cap = s.get(f"{API}/auth/captcha").json()
    a, b = map(int, re.findall(r'\d+', cap['question']))
    r = s.post(f"{API}/auth/login", json={
        'username': username, 'password': PASSWORD,
        'captcha_id': cap['id'], 'captcha_answer': str(a + b)
    })
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    s.headers['Authorization'] = f"Bearer {r.json()['token']}"
    return s, r.json()['user']


@pytest.fixture(scope='module')
def admin():
    s, u = _login('admin')
    return s, u

@pytest.fixture(scope='module')
def adminproject():
    s, u = _login('adminproject')
    return s, u

@pytest.fixture(scope='module')
def developer():
    s, u = _login('developer')
    return s, u

@pytest.fixture(scope='module')
def client_sess():
    s, u = _login('client')
    return s, u


# ---------- Auth ----------
def test_login_all_roles():
    for uname in ['admin', 'adminproject', 'developer', 'client']:
        s, u = _login(uname)
        assert u['username'] == uname


# ---------- Statuses ----------
def test_default_statuses(adminproject):
    s, _ = adminproject
    r = s.get(f"{API}/projects/{PID}/statuses")
    assert r.status_code == 200
    cols = r.json()
    names = [c['name'] for c in cols]
    for n in ['Belum Mulai', 'Dikerjakan', 'Testing', 'Revisi', 'Selesai']:
        assert n in names, f"missing default status {n}: {names}"
    for c in cols:
        for k in ['id', 'name', 'color', 'kind']:
            assert k in c


def test_status_crud_manager_only(adminproject, developer):
    s, _ = adminproject
    ds, _ = developer
    # Developer forbidden
    r = ds.post(f"{API}/projects/{PID}/statuses", json={'name': 'DevAttempt', 'color': '#123456', 'kind': 'active'})
    assert r.status_code == 403

    # Create new column
    unique = f"TEST_Col_{int(time.time())}"
    r = s.post(f"{API}/projects/{PID}/statuses", json={'name': unique, 'color': '#abcdef', 'kind': 'active'})
    assert r.status_code == 200, r.text
    cols = r.json()
    new_col = next(c for c in cols if c['name'] == unique)
    new_id = new_col['id']

    # Create a task in new col
    tr = s.post(f"{API}/projects/{PID}/tasks", json={'title': 'TEST_task_in_new_col', 'status': unique})
    assert tr.status_code == 200
    tid = tr.json()['id']

    # Rename: tasks should follow
    renamed = unique + '_R'
    r = s.patch(f"{API}/projects/{PID}/statuses/{new_id}", json={'name': renamed})
    assert r.status_code == 200
    t = s.get(f"{API}/projects/{PID}/tasks").json()
    assert next(x for x in t if x['id'] == tid)['status'] == renamed

    # Reorder
    ids = [c['id'] for c in r.json()]
    reordered = list(reversed(ids))
    rr = s.post(f"{API}/projects/{PID}/statuses/reorder", json={'ids': reordered})
    assert rr.status_code == 200
    assert [c['id'] for c in rr.json()] == reordered

    # Delete column moves tasks
    r = s.delete(f"{API}/projects/{PID}/statuses/{new_id}?move_to=Belum Mulai")
    assert r.status_code == 200
    t = s.get(f"{API}/projects/{PID}/tasks").json()
    assert next(x for x in t if x['id'] == tid)['status'] == 'Belum Mulai'
    # cleanup
    s.delete(f"{API}/projects/{PID}/tasks/{tid}")


# ---------- Tasks ----------
def test_task_create_and_fields(adminproject):
    s, _ = adminproject
    payload = {
        'title': 'TEST_task_full', 'status': 'Belum Mulai',
        'tags': ['tag1', 'tag2'], 'estimate_hours': 3,
        'start_date': '2026-01-01', 'due_date': '2026-01-10',
        'subtasks': ['sub1', 'sub2']
    }
    r = s.post(f"{API}/projects/{PID}/tasks", json=payload)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t['title'] == 'TEST_task_full'
    assert set(t['tags']) == {'tag1', 'tag2'}
    assert t['estimate_hours'] == 3
    assert 'order' in t
    assert 'time_entries' in t
    assert len(t['subtasks']) == 2
    # cleanup
    s.delete(f"{API}/projects/{PID}/tasks/{t['id']}")


def test_task_patch_status_and_drag(adminproject):
    s, _ = adminproject
    r = s.post(f"{API}/projects/{PID}/tasks", json={'title': 'TEST_patch'})
    tid = r.json()['id']
    # Move
    r = s.patch(f"{API}/projects/{PID}/tasks/{tid}", json={'status': 'Dikerjakan', 'order': 5})
    assert r.status_code == 200
    assert r.json()['status'] == 'Dikerjakan'
    # Invalid status
    r = s.patch(f"{API}/projects/{PID}/tasks/{tid}", json={'status': 'Nonexistent'})
    assert r.status_code == 400
    # due_date null
    r = s.patch(f"{API}/projects/{PID}/tasks/{tid}", json={'due_date': None})
    assert r.status_code == 200
    s.delete(f"{API}/projects/{PID}/tasks/{tid}")


def test_developer_permissions(adminproject, developer):
    s, _ = adminproject
    ds, duser = developer
    r = s.post(f"{API}/projects/{PID}/tasks", json={'title': 'TEST_dev_perm', 'assigned_to': duser['id']})
    tid = r.json()['id']
    # Developer can update status
    r = ds.patch(f"{API}/projects/{PID}/tasks/{tid}", json={'status': 'Dikerjakan'})
    assert r.status_code == 200
    # Developer cannot update title
    r = ds.patch(f"{API}/projects/{PID}/tasks/{tid}", json={'title': 'hacked'})
    assert r.status_code == 403
    s.delete(f"{API}/projects/{PID}/tasks/{tid}")


# ---------- Comments ----------
def test_comments_flow(adminproject, client_sess):
    s, _ = adminproject
    cs, _ = client_sess
    r = s.post(f"{API}/projects/{PID}/tasks", json={'title': 'TEST_comments'})
    tid = r.json()['id']
    # Client can comment
    r = cs.post(f"{API}/projects/{PID}/tasks/{tid}/comments", json={'message': 'hi from client'})
    assert r.status_code == 200, r.text
    cid = r.json()['id']
    # Read
    r = s.get(f"{API}/projects/{PID}/tasks/{tid}/comments")
    assert r.status_code == 200 and len(r.json()) >= 1
    # comment_count reflected
    tasks = s.get(f"{API}/projects/{PID}/tasks").json()
    t = next(x for x in tasks if x['id'] == tid)
    assert t['comment_count'] >= 1
    # Delete
    r = s.delete(f"{API}/projects/{PID}/tasks/{tid}/comments/{cid}")
    assert r.status_code == 200
    s.delete(f"{API}/projects/{PID}/tasks/{tid}")


# ---------- Timer + Manual time ----------
def test_timer_toggle_and_manual(adminproject):
    s, _ = adminproject
    r = s.post(f"{API}/projects/{PID}/tasks", json={'title': 'TEST_timer'})
    tid = r.json()['id']
    r = s.post(f"{API}/projects/{PID}/tasks/{tid}/timer")
    assert r.status_code == 200
    assert r.json().get('running_entry')
    time.sleep(1.2)
    r = s.post(f"{API}/projects/{PID}/tasks/{tid}/timer")
    assert r.status_code == 200
    body = r.json()
    assert body.get('running_entry') in (None, {}) 
    assert body['time_total'] > 0
    # Manual
    r = s.post(f"{API}/projects/{PID}/tasks/{tid}/time", json={'minutes': 30, 'note': 'manual'})
    assert r.status_code == 200
    entries = r.json()['time_entries']
    manual = next(e for e in entries if e.get('manual'))
    r = s.delete(f"{API}/projects/{PID}/tasks/{tid}/time/{manual['id']}")
    assert r.status_code == 200
    s.delete(f"{API}/projects/{PID}/tasks/{tid}")


# ---------- Bulk ----------
def test_bulk_update(adminproject):
    s, _ = adminproject
    ids = []
    for i in range(3):
        r = s.post(f"{API}/projects/{PID}/tasks", json={'title': f'TEST_bulk_{i}'})
        ids.append(r.json()['id'])
    r = s.post(f"{API}/projects/{PID}/tasks/bulk", json={'ids': ids, 'status': 'Dikerjakan'})
    assert r.status_code == 200
    r = s.post(f"{API}/projects/{PID}/tasks/bulk", json={'ids': ids, 'priority': 'Tinggi'})
    assert r.status_code == 200
    r = s.post(f"{API}/projects/{PID}/tasks/bulk", json={'ids': ids, 'delete': True})
    assert r.status_code == 200


# ---------- Stats ----------
def test_stats(adminproject):
    s, _ = adminproject
    r = s.get(f"{API}/projects/{PID}/tasks/stats")
    assert r.status_code == 200
    data = r.json()
    for k in ['total', 'done', 'overdue', 'by_status', 'by_priority', 'by_assignee', 'by_source', 'time_total']:
        assert k in data, f"missing {k}"


# ---------- Sync: features ----------
def test_feature_sync_with_task(adminproject):
    s, _ = adminproject
    r = s.post(f"{API}/projects/{PID}/features", json={'name': 'TEST_feat_sync', 'category': 'Frontend', 'price': 0})
    assert r.status_code == 200, r.text
    f = r.json()
    fid = f['id']
    task_id = f.get('task_id')
    assert task_id, "feature must have task_id"
    # PATCH task -> Selesai, feature should be 'Selesai'
    r = s.patch(f"{API}/projects/{PID}/tasks/{task_id}", json={'status': 'Selesai'})
    assert r.status_code == 200
    feats = s.get(f"{API}/projects/{PID}/features").json()
    assert next(x for x in feats if x['id'] == fid)['status'] == 'Selesai'
    # PATCH feature -> Dikerjakan, task should follow
    r = s.patch(f"{API}/projects/{PID}/features/{fid}", json={'status': 'Dikerjakan'})
    assert r.status_code == 200
    tasks = s.get(f"{API}/projects/{PID}/tasks").json()
    assert next(x for x in tasks if x['id'] == task_id)['status'] == 'Dikerjakan'
    # Delete feature deletes task
    r = s.delete(f"{API}/projects/{PID}/features/{fid}")
    assert r.status_code == 200
    tasks = s.get(f"{API}/projects/{PID}/tasks").json()
    assert not any(x['id'] == task_id for x in tasks)


# ---------- Sync: tickets ----------
def test_ticket_creates_task(client_sess, admin):
    cs, _ = client_sess
    ad, _ = admin
    r = cs.post(f"{API}/tickets", json={
        'project_id': PID, 'title': 'TEST_tkt_sync',
        'description': 'test ticket description', 'category': 'Bug / Problem', 'priority': 'Sedang'
    })
    assert r.status_code == 200, r.text
    t = r.json()
    tkt_id = t['id']
    task_id = t.get('task_id')
    assert task_id
    tasks = ad.get(f"{API}/projects/{PID}/tasks").json()
    tt = next((x for x in tasks if x['id'] == task_id), None)
    assert tt and tt['source'] == 'ticket'
    # Reject ticket via admin -> Ditinjau -> Ditolak
    r = ad.patch(f"{API}/tickets/{tkt_id}", json={'status': 'Ditinjau'})
    assert r.status_code == 200
    r = ad.patch(f"{API}/tickets/{tkt_id}", json={'status': 'Ditolak'})
    assert r.status_code == 200
    tasks = ad.get(f"{API}/projects/{PID}/tasks").json()
    assert not any(x['id'] == task_id for x in tasks), "task should be deleted on Ditolak"


def test_backfill_sources_present(adminproject):
    s, _ = adminproject
    tasks = s.get(f"{API}/projects/{PID}/tasks").json()
    sources = {t.get('source') for t in tasks}
    # at least manual + some feature/ticket/etc backfilled if any
    assert 'manual' in sources or len(tasks) > 0
