"""Iteration 26 regression: roles, tickets/maintenance, documents, notifications, ClickUp import."""

import io
import os
import re
import time
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


# Module: environment and auth helpers
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or BACKEND_ENV.get("SEED_PASSWORD")


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question or "")))


def _login(username: str) -> tuple[requests.Session, dict]:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    cap = session.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    cap_data = cap.json()
    auth = session.post(
        f"{API}/auth/login",
        json={
            "username": username,
            "password": SEED_PASSWORD,
            "captcha_id": cap_data.get("id", ""),
            "captcha_answer": _solve(cap_data.get("question", "")),
            "remember": False,
        },
        timeout=30,
    )
    assert auth.status_code == 200, f"login failed for {username}: {auth.status_code} {auth.text}"
    token = auth.json()["token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, auth.json()["user"]


def _multipart_post(session: requests.Session, url: str, *, data=None, files=None, timeout=40):
    headers = {k: v for k, v in session.headers.items() if k.lower() != "content-type"}
    return requests.post(url, headers=headers, cookies=session.cookies, data=data, files=files, timeout=timeout)


@pytest.fixture(scope="module")
def actors():
    admin = _login("admin")
    adminproject = _login("adminproject")
    developer = _login("developer")
    accounting = _login("accounting")
    client = _login("client")
    return {
        "admin": admin,
        "adminproject": adminproject,
        "developer": developer,
        "accounting": accounting,
        "client": client,
    }


# Module: role matrix for /team and reusable project membership
def test_team_endpoint_returns_only_internal_active_roles(actors):
    for role in ["admin", "adminproject"]:
        session, _ = actors[role]
        resp = session.get(f"{API}/team", timeout=20)
        assert resp.status_code == 200
        rows = resp.json()
        assert rows, "team list should not be empty"
        assert all(r.get("role") in ["Admin", "Admin Project", "Developer"] for r in rows)
        assert all(r.get("role") not in ["Accounting", "Client"] for r in rows)


def test_team_endpoint_forbidden_for_non_manager_roles(actors):
    for role in ["developer", "accounting", "client"]:
        session, _ = actors[role]
        resp = session.get(f"{API}/team", timeout=20)
        assert resp.status_code == 403


def test_same_developer_can_be_reused_across_two_new_projects(actors):
    admin_session, _ = actors["admin"]
    developer_session, developer_user = actors["developer"]

    clients = admin_session.get(f"{API}/clients", timeout=20)
    assert clients.status_code == 200
    client_id = clients.json()[0]["id"]

    start = date.today() + timedelta(days=1)
    due = start + timedelta(days=21)
    suffix = uuid.uuid4().hex[:6]
    created_ids = []
    for i in [1, 2]:
        payload = {
            "name": f"TEST_ITER26_REUSE_DEV_{suffix}_{i}",
            "client_id": client_id,
            "description": "membership reuse check",
            "platforms": ["Web"],
            "type": "Kecil",
            "value": 0,
            "start_date": start.isoformat(),
            "due_date": due.isoformat(),
            "assigned_to": [developer_user["id"]],
            "internal_notes": "",
        }
        created = admin_session.post(f"{API}/projects", json=payload, timeout=30)
        assert created.status_code == 200, created.text
        project = created.json()
        created_ids.append(project["id"])
        assert developer_user["id"] in project.get("assigned_to", [])

    # developer should be able to access both created projects
    for pid in created_ids:
        check = developer_session.get(f"{API}/projects/{pid}", timeout=20)
        assert check.status_code == 200


# Module: ticket creation permissions and maintenance virtual rows
def test_only_client_can_create_ticket(actors):
    title = f"TEST_ITER26_CLIENT_ONLY_{uuid.uuid4().hex[:6]}"
    payload = {
        "project_id": "project-1",
        "title": title,
        "description": "ticket permission matrix test",
        "category": "Bug / Problem",
        "priority": "Sedang",
    }
    for role in ["admin", "adminproject", "developer", "accounting"]:
        session, _ = actors[role]
        denied = session.post(f"{API}/tickets", json=payload, timeout=25)
        assert denied.status_code == 403

    client_session, _ = actors["client"]
    ok = client_session.post(f"{API}/tickets", json=payload, timeout=25)
    assert ok.status_code == 200
    created = ok.json()
    assert created["title"] == title


def test_new_client_ticket_appears_as_virtual_row_global_and_project(actors):
    client_session, _ = actors["client"]
    adminproject_session, _ = actors["adminproject"]
    developer_session, developer_user = actors["developer"]

    ticket = client_session.post(
        f"{API}/tickets",
        json={
            "project_id": "project-1",
            "title": f"TEST_ITER26_TICKET_MAINT_{uuid.uuid4().hex[:6]}",
            "description": "maintenance virtual row check",
            "category": "Bug / Problem",
            "priority": "Tinggi",
        },
        timeout=25,
    )
    assert ticket.status_code == 200
    tid = ticket.json()["id"]
    ticket_row_id = f"ticket:{tid}"

    global_rows = adminproject_session.get(f"{API}/work/maintenances", timeout=25)
    assert global_rows.status_code == 200
    global_match = [r for r in global_rows.json() if r.get("id") == ticket_row_id]
    assert len(global_match) == 1

    project_rows = adminproject_session.get(f"{API}/projects/project-1/work/maintenances", timeout=25)
    assert project_rows.status_code == 200
    project_match = [r for r in project_rows.json() if r.get("id") == ticket_row_id]
    assert len(project_match) == 1

    # Developer sees only tickets assigned to them in maintenance-ticket rows.
    dev_global_rows = developer_session.get(f"{API}/work/maintenances", timeout=25)
    assert dev_global_rows.status_code == 200
    for row in dev_global_rows.json():
        if str(row.get("id", "")).startswith("ticket:"):
            assert row.get("assigned_to") == developer_user["id"]


# Module: manual maintenance permission matrix
def test_manual_maintenance_allowed_for_admin_and_admin_project_only(actors):
    payload = {
        "title": f"TEST_ITER26_MANUAL_MAINT_{uuid.uuid4().hex[:6]}",
        "description": "manual maintenance role test",
        "kind": "Adaptive",
        "assigned_to": "",
        "entry_date": date.today().isoformat(),
        "priority": "Sedang",
        "estimate": 0,
        "subtasks": [],
    }
    for role in ["admin", "adminproject"]:
        session, _ = actors[role]
        ok = session.post(f"{API}/projects/project-1/work/maintenances", json=payload, timeout=25)
        assert ok.status_code == 200, f"{role} should be allowed: {ok.status_code} {ok.text}"
        assert ok.json().get("title") == payload["title"]

    for role in ["client", "developer", "accounting"]:
        session, _ = actors[role]
        denied = session.post(f"{API}/projects/project-1/work/maintenances", json=payload, timeout=25)
        assert denied.status_code == 403


# Module: project documents file/link validation and visibility boundaries
def test_document_link_success_and_internal_visibility_not_exposed_to_client(actors):
    admin_session, _ = actors["admin"]
    client_session, _ = actors["client"]
    suffix = uuid.uuid4().hex[:6]
    data = {
        "kind": "Requirement",
        "visibility": "Internal",
        "name": f"TEST_DOC_LINK_{suffix}",
        "url": "https://docs.google.com/document/d/abc123/edit",
    }
    created = _multipart_post(admin_session, f"{API}/projects/project-1/documents", data=data, timeout=30)
    assert created.status_code == 200, created.text
    doc = created.json()
    assert doc.get("document_type") == "link"
    assert doc.get("name") == data["name"]

    visible_for_client = client_session.get(f"{API}/projects/project-1/documents", timeout=25)
    assert visible_for_client.status_code == 200
    assert all(d.get("id") != doc["id"] for d in visible_for_client.json())


@pytest.mark.parametrize(
    "data,files,expected_status",
    [
        ({"kind": "Requirement", "visibility": "Internal", "name": "JS URL", "url": "javascript:alert(1)"}, None, 400),
        ({"kind": "Requirement", "visibility": "Internal", "name": "DATA URL", "url": "data:text/plain,abc"}, None, 400),
        ({"kind": "Requirement", "visibility": "Internal", "name": "CRED URL", "url": "https://user:pass@example.com/doc"}, None, 400),
        ({"kind": "Requirement", "visibility": "Internal", "name": "", "url": "https://example.com/doc"}, None, 400),
        ({"kind": "Requirement", "visibility": "Internal", "name": "BOTH", "url": "https://example.com/doc"}, {"file": ("a.txt", b"abc", "text/plain")}, 400),
        ({"kind": "Requirement", "visibility": "Internal", "name": "NEITHER"}, None, 400),
    ],
)
def test_document_rejects_invalid_link_and_file_link_combo(actors, data, files, expected_status):
    admin_session, _ = actors["admin"]
    resp = _multipart_post(admin_session, f"{API}/projects/project-1/documents", data=data, files=files, timeout=30)
    assert resp.status_code == expected_status


# Module: notification preferences self endpoints, validation, and rate limit
def test_account_notifications_get_patch_and_phone_normalization(actors):
    developer_session, _ = actors["developer"]

    get_resp = developer_session.get(f"{API}/account/notifications", timeout=20)
    assert get_resp.status_code == 200
    assert "registered_email" in get_resp.json()

    patch_resp = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": True, "whatsapp_number": "0812 3456 7890"},
        timeout=25,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["whatsapp_number"].startswith("+62")

    invalid_phone = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": True, "whatsapp_number": "0812"},
        timeout=25,
    )
    assert invalid_phone.status_code in [400, 422]


def test_account_notifications_extra_fields_forbidden_and_test_rate_limited(actors):
    adminproject_session, _ = actors["adminproject"]

    bad_patch = adminproject_session.patch(
        f"{API}/account/notifications",
        json={
            "in_app": True,
            "email": True,
            "whatsapp": False,
            "whatsapp_number": "",
            "recipient": "x@example.com",
        },
        timeout=25,
    )
    assert bad_patch.status_code == 422

    first = adminproject_session.post(f"{API}/account/notifications/test", timeout=25)
    assert first.status_code in [200, 429]
    second = adminproject_session.post(f"{API}/account/notifications/test", timeout=25)
    assert second.status_code == 429


# Module: ClickUp CSV import role restrictions, preview/commit guards, and duplicate handling
def _csv_bytes() -> bytes:
    rows = [
        "Task ID,Task Name,Status,Assignee,Priority,Start Date,Due Date,Parent ID,Description,Tags,Time Estimate,Space Name,Folder Name,List Name",
        "T-1001,TEST CSV Root Task,To Do,,Normal,01/02/2026,05/02/2026,,Line one; line two,ops,3600000,Space A,Folder A,List A",
        "T-1002,TEST CSV Child Task,In Progress,,High,02/02/2026,06/02/2026,T-1001,Child description,dev,1800000,Space A,Folder A,List A",
    ]
    return ("\n".join(rows)).encode("utf-8")


def test_clickup_import_analyze_role_allows_only_managers(actors):
    admin_session, _ = actors["admin"]
    developer_session, _ = actors["developer"]

    files = {"file": ("clickup-test.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    ok = _multipart_post(admin_session, f"{API}/imports/clickup/analyze", data={"project_id": "project-1"}, files=files, timeout=40)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body.get("session_id")
    assert body.get("row_count") == 2

    files2 = {"file": ("clickup-test.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    denied = _multipart_post(developer_session, f"{API}/imports/clickup/analyze", data={"project_id": "project-1"}, files=files2, timeout=40)
    assert denied.status_code == 403


def test_clickup_preview_commit_guards_and_duplicate_rerun_skips(actors):
    admin_session, _ = actors["admin"]

    tasks_before = admin_session.get(f"{API}/projects/project-1/tasks", timeout=30)
    assert tasks_before.status_code == 200
    before_count = len(tasks_before.json())

    analyze = _multipart_post(
        admin_session,
        f"{API}/imports/clickup/analyze",
        data={"project_id": "project-1"},
        files={"file": ("clickup-test.csv", io.BytesIO(_csv_bytes()), "text/csv")},
        timeout=40,
    )
    assert analyze.status_code == 200, analyze.text
    session = analyze.json()

    # Invalid preview mapping: missing required title mapping should fail.
    invalid_preview = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/preview",
        json={
            "columns": {**session["columns"], "title": "", "external_id": session["columns"].get("external_id", "Task ID")},
            "status_map": session.get("status_map", {}),
            "user_map": session.get("user_map", {}),
            "date_order": "DMY",
            "estimate_unit": "milliseconds",
        },
        timeout=40,
    )
    assert invalid_preview.status_code == 400

    valid_preview = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/preview",
        json={
            "columns": session["columns"],
            "status_map": session.get("status_map", {}),
            "user_map": session.get("user_map", {}),
            "date_order": "DMY",
            "estimate_unit": "milliseconds",
        },
        timeout=40,
    )
    assert valid_preview.status_code == 200, valid_preview.text
    preview = valid_preview.json()
    assert "preview_hash" in preview

    # Preview should not write task rows.
    tasks_after_preview = admin_session.get(f"{API}/projects/project-1/tasks", timeout=30)
    assert tasks_after_preview.status_code == 200
    assert len(tasks_after_preview.json()) == before_count

    bad_hash = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/commit",
        json={"preview_hash": "bad-hash", "confirm": True},
        timeout=40,
    )
    assert bad_hash.status_code == 409

    committed = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/commit",
        json={"preview_hash": preview["preview_hash"], "confirm": True},
        timeout=45,
    )
    assert committed.status_code == 200, committed.text
    result_first = committed.json()
    assert result_first["imported"] + result_first["skipped"] >= 1

    # Re-upload the same CSV: stable ids should prevent duplication.
    time.sleep(0.5)
    analyze2 = _multipart_post(
        admin_session,
        f"{API}/imports/clickup/analyze",
        data={"project_id": "project-1"},
        files={"file": ("clickup-test.csv", io.BytesIO(_csv_bytes()), "text/csv")},
        timeout=40,
    )
    assert analyze2.status_code == 200
    session2 = analyze2.json()

    preview2 = admin_session.post(
        f"{API}/imports/clickup/{session2['session_id']}/preview",
        json={
            "columns": session2["columns"],
            "status_map": session2.get("status_map", {}),
            "user_map": session2.get("user_map", {}),
            "date_order": "DMY",
            "estimate_unit": "milliseconds",
        },
        timeout=40,
    )
    assert preview2.status_code == 200
    p2 = preview2.json()

    committed2 = admin_session.post(
        f"{API}/imports/clickup/{session2['session_id']}/commit",
        json={"preview_hash": p2["preview_hash"], "confirm": True},
        timeout=45,
    )
    assert committed2.status_code == 200
    result_second = committed2.json()
    assert result_second["imported"] == 0
    assert result_second["skipped"] >= 1
