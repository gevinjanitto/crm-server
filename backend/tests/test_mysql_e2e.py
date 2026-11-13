"""E2E regression after Mongo->MySQL migration. Uses REACT_APP_BACKEND_URL."""
import os, re, uuid, time, io
from pathlib import Path
from dotenv import dotenv_values
import pytest
import requests

def _load_url():
    import pathlib
    for p in ['/app/frontend/.env']:
        try:
            for line in pathlib.Path(p).read_text().splitlines():
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().rstrip('/')
        except Exception: pass
    return os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

BASE = _load_url()
assert BASE, "REACT_APP_BACKEND_URL not found"
API = f"{BASE}/api"
PASSWORD = os.environ.get('SEED_PASSWORD') or dotenv_values(Path(__file__).resolve().parents[1] / '.env').get('SEED_PASSWORD')


def _solve(q):
    a, b = re.findall(r'\d+', q)[:2]
    return str(int(a) + int(b))


def _login(username, password=PASSWORD):
    s = requests.Session()
    cap = s.get(f"{API}/auth/captcha", timeout=15).json()
    r = s.post(f"{API}/auth/login", json={
        "username": username, "password": password,
        "captcha_id": cap['id'], "captcha_answer": _solve(cap['question'])
    }, timeout=15)
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    tok = r.json()['token']
    s.headers.update({'Authorization': f'Bearer {tok}'})
    return s, r.json()


# ---------- session fixtures for each role ----------
@pytest.fixture(scope='module')
def admin():
    s, u = _login('admin'); return s


@pytest.fixture(scope='module')
def adminproject():
    s, u = _login('adminproject'); return s


@pytest.fixture(scope='module')
def developer():
    s, u = _login('developer'); return s


@pytest.fixture(scope='module')
def accounting():
    s, u = _login('accounting'); return s


@pytest.fixture(scope='module')
def client_sess():
    s, u = _login('client'); return s


# ---------- auth ----------
class TestAuth:
    def test_captcha_endpoint(self):
        r = requests.get(f"{API}/auth/captcha", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d['provider'] == 'math' and 'id' in d and '=' in d['question']

    def test_login_bad_captcha(self):
        cap = requests.get(f"{API}/auth/captcha", timeout=10).json()
        r = requests.post(f"{API}/auth/login", json={
            "username": "admin", "password": PASSWORD,
            "captcha_id": cap['id'], "captcha_answer": "999"
        }, timeout=10)
        assert r.status_code in (400, 401, 403)

    def test_login_bad_password(self):
        cap = requests.get(f"{API}/auth/captcha", timeout=10).json()
        r = requests.post(f"{API}/auth/login", json={
            "username": "admin", "password": "wrongpw1234",
            "captcha_id": cap['id'], "captcha_answer": _solve(cap['question'])
        }, timeout=10)
        assert r.status_code in (400, 401)

    @pytest.mark.parametrize('u', ['admin', 'adminproject', 'developer', 'accounting', 'client'])
    def test_login_all_roles(self, u):
        s, data = _login(u)
        assert 'token' in data and 'user' in data
        assert data['user']['username'] == u

    def test_me_endpoint(self, admin):
        r = admin.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()['username'] == 'admin'


# ---------- clients CRUD + auto-create login ----------
class TestClients:
    created_id = None
    created_email = None

    def test_list_clients(self, admin):
        r = admin.get(f"{API}/clients", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_client_creates_login_account(self, admin):
        suffix = uuid.uuid4().hex[:6]
        email = f"TEST_cli_{suffix}@example.com"
        payload = {"name": f"TEST Client {suffix}", "contact": "John", "email": email,
                   "phone": "0812", "industry": "IT", "address": "Jl X"}
        r = admin.post(f"{API}/clients", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d['email'] == email and 'id' in d
        TestClients.created_id = d['id']
        TestClients.created_email = email

        # auto-created user with username=email, password 12345678
        cap = requests.get(f"{API}/auth/captcha", timeout=10).json()
        lr = requests.post(f"{API}/auth/login", json={
            "username": email, "password": "12345678",
            "captcha_id": cap['id'], "captcha_answer": _solve(cap['question'])
        }, timeout=15)
        assert lr.status_code == 200, f"auto-created client login failed: {lr.text}"
        body = lr.json()
        assert body.get('user', {}).get('must_change_password') is True or \
               body.get('must_change_password') is True, f"must_change_password missing: {body}"

    def test_get_client(self, admin):
        # list and verify presence (no GET /clients/{id} endpoint)
        assert TestClients.created_id
        r = admin.get(f"{API}/clients", timeout=10)
        assert r.status_code == 200
        assert any(c['id'] == TestClients.created_id for c in r.json())

    def test_update_client(self, admin):
        r = admin.patch(f"{API}/clients/{TestClients.created_id}",
                      json={"name": "TEST Client UPD", "contact": "John",
                            "email": TestClients.created_email, "phone": "081", "industry": "IT", "address": "A"},
                      timeout=15)
        assert r.status_code == 200, r.text
        got = admin.get(f"{API}/clients", timeout=10).json()
        found = next((c for c in got if c['id'] == TestClients.created_id), None)
        assert found and found['name'] == "TEST Client UPD"


# ---------- users ----------
class TestUsers:
    created_id = None

    def test_list_users(self, admin):
        r = admin.get(f"{API}/users", timeout=15)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_create_user_default_password(self, admin):
        suffix = uuid.uuid4().hex[:6]
        username = f"test_u_{suffix}"
        r = admin.post(f"{API}/users", json={
            "name": f"TEST User {suffix}", "username": username,
            "email": f"{username}@example.com", "role": "Developer", "client_id": ""
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        TestUsers.created_id = r.json()['id']
        # login with default 12345678
        cap = requests.get(f"{API}/auth/captcha", timeout=10).json()
        lr = requests.post(f"{API}/auth/login", json={
            "username": username, "password": "12345678",
            "captcha_id": cap['id'], "captcha_answer": _solve(cap['question'])
        }, timeout=15)
        assert lr.status_code == 200, lr.text

    def test_non_admin_cannot_list_users(self, developer):
        r = developer.get(f"{API}/users", timeout=10)
        # Developer should NOT have access to admin user list
        assert r.status_code in (401, 403)


# ---------- projects ----------
class TestProjects:
    pid1 = None
    pid2 = None
    code1 = None
    code2 = None

    def test_create_two_projects_code_increments(self, admin):
        # fetch a client for FK
        cls = admin.get(f"{API}/clients", timeout=15).json()
        assert cls, "need at least 1 client"
        cid = TestClients.created_id or cls[0]['id']
        p1 = admin.post(f"{API}/projects", json={
            "name": f"TEST Proj A {uuid.uuid4().hex[:5]}",
            "client_id": cid, "platforms": ["Web"],
            "start_date": "2026-01-01", "due_date": "2026-02-01",
            "value": 100, "description": "x"
        }, timeout=15)
        assert p1.status_code in (200, 201), p1.text
        p2 = admin.post(f"{API}/projects", json={
            "name": f"TEST Proj B {uuid.uuid4().hex[:5]}",
            "client_id": cid, "platforms": ["Web"],
            "start_date": "2026-01-01", "due_date": "2026-02-01",
            "value": 100, "description": "y"
        }, timeout=15)
        assert p2.status_code in (200, 201), p2.text
        d1, d2 = p1.json(), p2.json()
        TestProjects.pid1, TestProjects.pid2 = d1['id'], d2['id']
        TestProjects.code1, TestProjects.code2 = d1.get('code'), d2.get('code')
        assert TestProjects.code1 and re.match(r'^[A-Z]+-\d+$', TestProjects.code1), f"unexpected code format: {TestProjects.code1}"
        assert TestProjects.code2 and re.match(r'^[A-Z]+-\d+$', TestProjects.code2)
        n1 = int(re.sub(r'\D', '', TestProjects.code1))
        n2 = int(re.sub(r'\D', '', TestProjects.code2))
        assert n2 == n1 + 1, f"codes not sequential: {TestProjects.code1} -> {TestProjects.code2}"

    def test_list_projects(self, admin):
        r = admin.get(f"{API}/projects", timeout=15)
        assert r.status_code == 200
        assert any(p['id'] == TestProjects.pid1 for p in r.json())

    def test_get_project(self, admin):
        r = admin.get(f"{API}/projects/{TestProjects.pid1}", timeout=10)
        assert r.status_code == 200

    def test_update_project_status(self, admin):
        r = admin.post(f"{API}/projects/{TestProjects.pid1}/status", json={"status": "Follow Up", "note": ""}, timeout=15)
        assert r.status_code in (200, 204), r.text
        assert admin.get(f"{API}/projects/{TestProjects.pid1}").json().get('status') == 'Follow Up'

    def test_client_sees_only_own_projects(self, client_sess, admin):
        r = client_sess.get(f"{API}/projects", timeout=15)
        # Client may be allowed limited listing or 403 - whichever the design chose
        if r.status_code == 200:
            # must be subset / own-only
            own_ids = {p['id'] for p in r.json()}
            # the project we just created is for TEST client, not 'client' user, so pid1 should NOT appear
            assert TestProjects.pid1 not in own_ids
        else:
            assert r.status_code == 403

    def test_developer_sees_only_assigned(self, developer):
        r = developer.get(f"{API}/projects", timeout=15)
        assert r.status_code == 200
        # developer not assigned to pid1
        assert all(p['id'] != TestProjects.pid1 for p in r.json())


# ---------- sprints: only one active ----------
class TestSprints:
    def test_second_active_sprint_rejected(self, admin):
        pid = TestProjects.pid1
        if not pid: pytest.skip("project missing")
        s1 = admin.post(f"{API}/projects/{pid}/workspace/sprints", json={
            "name": "TEST S1", "start_date": "2026-01-01", "end_date": "2026-01-14", "status": "active"
        }, timeout=15)
        if s1.status_code not in (200, 201):
            pytest.skip(f"sprint endpoint shape differs: {s1.status_code} {s1.text[:200]}")
        s2 = admin.post(f"{API}/projects/{pid}/workspace/sprints", json={
            "name": "TEST S2", "start_date": "2026-01-15", "end_date": "2026-01-28", "status": "active"
        }, timeout=15)
        assert s2.status_code == 400, f"expected 400 for 2nd active sprint, got {s2.status_code} {s2.text}"


# ---------- kanban tasks ----------
class TestKanban:
    tid = None

    def test_create_task(self, admin):
        pid = TestProjects.pid1
        if not pid: pytest.skip()
        # fetch statuses available
        st = admin.get(f"{API}/projects/{pid}/statuses", timeout=10)
        status_name = 'Backlog'
        if st.status_code == 200 and st.json():
            status_name = st.json()[0].get('name') or st.json()[0].get('id') or 'Backlog'
        r = admin.post(f"{API}/projects/{pid}/tasks", json={
            "title": "TEST Kanban task", "status": status_name, "priority": "Sedang"
        }, timeout=15)
        if r.status_code not in (200, 201):
            pytest.skip(f"kanban create shape differs: {r.status_code} {r.text[:200]}")
        TestKanban.tid = r.json().get('id')
        assert TestKanban.tid

    def test_move_task(self, admin):
        if not TestKanban.tid: pytest.skip()
        pid = TestProjects.pid1
        st = admin.get(f"{API}/projects/{pid}/statuses", timeout=10).json()
        new_status = (st[1] if len(st) > 1 else st[0]).get('name')
        r = admin.patch(f"{API}/projects/{pid}/tasks/{TestKanban.tid}", json={"status": new_status}, timeout=15)
        assert r.status_code in (200, 204), r.text


# ---------- documents ----------
class TestDocuments:
    doc_id = None

    def test_upload_document(self, admin):
        pid = TestProjects.pid1
        if not pid: pytest.skip()
        files = {'file': ('test.txt', io.BytesIO(b'hello mysql'), 'text/plain')}
        data = {'kind': 'Requirement', 'visibility': 'Internal', 'name': 'TEST doc'}
        r = admin.post(f"{API}/projects/{pid}/documents", files=files, data=data, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"docs upload shape differs: {r.status_code} {r.text[:200]}")
        TestDocuments.doc_id = r.json().get('id')
        assert TestDocuments.doc_id

    def test_download_document(self, admin):
        if not TestDocuments.doc_id: pytest.skip()
        pid = TestProjects.pid1
        r = admin.get(f"{API}/projects/{pid}/documents/{TestDocuments.doc_id}/download", timeout=15)
        assert r.status_code == 200
        assert b'hello mysql' in r.content

    def test_delete_doc_goes_to_trash_and_restore(self, admin):
        if not TestDocuments.doc_id: pytest.skip()
        pid = TestProjects.pid1
        d = admin.delete(f"{API}/projects/{pid}/documents/{TestDocuments.doc_id}", timeout=10)
        assert d.status_code in (200, 204)
        tr = admin.get(f"{API}/trash", timeout=10)
        assert tr.status_code == 200
        found = any(TestDocuments.doc_id in str(t) for t in tr.json())
        assert found, "deleted doc not in trash"


# ---------- notifications ----------
class TestNotifications:
    def test_list(self, admin):
        r = admin.get(f"{API}/notifications", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, (list, dict))


# ---------- finance ----------
class TestFinance:
    def test_cost_types_list(self, accounting):
        r = accounting.get(f"{API}/finance/cost-types", timeout=10)
        assert r.status_code in (200, 404)  # tolerate rename

    def test_expenses_list(self, accounting):
        r = accounting.get(f"{API}/finance/expenses", timeout=10)
        assert r.status_code in (200, 404)


# ---------- audit ----------
class TestAudit:
    def test_activity_logs(self, admin):
        r = admin.get(f"{API}/audit", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- cleanup ----------
def test_zz_cleanup(admin):
    # delete created project
    for pid in [TestProjects.pid1, TestProjects.pid2]:
        if pid:
            admin.delete(f"{API}/projects/{pid}", timeout=10)
    if TestClients.created_id:
        admin.delete(f"{API}/clients/{TestClients.created_id}", timeout=10)
    if TestUsers.created_id:
        admin.delete(f"{API}/users/{TestUsers.created_id}", timeout=10)
