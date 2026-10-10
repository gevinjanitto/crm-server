"""Regression tests for auth, role matrix, project, document, ticket, and user flows."""

import os
import re
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENV_VALUES = dotenv_values("/app/backend/.env")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or ENV_VALUES.get("SEED_PASSWORD")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return BASE_URL


@pytest.fixture(scope="session")
def seed_password():
    if not SEED_PASSWORD:
        pytest.skip("SEED_PASSWORD missing from environment/backend .env")
    return SEED_PASSWORD


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def solve_question(question: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", question)]
    return str(sum(nums))


def get_captcha(client, base_url):
    r = client.get(f"{base_url}/api/auth/captcha", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data and "question" in data
    return data


def login(client, base_url, username, password, remember=False):
    c = get_captcha(client, base_url)
    payload = {
        "username": username,
        "password": password,
        "captcha_id": c["id"],
        "captcha_answer": solve_question(c["question"]),
        "remember": remember,
    }
    r = client.post(f"{base_url}/api/auth/login", json=payload, timeout=25)
    return r


@pytest.fixture(scope="session")
def role_tokens(api_client, base_url, seed_password):
    users = ["admin", "adminproject", "developer", "accounting", "client"]
    out = {}
    for username in users:
        r = login(api_client, base_url, username, seed_password)
        assert r.status_code == 200, f"login failed for {username}: {r.text}"
        body = r.json()
        out[username] = {
            "token": body["token"],
            "user": body["user"],
        }
    return out


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# Auth + security core behavior
def test_captcha_and_login_all_5_roles(api_client, base_url, role_tokens):
    c = get_captcha(api_client, base_url)
    assert re.search(r"\d+", c["question"]) is not None
    roles = {v["user"]["role"] for v in role_tokens.values()}
    assert roles == {"Admin", "Admin Project", "Developer", "Accounting", "Client"}


def test_login_wrong_captcha(api_client, base_url, seed_password):
    c = get_captcha(api_client, base_url)
    r = api_client.post(
        f"{base_url}/api/auth/login",
        json={
            "username": "admin",
            "password": seed_password,
            "captcha_id": c["id"],
            "captcha_answer": "999",
            "remember": False,
        },
        timeout=20,
    )
    assert r.status_code == 400
    assert "CAPTCHA" in r.text


def test_login_reused_captcha_rejected(api_client, base_url, seed_password):
    c = get_captcha(api_client, base_url)
    correct = solve_question(c["question"])
    payload = {
        "username": "admin",
        "password": seed_password,
        "captcha_id": c["id"],
        "captcha_answer": correct,
        "remember": False,
    }
    first = api_client.post(f"{base_url}/api/auth/login", json=payload, timeout=20)
    assert first.status_code == 200
    second = api_client.post(f"{base_url}/api/auth/login", json=payload, timeout=20)
    assert second.status_code == 400
    assert "CAPTCHA" in second.text


def test_login_wrong_password(api_client, base_url):
    c = get_captcha(api_client, base_url)
    r = api_client.post(
        f"{base_url}/api/auth/login",
        json={
            "username": "admin",
            "password": "wrong-password-123",
            "captcha_id": c["id"],
            "captcha_answer": solve_question(c["question"]),
            "remember": False,
        },
        timeout=20,
    )
    assert r.status_code == 401
    assert "password" in r.text.lower() or "username" in r.text.lower()


def test_anonymous_protected_api_rejected(api_client, base_url):
    fresh = requests.Session()
    r = fresh.get(f"{base_url}/api/projects", timeout=20)
    assert r.status_code == 401


# Role matrix coverage
def test_client_scope_and_leak_protection(api_client, base_url, role_tokens):
    token = role_tokens["client"]["token"]
    h = auth_headers(token)

    plist = api_client.get(f"{base_url}/api/projects", headers=h, timeout=20)
    assert plist.status_code == 200
    rows = plist.json()
    ids = {p["id"] for p in rows}
    assert ids == {"project-1", "project-6"}
    for p in rows:
        assert "value" not in p
        assert "development_cost" not in p
        assert "server_cost" not in p
        assert "internal_notes" not in p

    detail_own = api_client.get(f"{base_url}/api/projects/project-1", headers=h, timeout=20)
    assert detail_own.status_code == 200
    own = detail_own.json()
    assert "value" not in own and "internal_notes" not in own

    detail_other = api_client.get(f"{base_url}/api/projects/project-2", headers=h, timeout=20)
    assert detail_other.status_code == 404

    costs = api_client.get(f"{base_url}/api/projects/project-1/costs", headers=h, timeout=20)
    assert costs.status_code == 403

    users = api_client.get(f"{base_url}/api/users", headers=h, timeout=20)
    assert users.status_code == 403

    dashboard = api_client.get(f"{base_url}/api/dashboard", headers=h, timeout=20)
    assert dashboard.status_code == 200
    dash = dashboard.json()
    assert "finance" not in dash and "total_value" not in dash
    if dash.get("projects"):
        assert "value" not in dash["projects"][0]


def test_developer_scope_and_restrictions(api_client, base_url, role_tokens):
    token = role_tokens["developer"]["token"]
    h = auth_headers(token)

    projects = api_client.get(f"{base_url}/api/projects", headers=h, timeout=20)
    assert projects.status_code == 200
    ids = {p["id"] for p in projects.json()}
    assert "project-7" not in ids

    unassigned_detail = api_client.get(f"{base_url}/api/projects/project-7", headers=h, timeout=20)
    assert unassigned_detail.status_code == 404

    costs = api_client.get(f"{base_url}/api/projects/project-1/costs", headers=h, timeout=20)
    assert costs.status_code == 403

    final_status = api_client.post(
        f"{base_url}/api/projects/project-1/status",
        headers=h,
        json={"status": "Uploaded to Production", "note": "try-final"},
        timeout=20,
    )
    assert final_status.status_code in [400, 403]


def test_accounting_permissions(api_client, base_url, role_tokens):
    token = role_tokens["accounting"]["token"]
    h = auth_headers(token)

    dashboard = api_client.get(f"{base_url}/api/dashboard", headers=h, timeout=20)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert "finance" in body
    assert all(k in body["finance"] for k in ["value", "development_cost", "server_cost", "profit"])

    users = api_client.get(f"{base_url}/api/users", headers=h, timeout=20)
    assert users.status_code == 403

    tickets = api_client.get(f"{base_url}/api/tickets", headers=h, timeout=20)
    assert tickets.status_code == 403

    costs = api_client.get(f"{base_url}/api/projects/project-1/costs", headers=h, timeout=20)
    assert costs.status_code == 200
    c = costs.json()
    assert "profit" in c


def test_admin_project_finance_isolation(api_client, base_url, role_tokens):
    token = role_tokens["adminproject"]["token"]
    h = auth_headers(token)

    dashboard = api_client.get(f"{base_url}/api/dashboard", headers=h, timeout=20)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert "total_value" in body
    assert "finance" not in body

    detail = api_client.get(f"{base_url}/api/projects/project-1", headers=h, timeout=20)
    assert detail.status_code == 200
    p = detail.json()
    assert "value" in p
    assert "development_cost" not in p and "server_cost" not in p


# Admin create/edit/delete core
def test_admin_client_project_crud_and_date_validation(api_client, base_url, role_tokens):
    token = role_tokens["admin"]["token"]
    h = auth_headers(token)

    suffix = uuid.uuid4().hex[:8]
    client_payload = {
        "name": f"TEST_Client_{suffix}",
        "contact": "TEST Contact",
        "email": f"test-{suffix}@example.com",
        "phone": "+62 811000000",
        "industry": "Testing",
        "address": "Denpasar",
    }
    c_create = api_client.post(f"{base_url}/api/clients", headers=h, json=client_payload, timeout=25)
    assert c_create.status_code == 200
    client_id = c_create.json()["id"]

    c_edit = api_client.patch(
        f"{base_url}/api/clients/{client_id}",
        headers=h,
        json={**client_payload, "name": f"TEST_Client_EDIT_{suffix}"},
        timeout=25,
    )
    assert c_edit.status_code == 200
    assert c_edit.json()["name"].startswith("TEST_Client_EDIT")

    invalid_project = {
        "name": f"TEST_Project_Invalid_{suffix}",
        "client_id": client_id,
        "description": "Invalid date",
        "category": "Web Development",
        "type": "Besar",
        "value": 1000000,
        "start_date": date.today().isoformat(),
        "due_date": (date.today() - timedelta(days=1)).isoformat(),
        "assigned_to": ["user-developer"],
        "internal_notes": "test",
    }
    bad = api_client.post(f"{base_url}/api/projects", headers=h, json=invalid_project, timeout=25)
    assert bad.status_code == 422

    good_project = {
        **invalid_project,
        "name": f"TEST_Project_{suffix}",
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
    }
    created = api_client.post(f"{base_url}/api/projects", headers=h, json=good_project, timeout=25)
    assert created.status_code == 200
    project_id = created.json()["id"]

    deleted = api_client.delete(f"{base_url}/api/projects/{project_id}", headers=h, timeout=25)
    assert deleted.status_code == 200

    remove_client = api_client.delete(f"{base_url}/api/clients/{client_id}", headers=h, timeout=25)
    assert remove_client.status_code == 200


# Documents and storage behavior
def test_document_upload_download_and_validation(api_client, base_url, role_tokens):
    upload_client = requests.Session()
    admin_h = auth_headers(role_tokens["admin"]["token"])
    client_h = auth_headers(role_tokens["client"]["token"])

    txt_bytes = b"TEST_DOC_MAIHARTA_123"
    files = {"file": ("tiny-test.txt", txt_bytes, "text/plain")}
    data = {"kind": "Kontrak", "visibility": "Client"}
    up = upload_client.post(
        f"{base_url}/api/projects/project-1/documents",
        headers={"Authorization": admin_h["Authorization"]},
        files=files,
        data=data,
        timeout=60,
    )
    assert up.status_code == 200
    doc_id = up.json()["id"]

    dl = api_client.get(f"{base_url}/api/projects/project-1/documents/{doc_id}/download", headers=client_h, timeout=40)
    assert dl.status_code == 200
    assert dl.content == txt_bytes

    up_internal = upload_client.post(
        f"{base_url}/api/projects/project-1/documents",
        headers={"Authorization": admin_h["Authorization"]},
        files={"file": ("internal-note.txt", b"INTERNAL_ONLY", "text/plain")},
        data={"kind": "Requirement", "visibility": "Internal"},
        timeout=60,
    )
    assert up_internal.status_code == 200
    internal_id = up_internal.json()["id"]

    list_client = api_client.get(f"{base_url}/api/projects/project-1/documents", headers=client_h, timeout=20)
    assert list_client.status_code == 200
    assert all(d["visibility"] == "Client" for d in list_client.json())

    deny_internal = api_client.get(
        f"{base_url}/api/projects/project-1/documents/{internal_id}/download",
        headers=client_h,
        timeout=30,
    )
    assert deny_internal.status_code == 404

    unsupported = upload_client.post(
        f"{base_url}/api/projects/project-1/documents",
        headers={"Authorization": admin_h["Authorization"]},
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        data={"kind": "Kontrak", "visibility": "Internal"},
        timeout=30,
    )
    assert unsupported.status_code == 400

    big_data = b"A" * (10 * 1024 * 1024 + 1)
    too_big = upload_client.post(
        f"{base_url}/api/projects/project-1/documents",
        headers={"Authorization": admin_h["Authorization"]},
        files={"file": ("big.txt", big_data, "text/plain")},
        data={"kind": "Kontrak", "visibility": "Internal"},
        timeout=90,
    )
    assert too_big.status_code == 400


# Tickets triage and CR approval protections
def test_ticket_triage_and_developer_guardrails(api_client, base_url, role_tokens):
    client_h = auth_headers(role_tokens["client"]["token"])
    dev_h = auth_headers(role_tokens["developer"]["token"])
    ap_h = auth_headers(role_tokens["adminproject"]["token"])

    create = api_client.post(
        f"{base_url}/api/tickets",
        headers=client_h,
        json={
            "project_id": "project-1",
            "title": "TEST Ticket New",
            "description": "TEST tiket untuk verifikasi triase",
            "category": "Change Request",
            "priority": "Sedang",
        },
        timeout=25,
    )
    assert create.status_code == 200
    tid = create.json()["id"]

    dev_try = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=dev_h,
        json={"status": "Dikerjakan"},
        timeout=25,
    )
    assert dev_try.status_code in [403, 404]

    triage = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=ap_h,
        json={"status": "Ditinjau", "category": "Change Request", "assigned_to": "user-developer"},
        timeout=25,
    )
    assert triage.status_code == 200

    need_estimate = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=ap_h,
        json={"status": "Menunggu Estimasi Biaya", "category": "Change Request"},
        timeout=25,
    )
    assert need_estimate.status_code == 200

    no_estimate = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=ap_h,
        json={"status": "Menunggu Persetujuan", "category": "Change Request", "estimate": 0},
        timeout=25,
    )
    assert no_estimate.status_code == 400

    with_estimate = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=ap_h,
        json={"status": "Menunggu Persetujuan", "category": "Change Request", "estimate": 1250000},
        timeout=25,
    )
    assert with_estimate.status_code == 200

    client_approve = api_client.patch(
        f"{base_url}/api/tickets/{tid}",
        headers=client_h,
        json={"status": "Diterima"},
        timeout=25,
    )
    assert client_approve.status_code == 200
    assert client_approve.json().get("approved") is True


# User lifecycle and password flow on disposable account
def test_user_management_and_password_change_disposable(api_client, base_url, role_tokens):
    admin_h = auth_headers(role_tokens["admin"]["token"])
    suffix = uuid.uuid4().hex[:8]

    create_payload = {
        "name": f"TEST User {suffix}",
        "username": f"testuser_{suffix}",
        "email": f"testuser_{suffix}@example.com",
        "password": "TempPass1234",
        "role": "Developer",
        "client_id": "",
    }
    created = api_client.post(f"{base_url}/api/users", headers=admin_h, json=create_payload, timeout=25)
    assert created.status_code == 200
    user_id = created.json()["id"]

    update_role = api_client.patch(
        f"{base_url}/api/users/{user_id}",
        headers=admin_h,
        json={"role": "Accounting"},
        timeout=25,
    )
    assert update_role.status_code == 200
    assert update_role.json()["role"] == "Accounting"

    self_demotion = api_client.patch(
        f"{base_url}/api/users/user-admin",
        headers=admin_h,
        json={"role": "Developer"},
        timeout=25,
    )
    assert self_demotion.status_code == 400

    u_login = login(api_client, base_url, create_payload["username"], create_payload["password"])
    assert u_login.status_code == 200
    token = u_login.json()["token"]

    pw_change = api_client.post(
        f"{base_url}/api/auth/password",
        headers=auth_headers(token),
        json={"current_password": "TempPass1234", "new_password": "TempPass5678"},
        timeout=25,
    )
    assert pw_change.status_code == 200

    relogin_old = login(api_client, base_url, create_payload["username"], "TempPass1234")
    assert relogin_old.status_code == 401
    relogin_new = login(api_client, base_url, create_payload["username"], "TempPass5678")
    assert relogin_new.status_code == 200

    deactivate = api_client.patch(
        f"{base_url}/api/users/{user_id}",
        headers=admin_h,
        json={"active": False},
        timeout=25,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["active"] is False


# Additional workflow, export, and isolation checks
def test_client_forbidden_cross_client_ticket(api_client, base_url, role_tokens):
    client_h = auth_headers(role_tokens["client"]["token"])
    r = api_client.post(
        f"{base_url}/api/tickets",
        headers=client_h,
        json={
            "project_id": "project-2",
            "title": "TEST cross client",
            "description": "Mencoba tiket di project client lain",
            "category": "Bug / Problem",
            "priority": "Sedang",
        },
        timeout=25,
    )
    assert r.status_code == 404


def test_workflow_development_requires_four_documents(api_client, base_url, role_tokens):
    admin_h = auth_headers(role_tokens["admin"]["token"])
    upload_client = requests.Session()
    suffix = uuid.uuid4().hex[:8]

    c_payload = {
        "name": f"TEST_WF_Client_{suffix}",
        "contact": "WF Contact",
        "email": f"wf-{suffix}@example.com",
        "phone": "+62 811111111",
        "industry": "Testing",
        "address": "Bali",
    }
    c_create = api_client.post(f"{base_url}/api/clients", headers=admin_h, json=c_payload, timeout=25)
    assert c_create.status_code == 200
    cid = c_create.json()["id"]

    p_payload = {
        "name": f"TEST_WF_Project_{suffix}",
        "client_id": cid,
        "description": "workflow test",
        "platforms": ["Web"],
        "type": "Besar",
        "value": 2000000,
        "start_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "assigned_to": ["user-developer"],
        "internal_notes": "wf",
    }
    p_create = api_client.post(f"{base_url}/api/projects", headers=admin_h, json=p_payload, timeout=25)
    assert p_create.status_code == 200
    pid = p_create.json()["id"]

    for st in ["Follow Up", "Dokumen Disiapkan", "Scope Dirinci", "UI/UX", "Disetujui"]:
        move = api_client.post(
            f"{base_url}/api/projects/{pid}/status",
            headers=admin_h,
            json={"status": st, "note": "wf"},
            timeout=25,
        )
        assert move.status_code == 200

    blocked = api_client.post(
        f"{base_url}/api/projects/{pid}/status",
        headers=admin_h,
        json={"status": "Development", "note": "wf"},
        timeout=25,
    )
    assert blocked.status_code == 400

    required_kinds = ["Kontrak", "Requirement", "Rincian Fitur", "Timeline"]
    for kind in required_kinds:
        up = upload_client.post(
            f"{base_url}/api/projects/{pid}/documents",
            headers={"Authorization": admin_h["Authorization"]},
            files={"file": (f"{kind}.txt", b"WF_DOC", "text/plain")},
            data={"kind": kind, "visibility": "Internal"},
            timeout=60,
        )
        assert up.status_code == 200

    allowed = api_client.post(
        f"{base_url}/api/projects/{pid}/status",
        headers=admin_h,
        json={"status": "Development", "note": "wf"},
        timeout=25,
    )
    assert allowed.status_code == 200

    cleanup_p = api_client.delete(f"{base_url}/api/projects/{pid}", headers=admin_h, timeout=25)
    assert cleanup_p.status_code in [200, 400]
    cleanup_c = api_client.delete(f"{base_url}/api/clients/{cid}", headers=admin_h, timeout=25)
    assert cleanup_c.status_code in [200, 400]


def test_maintenance_and_deployment_restrictions(api_client, base_url, role_tokens):
    ap_h = auth_headers(role_tokens["adminproject"]["token"])
    admin_h = auth_headers(role_tokens["admin"]["token"])
    dev_h = auth_headers(role_tokens["developer"]["token"])

    before_prod = api_client.post(
        f"{base_url}/api/projects/project-1/work/maintenances",
        headers=ap_h,
        json={
            "title": "TEST maintenance pre-prod",
            "description": "maintenance should fail pre-production",
            "kind": "Corrective",
            "assigned_to": "user-developer",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "estimate": 0,
        },
        timeout=25,
    )
    assert before_prod.status_code == 400

    prod_ok = api_client.post(
        f"{base_url}/api/projects/project-4/work/maintenances",
        headers=ap_h,
        json={
            "title": "TEST maintenance prod",
            "description": "maintenance allowed",
            "kind": "Adaptive",
            "assigned_to": "user-developer",
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
            "estimate": 0,
        },
        timeout=25,
    )
    assert prod_ok.status_code == 200
    assert prod_ok.json().get("completed_at") is None

    dev_prod_deploy = api_client.post(
        f"{base_url}/api/projects/project-4/deployments",
        headers=dev_h,
        json={
            "environment": "Production",
            "url": "https://example.com/prod",
            "version": "v-test-dev",
            "notes": "developer should be blocked",
        },
        timeout=25,
    )
    assert dev_prod_deploy.status_code == 403

    admin_prod_deploy = api_client.post(
        f"{base_url}/api/projects/project-4/deployments",
        headers=admin_h,
        json={
            "environment": "Production",
            "url": "https://example.com/prod-admin",
            "version": "v-test-admin",
            "notes": "admin allowed",
        },
        timeout=25,
    )
    assert admin_prod_deploy.status_code == 200


def test_csv_role_data_isolation(api_client, base_url, role_tokens):
    client_h = auth_headers(role_tokens["client"]["token"])
    accounting_h = auth_headers(role_tokens["accounting"]["token"])

    client_csv = api_client.get(f"{base_url}/api/reports/projects.csv", headers=client_h, timeout=30)
    assert client_csv.status_code == 200
    assert "Nilai Project" not in client_csv.text
    assert "Biaya Development" not in client_csv.text

    accounting_csv = api_client.get(f"{base_url}/api/reports/projects.csv", headers=accounting_h, timeout=30)
    assert accounting_csv.status_code == 200
    assert "Nilai Project" in accounting_csv.text
    assert "Biaya Development" in accounting_csv.text


def test_ticket_comment_internal_visibility(api_client, base_url, role_tokens):
    ap_h = auth_headers(role_tokens["adminproject"]["token"])
    client_h = auth_headers(role_tokens["client"]["token"])

    t_create = api_client.post(
        f"{base_url}/api/tickets",
        headers=client_h,
        json={
            "project_id": "project-1",
            "title": "TEST internal visibility",
            "description": "Verifikasi komentar internal tidak terlihat client",
            "category": "Bug / Problem",
            "priority": "Sedang",
        },
        timeout=25,
    )
    assert t_create.status_code == 200
    tid = t_create.json()["id"]

    internal_comment = api_client.post(
        f"{base_url}/api/tickets/{tid}/comments",
        headers=ap_h,
        json={"message": "Catatan internal QA", "internal": True},
        timeout=25,
    )
    assert internal_comment.status_code == 200

    public_comment = api_client.post(
        f"{base_url}/api/tickets/{tid}/comments",
        headers=ap_h,
        json={"message": "Update publik untuk client", "internal": False},
        timeout=25,
    )
    assert public_comment.status_code == 200

    c_view = api_client.get(f"{base_url}/api/tickets/{tid}/comments", headers=client_h, timeout=25)
    assert c_view.status_code == 200
    comments = c_view.json()
    assert all(c.get("internal") is False for c in comments)
    assert any("publik" in c.get("message", "").lower() for c in comments)


def test_feature_progress_and_cost_profit_update(api_client, base_url, role_tokens):
    admin_h = auth_headers(role_tokens["admin"]["token"])
    ap_h = auth_headers(role_tokens["adminproject"]["token"])
    dev_h = auth_headers(role_tokens["developer"]["token"])

    suffix = uuid.uuid4().hex[:8]
    c_create = api_client.post(
        f"{base_url}/api/clients",
        headers=admin_h,
        json={
            "name": f"TEST_FP_Client_{suffix}",
            "contact": "Feature Progress",
            "email": f"fp-{suffix}@example.com",
            "phone": "+62 812300000",
            "industry": "Testing",
            "address": "Bali",
        },
        timeout=25,
    )
    assert c_create.status_code == 200
    cid = c_create.json()["id"]

    p_create = api_client.post(
        f"{base_url}/api/projects",
        headers=ap_h,
        json={
            "name": f"TEST_FP_Project_{suffix}",
            "client_id": cid,
            "description": "feature test",
            "category": "Web Development",
            "type": "Besar",
            "value": 5000000,
            "start_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=21)).isoformat(),
            "assigned_to": ["user-developer"],
            "internal_notes": "fp",
        },
        timeout=25,
    )
    assert p_create.status_code == 200
    pid = p_create.json()["id"]

    f1 = api_client.post(
        f"{base_url}/api/projects/{pid}/features",
        headers=ap_h,
        json={"name": "Feature A", "category": "Frontend", "price": 100000, "assigned_to": "user-developer"},
        timeout=25,
    )
    f2 = api_client.post(
        f"{base_url}/api/projects/{pid}/features",
        headers=ap_h,
        json={"name": "Feature B", "category": "Backend", "price": 120000, "assigned_to": "user-developer"},
        timeout=25,
    )
    assert f1.status_code == 200 and f2.status_code == 200

    done_one = api_client.patch(
        f"{base_url}/api/projects/{pid}/features/{f1.json()['id']}",
        headers=dev_h,
        json={"status": "Selesai"},
        timeout=25,
    )
    assert done_one.status_code == 200

    p_mid = api_client.get(f"{base_url}/api/projects/{pid}", headers=ap_h, timeout=20)
    assert p_mid.status_code == 200
    assert p_mid.json().get("progress") == 50

    done_two = api_client.patch(
        f"{base_url}/api/projects/{pid}/features/{f2.json()['id']}",
        headers=dev_h,
        json={"status": "Selesai"},
        timeout=25,
    )
    assert done_two.status_code == 200

    p_done = api_client.get(f"{base_url}/api/projects/{pid}", headers=ap_h, timeout=20)
    assert p_done.status_code == 200
    assert p_done.json().get("progress") == 100

    c_update = api_client.post(
        f"{base_url}/api/projects/{pid}/costs",
        headers=admin_h,
        json={"development_cost": 2000000, "server_cost": 500000},
        timeout=25,
    )
    assert c_update.status_code == 200
    costs = c_update.json()
    assert costs["profit"] == 2500000

    api_client.delete(f"{base_url}/api/projects/{pid}", headers=ap_h, timeout=25)
    api_client.delete(f"{base_url}/api/clients/{cid}", headers=admin_h, timeout=25)


def test_revision_out_of_scope_needs_estimate_and_approval(api_client, base_url, role_tokens):
    ap_h = auth_headers(role_tokens["adminproject"]["token"])

    create = api_client.post(
        f"{base_url}/api/projects/project-8/work/revisions",
        headers=ap_h,
        json={
            "title": "TEST out of scope revision",
            "description": "harus butuh estimasi & approval",
            "kind": "Out-of-scope",
            "assigned_to": "user-developer",
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
            "estimate": 0,
        },
        timeout=25,
    )
    assert create.status_code == 200
    rid = create.json()["id"]

    blocked = api_client.patch(
        f"{base_url}/api/projects/project-8/work/revisions/{rid}",
        headers=ap_h,
        json={"status": "Dikerjakan", "approved": False},
        timeout=25,
    )
    assert blocked.status_code == 400

    approve = api_client.patch(
        f"{base_url}/api/projects/project-8/work/revisions/{rid}",
        headers=ap_h,
        json={"status": "Dikerjakan", "approved": True},
        timeout=25,
    )
    assert approve.status_code == 400

