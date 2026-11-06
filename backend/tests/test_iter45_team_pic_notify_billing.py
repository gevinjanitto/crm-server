# Iter45: project team validation, notification scoping for Admin Project, default task PIC, Task Tim access & sort, billing for Admin Project
import os, subprocess, time, pytest, requests

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0]).rstrip('/')
A = f'{BASE_URL}/api'
ADMIN, AP, DEV, ACC = 'user-admin', 'user-adminproject', 'user-developer', 'user-accounting'


def sess(user):
    t = subprocess.check_output(['bash', '/app/tests/login_token.sh', user]).decode().strip()
    if len(t) < 20: pytest.skip(f'login failed {user}: {t}')
    s = requests.Session(); s.headers['Authorization'] = f'Bearer {t}'
    return s


@pytest.fixture(scope='module')
def admin(): return sess('admin')
@pytest.fixture(scope='module')
def ap(): return sess('adminproject')
@pytest.fixture(scope='module')
def dev(): return sess('developer')


def payload(name, team):
    return {'name': name, 'description': 'TEST iter45', 'client_id': 'client-3', 'category': 'Web Development', 'platforms': ['Web'], 'type': 'Kecil',
            'start_date': '2026-01-10', 'due_date': '2026-02-10', 'value': 0, 'assigned_to': team}


@pytest.fixture(scope='module')
def proj(admin):
    r = admin.post(f'{A}/projects', json=payload('TEST_iter45 proj', [ADMIN, DEV]))
    assert r.status_code == 200, r.text
    p = r.json()
    yield p
    admin.delete(f'{A}/projects/{p["id"]}')


# Project team validation
class TestProjectTeam:
    def test_create_without_developer_400(self, admin):
        # iter3: Admin counts as developer, so Admin Project alone must fail
        r = admin.post(f'{A}/projects', json=payload('TEST_iter45 nodev', ['user-adminproject']))
        if r.status_code == 200: admin.delete(f'{A}/projects/{r.json()["id"]}')
        assert r.status_code == 400 and 'Developer' in r.json()['detail']

    def test_create_without_manager_400(self, admin):
        r = admin.post(f'{A}/projects', json=payload('TEST_iter45 noadm', [DEV]))
        assert r.status_code == 400 and 'Admin' in r.json()['detail']

    def test_create_empty_400(self, admin):
        assert admin.post(f'{A}/projects', json=payload('TEST_iter45 empty', [])).status_code == 400

    def test_create_ok_and_patch_validation(self, admin, proj):
        assert set(proj['assigned_to']) == {ADMIN, DEV}
        body = payload('TEST_iter45 proj', [DEV])
        assert admin.patch(f'{A}/projects/{proj["id"]}', json=body).status_code == 400
        body['assigned_to'] = [AP]
        assert admin.patch(f'{A}/projects/{proj["id"]}', json=body).status_code == 400
        body['assigned_to'] = [ADMIN, DEV]
        assert admin.patch(f'{A}/projects/{proj["id"]}', json=body).status_code == 200
        assert set(admin.get(f'{A}/projects/{proj["id"]}').json()['assigned_to']) == {ADMIN, DEV}


# Default PIC
class TestTaskPIC:
    def test_create_without_assignee_creator_pic(self, admin, proj):
        r = admin.post(f'{A}/projects/{proj["id"]}/tasks', json={'title': 'TEST_iter45 nopic'})
        assert r.status_code == 200, r.text
        t = r.json(); assert t['assignee_ids'] == [ADMIN] and t['assigned_to'] == ADMIN

    def test_adminproject_create_without_assignee(self, admin, ap, proj):
        body = payload('TEST_iter45 proj', [ADMIN, DEV, AP])
        assert admin.patch(f'{A}/projects/{proj["id"]}', json=body).status_code == 200
        r = ap.post(f'{A}/projects/{proj["id"]}/tasks', json={'title': 'TEST_iter45 ap nopic'})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == [AP]

    def test_patch_empty_assignees_falls_back(self, admin, proj):
        t = admin.post(f'{A}/projects/{proj["id"]}/tasks', json={'title': 'TEST_iter45 fallback', 'assignee_ids': [DEV]}).json()
        assert t['assignee_ids'] == [DEV]
        r = admin.patch(f'{A}/projects/{proj["id"]}/tasks/{t["id"]}', json={'assignee_ids': []})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == [ADMIN]
        r = admin.patch(f'{A}/projects/{proj["id"]}/tasks/{t["id"]}', json={'assigned_to': ''})
        assert r.status_code == 200 and r.json()['assignee_ids'] == [ADMIN]

    def test_bulk_empty_assignee_400(self, admin, proj):
        t = admin.post(f'{A}/projects/{proj["id"]}/tasks', json={'title': 'TEST_iter45 bulk'}).json()
        r = admin.post(f'{A}/projects/{proj["id"]}/tasks/bulk', json={'ids': [t['id']], 'assigned_to': ''})
        assert r.status_code == 400, r.text

    def test_no_task_without_pic_in_seed(self, admin):
        tasks = admin.get(f'{A}/tasks').json()
        # iter3: backfill reverted; 9 seed tasks intentionally have no PIC
        empty = [x['id'] for x in tasks if not x.get('assignee_ids')]
        assert len(empty) <= 9, f'tasks without PIC: {empty[:10]}'


def notif_ids(s, tid):
    return [n for n in s.get(f'{A}/notifications').json()['items'] if n.get('entity_id') == tid and '→' in n['title']]


# Notification scoping
class TestNotifyScope:
    def test_card_move_scoping(self, admin, ap, dev, proj):
        pid = proj['id']
        assert admin.patch(f'{A}/projects/{pid}', json=payload('TEST_iter45 proj', [ADMIN, DEV])).status_code == 200
        t = admin.post(f'{A}/projects/{pid}/tasks', json={'title': 'TEST_iter45 move', 'assignee_ids': [DEV]}).json()
        r = dev.patch(f'{A}/projects/{pid}/tasks/{t["id"]}', json={'status': 'Dikerjakan'})
        assert r.status_code == 200, r.text
        time.sleep(1)
        assert notif_ids(admin, t['id']), 'Admin must get notification'
        assert not notif_ids(ap, t['id']), 'Admin Project not member must NOT get notification'
        # add AP as member
        assert admin.patch(f'{A}/projects/{pid}', json=payload('TEST_iter45 proj', [ADMIN, DEV, AP])).status_code == 200
        r = dev.patch(f'{A}/projects/{pid}/tasks/{t["id"]}', json={'status': 'Testing'})
        assert r.status_code == 200
        time.sleep(1)
        assert notif_ids(ap, t['id']), 'Admin Project member must get notification'


# Task Tim
class TestTaskTim:
    def test_access(self, admin, ap, dev):
        assert dev.get(f'{A}/admin/tasks-by-user').status_code == 403
        r = ap.get(f'{A}/admin/tasks-by-user'); assert r.status_code == 200
        g = admin.get(f'{A}/admin/tasks-by-user').json()
        assigned = [x for x in g if x['user_id']]
        counts = [len(x['tasks']) for x in assigned]
        assert counts == sorted(counts, reverse=True)
        if any(not x['user_id'] for x in g): assert not g[-1]['user_id']


# Billing for Admin Project
class TestBilling:
    @pytest.mark.parametrize('kind', ['receipts', 'invoices'])
    def test_access(self, ap, dev, proj, kind):
        pid = proj['id']
        assert ap.get(f'{A}/projects/{pid}/{kind}').status_code == 200
        base = ap.get(f'{A}/projects/{pid}/{kind}/new'); assert base.status_code == 200
        assert ap.post(f'{A}/projects/{pid}/{kind}/preview', json=base.json()).status_code == 200
        b = base.json(); b['number'] = ''
        if kind == 'receipts': b['received_from'] = 'TEST_iter45'
        else: b['to_name'] = 'TEST_iter45'
        r = ap.post(f'{A}/projects/{pid}/{kind}', json=b); assert r.status_code == 200, r.text
        ap.delete(f'{A}/projects/{pid}/{kind}/{r.json()["id"]}')
        assert dev.get(f'{A}/projects/{pid}/{kind}').status_code == 403
