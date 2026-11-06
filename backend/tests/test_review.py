"""Backend tests for maintenance kinds, ticket categories, notification settings."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split('\n')[0]
BASE_URL = BASE_URL.rstrip('/')
PWD = 'Maiharta2026!'


def _login(username):
    c = requests.get(f"{BASE_URL}/api/auth/captcha", timeout=15).json()
    q = c['question'].split()
    ans = int(q[0]) + int(q[2]) if q[1] == '+' else int(q[0]) - int(q[2])
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": username, "password": PWD,
        "captcha_id": c['id'], "captcha_answer": str(ans)
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()['token']


@pytest.fixture(scope='module')
def admin_token():
    return _login('admin')


@pytest.fixture(scope='module')
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope='module')
def client_h():
    return {"Authorization": f"Bearer {_login('client')}"}


@pytest.fixture(scope='module')
def client_project_id(client_h):
    r = requests.get(f"{BASE_URL}/api/ticket-projects", headers=client_h, timeout=15)
    assert r.status_code == 200, r.text
    projs = r.json()
    assert projs, "No ticket projects for client"
    return projs[0]['id']


@pytest.fixture(scope='module')
def project_id(admin_h):
    r = requests.get(f"{BASE_URL}/api/projects", headers=admin_h, timeout=15)
    assert r.status_code == 200
    projs = r.json()
    assert len(projs) > 0, "No projects seeded"
    return projs[0]['id']


class TestMaintenanceKinds:
    def test_create_preventive(self, admin_h, project_id):
        r = requests.post(f"{BASE_URL}/api/projects/{project_id}/work/maintenances",
                          headers=admin_h, json={"title": "TEST_Prev", "kind": "Preventive"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get('kind') == 'Preventive'
        assert 'id' in data

    def test_create_support(self, admin_h, project_id):
        r = requests.post(f"{BASE_URL}/api/projects/{project_id}/work/maintenances",
                          headers=admin_h, json={"title": "TEST_Supp", "kind": "Support"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get('kind') == 'Support'

    def test_reject_unknown_kind(self, admin_h, project_id):
        r = requests.post(f"{BASE_URL}/api/projects/{project_id}/work/maintenances",
                          headers=admin_h, json={"title": "TEST_Bogus", "kind": "Bogus"}, timeout=15)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

    def test_list_contains_new(self, admin_h, project_id):
        r = requests.get(f"{BASE_URL}/api/projects/{project_id}/work/maintenances",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        items = r.json()
        kinds = {i.get('kind') for i in items}
        assert 'Preventive' in kinds
        assert 'Support' in kinds


class TestTicketCategories:
    def test_client_create_ticket_preventive(self, client_h, client_project_id):
        r = requests.post(f"{BASE_URL}/api/tickets", headers=client_h,
                          json={"title": "TEST_T_Prev", "description": "testing preventive category creation", "category": "Preventive", "project_id": client_project_id}, timeout=15)
        assert r.status_code in (200, 201), r.text
        assert r.json().get('category') == 'Preventive'

    def test_client_create_ticket_support(self, client_h, client_project_id):
        r = requests.post(f"{BASE_URL}/api/tickets", headers=client_h,
                          json={"title": "TEST_T_Supp", "description": "testing support category creation", "category": "Support", "project_id": client_project_id}, timeout=15)
        assert r.status_code in (200, 201), r.text
        assert r.json().get('category') == 'Support'

    def test_admin_patch_ticket_category_preventive(self, admin_h, client_h, client_project_id):
        r = requests.post(f"{BASE_URL}/api/tickets", headers=client_h,
                          json={"title": "TEST_T_Patch", "description": "testing patch flow for category", "category": "Bug / Problem", "project_id": client_project_id}, timeout=15)
        assert r.status_code in (200, 201), r.text
        tid = r.json()['id']
        r2 = requests.patch(f"{BASE_URL}/api/tickets/{tid}", headers=admin_h,
                            json={"status": "Baru", "category": "Preventive"}, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json().get('category') == 'Preventive'

    def test_reject_bad_category(self, client_h, client_project_id):
        r = requests.post(f"{BASE_URL}/api/tickets", headers=client_h,
                          json={"title": "TEST_T_Bad", "description": "testing invalid category rejection", "category": "Foo", "project_id": client_project_id}, timeout=15)
        assert r.status_code in (400, 422)


class TestNotificationSettings:
    def test_account_notifications_shape(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/account/notifications", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get('email_provider') == 'Gmail via n8n'
        txt = str(data).lower()
        assert 'resend' not in txt
        # no credentials in response
        for k in ('api_key', 'apikey', 'password', 'secret_key', 'access_token', 'bearer'):
            assert k not in txt, f"Found possible secret key '{k}' in response"

    def test_guide_md_served(self):
        r = requests.get(f"{BASE_URL}/panduan-notifikasi.md", timeout=15)
        assert r.status_code == 200
        body = r.text
        assert 'Resend' not in body
        assert 'WAHA' in body or 'waha' in body.lower()

    def test_n8n_workflows_served(self):
        for f in ('n8n-waha-workflow.json', 'n8n-gmail-workflow.json'):
            r = requests.get(f"{BASE_URL}/{f}", timeout=15)
            assert r.status_code == 200, f"{f} -> {r.status_code}"
