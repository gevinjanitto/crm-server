"""Iteration 27 focused coverage: role assignment, docs bytes/download, notifications, ClickUp lease/session guards."""

import io
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


# Module: environment/auth helpers
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or BACKEND_ENV.get("SEED_PASSWORD")


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question or "")))


def _login(username: str, password: str | None = None) -> tuple[requests.Session, dict]:
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
            "password": password or SEED_PASSWORD,
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


CREATED = {
    "tasks": [],
    "docs": [],
    "tickets": [],
    "maint": [],
    "projects": [],
    "users": [],
}


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


@pytest.fixture(scope="module", autouse=True)
def cleanup(actors):
    yield
    admin_session, _ = actors["admin"]
    adminproject_session, _ = actors["adminproject"]
    developer_session, _ = actors["developer"]

    # Restore developer notification preferences requested by main agent context
    developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": False, "whatsapp_number": ""},
        timeout=25,
    )

    for did in CREATED["docs"]:
        admin_session.delete(f"{API}/projects/project-1/documents/{did}", timeout=25)
    for tid in CREATED["tasks"]:
        admin_session.delete(f"{API}/projects/project-1/tasks/{tid}", timeout=25)
    for mid in CREATED["maint"]:
        adminproject_session.delete(f"{API}/projects/project-1/work/maintenances/{mid}", timeout=25)
    for pid in CREATED["projects"]:
        admin_session.delete(f"{API}/projects/{pid}", timeout=25)
    for uid in CREATED["users"]:
        admin_session.patch(f"{API}/users/{uid}", json={"active": False}, timeout=25)


# Module: role assignment validation for task/subtask + reusable membership
def test_assign_admin_adminproject_developer_to_task_and_subtask_allowed(actors):
    admin_session, admin_user = actors["admin"]
    _, adminproject_user = actors["adminproject"]
    _, developer_user = actors["developer"]

    base = {
        "title": f"TEST_ITER26_ASSIGN_OK_{uuid.uuid4().hex[:6]}",
        "description": "role assignment check",
        "status": "Belum Mulai",
        "priority": "Sedang",
    }
    for assignee in [admin_user["id"], adminproject_user["id"], developer_user["id"]]:
        payload = {**base, "title": f"{base['title']}_{assignee[-4:]}", "assigned_to": assignee}
        created = admin_session.post(f"{API}/projects/project-1/tasks", json=payload, timeout=25)
        assert created.status_code == 200, created.text
        row = created.json()
        CREATED["tasks"].append(row["id"])
        assert row["assigned_to"] == assignee

    task = admin_session.post(
        f"{API}/projects/project-1/tasks",
        json={"title": f"TEST_ITER26_SUBTASK_PARENT_{uuid.uuid4().hex[:6]}", "status": "Belum Mulai", "assigned_to": ""},
        timeout=25,
    )
    assert task.status_code == 200
    tid = task.json()["id"]
    CREATED["tasks"].append(tid)

    for assignee in [admin_user["id"], adminproject_user["id"], developer_user["id"]]:
        sub = admin_session.post(
            f"{API}/projects/project-1/tasks/{tid}/subtasks",
            json={"title": f"TEST_ITER26_SUB_{assignee[-4:]}", "assigned_to": assignee},
            timeout=25,
        )
        assert sub.status_code == 200, sub.text


def test_inactive_accounting_client_and_unassigned_developer_rejected_for_task_and_subtask(actors):
    admin_session, _ = actors["admin"]
    _, accounting_user = actors["accounting"]
    _, client_user = actors["client"]

    unique = uuid.uuid4().hex[:6]
    password = "TestIter26!1"

    unassigned_dev = admin_session.post(
        f"{API}/users",
        json={
            "name": f"TEST_ITER26 Unassigned Dev {unique}",
            "username": f"test_iter26_dev_{unique}",
            "email": f"test_iter26_dev_{unique}@example.org",
            "password": password,
            "role": "Developer",
            "client_id": "",
        },
        timeout=30,
    )
    assert unassigned_dev.status_code == 200, unassigned_dev.text
    unassigned_dev_id = unassigned_dev.json()["id"]
    CREATED["users"].append(unassigned_dev_id)

    inactive_dev = admin_session.post(
        f"{API}/users",
        json={
            "name": f"TEST_ITER26 Inactive Dev {unique}",
            "username": f"test_iter26_inactive_{unique}",
            "email": f"test_iter26_inactive_{unique}@example.org",
            "password": password,
            "role": "Developer",
            "client_id": "",
        },
        timeout=30,
    )
    assert inactive_dev.status_code == 200, inactive_dev.text
    inactive_dev_id = inactive_dev.json()["id"]
    CREATED["users"].append(inactive_dev_id)
    deactivate = admin_session.patch(f"{API}/users/{inactive_dev_id}", json={"active": False}, timeout=25)
    assert deactivate.status_code == 200

    denied_ids = [accounting_user["id"], client_user["id"], inactive_dev_id, unassigned_dev_id]
    for denied in denied_ids:
        task = admin_session.post(
            f"{API}/projects/project-1/tasks",
            json={"title": f"TEST_ITER26_ASSIGN_DENY_{denied[-4:]}_{unique}", "status": "Belum Mulai", "assigned_to": denied},
            timeout=25,
        )
        assert task.status_code == 400, f"expected reject for {denied}, got {task.status_code} {task.text}"

    parent = admin_session.post(
        f"{API}/projects/project-1/tasks",
        json={"title": f"TEST_ITER26_SUBTASK_DENY_PARENT_{unique}", "status": "Belum Mulai", "assigned_to": ""},
        timeout=25,
    )
    assert parent.status_code == 200
    tid = parent.json()["id"]
    CREATED["tasks"].append(tid)

    for denied in denied_ids:
        sub = admin_session.post(
            f"{API}/projects/project-1/tasks/{tid}/subtasks",
            json={"title": f"TEST_ITER26_SUB_DENY_{denied[-4:]}_{unique}", "assigned_to": denied},
            timeout=25,
        )
        assert sub.status_code == 400


def test_eligible_membership_reusable_across_projects(actors):
    admin_session, admin_user = actors["admin"]
    _, adminproject_user = actors["adminproject"]
    _, developer_user = actors["developer"]

    clients = admin_session.get(f"{API}/clients", timeout=20)
    assert clients.status_code == 200
    client_id = clients.json()[0]["id"]

    start = date.today() + timedelta(days=1)
    due = start + timedelta(days=14)
    suffix = uuid.uuid4().hex[:6]
    members = [admin_user["id"], adminproject_user["id"], developer_user["id"]]

    for idx in [1, 2]:
        payload = {
            "name": f"TEST_ITER26_MEMBERSHIP_{suffix}_{idx}",
            "client_id": client_id,
            "description": "membership reuse roles",
            "platforms": ["Web"],
            "type": "Kecil",
            "value": 0,
            "start_date": start.isoformat(),
            "due_date": due.isoformat(),
            "assigned_to": members,
            "internal_notes": "",
        }
        created = admin_session.post(f"{API}/projects", json=payload, timeout=30)
        assert created.status_code == 200, created.text
        row = created.json()
        CREATED["projects"].append(row["id"])
        assert set(members).issubset(set(row.get("assigned_to", [])))


# Module: source assignment sync for ticket/maintenance-origin tasks
def test_source_assignment_sync_ticket_and_maintenance(actors):
    client_session, _ = actors["client"]
    adminproject_session, adminproject_user = actors["adminproject"]
    _, admin_user = actors["admin"]
    _, developer_user = actors["developer"]

    ticket = client_session.post(
        f"{API}/tickets",
        json={
            "project_id": "project-1",
            "title": f"TEST_ITER26_SYNC_TICKET_{uuid.uuid4().hex[:6]}",
            "description": "sync assignment for ticket task",
            "category": "Bug / Problem",
            "priority": "Sedang",
        },
        timeout=30,
    )
    assert ticket.status_code == 200, ticket.text
    ticket_doc = ticket.json()
    CREATED["tickets"].append(ticket_doc["id"])

    triage = adminproject_session.patch(
        f"{API}/tickets/{ticket_doc['id']}",
        json={"status": "Ditinjau", "assigned_to": adminproject_user["id"]},
        timeout=30,
    )
    assert triage.status_code == 200, triage.text

    tasks = adminproject_session.get(f"{API}/projects/project-1/tasks", timeout=25)
    assert tasks.status_code == 200
    source_tasks = [t for t in tasks.json() if t.get("source") == "ticket" and t.get("source_id") == ticket_doc["id"]]
    assert source_tasks and source_tasks[0].get("assigned_to") == adminproject_user["id"]

    maint = adminproject_session.post(
        f"{API}/projects/project-1/work/maintenances",
        json={
            "title": f"TEST_ITER26_SYNC_MAINT_{uuid.uuid4().hex[:6]}",
            "description": "sync from task -> maintenance",
            "kind": "Adaptive",
            "assigned_to": developer_user["id"],
            "entry_date": date.today().isoformat(),
            "priority": "Sedang",
            "estimate": 0,
            "subtasks": [],
        },
        timeout=30,
    )
    assert maint.status_code == 200, maint.text
    mdoc = maint.json()
    CREATED["maint"].append(mdoc["id"])
    task_id = mdoc["task_id"]
    CREATED["tasks"].append(task_id)

    reassign = adminproject_session.patch(
        f"{API}/projects/project-1/tasks/{task_id}",
        json={"assigned_to": admin_user["id"]},
        timeout=30,
    )
    assert reassign.status_code == 200, reassign.text

    maint_rows = adminproject_session.get(f"{API}/projects/project-1/work/maintenances", timeout=25)
    assert maint_rows.status_code == 200
    synced = next((r for r in maint_rows.json() if r.get("id") == mdoc["id"]), None)
    assert synced and synced.get("assigned_to") == admin_user["id"]


# Module: documents bytes/filename, links, and client/internal boundaries
def test_txt_file_download_preserves_bytes_and_original_filename_with_custom_name(actors):
    admin_session, _ = actors["admin"]
    payload_name = f"TEST_ITER26_DOCNAME_{uuid.uuid4().hex[:6]}"
    file_name = "TEST_ITER26_payload.txt"
    file_bytes = b"TEST_ITER26 line-1\nline-2\nUTF8-bytes: \xe2\x9c\x93"

    created = _multipart_post(
        admin_session,
        f"{API}/projects/project-1/documents",
        data={"kind": "Requirement", "visibility": "Internal", "name": payload_name},
        files={"file": (file_name, io.BytesIO(file_bytes), "text/plain")},
        timeout=40,
    )
    assert created.status_code == 200, created.text
    doc = created.json()
    CREATED["docs"].append(doc["id"])
    assert doc.get("name") == payload_name
    assert doc.get("filename") == file_name

    downloaded = admin_session.get(f"{API}/projects/project-1/documents/{doc['id']}/download", timeout=40)
    assert downloaded.status_code == 200
    assert downloaded.content == file_bytes
    assert file_name in downloaded.headers.get("content-disposition", "")


def test_google_sheet_and_http_link_save_and_client_internal_denial(actors):
    admin_session, _ = actors["admin"]
    client_session, _ = actors["client"]
    suffix = uuid.uuid4().hex[:6]

    links = [
        (f"TEST_DOC_LINK_{suffix}_GS", "https://docs.google.com/spreadsheets/d/abc123/edit"),
        (f"TEST_DOC_LINK_{suffix}_HTTP", "https://example.com/specs/iter26"),
    ]
    created_ids = []
    for name, url in links:
        created = _multipart_post(
            admin_session,
            f"{API}/projects/project-1/documents",
            data={"kind": "Requirement", "visibility": "Internal", "name": name, "url": url},
            timeout=30,
        )
        assert created.status_code == 200, created.text
        doc = created.json()
        created_ids.append(doc["id"])
        CREATED["docs"].append(doc["id"])
        assert doc.get("document_type") == "link"

    listing = client_session.get(f"{API}/projects/project-1/documents", timeout=25)
    assert listing.status_code == 200
    assert all(d.get("id") not in created_ids for d in listing.json())

    denied = client_session.get(f"{API}/projects/project-1/documents/{created_ids[0]}/download", timeout=25)
    assert denied.status_code == 404

    not_owner = client_session.get(f"{API}/projects/project-2/documents", timeout=25)
    assert not_owner.status_code == 404


# Module: notification preference isolation, opt-out behavior, opt-in timestamp, managed email target
def test_notification_preferences_isolated_optout_blocks_inapp_and_delivery_and_optin_timestamp(actors):
    admin_session, _ = actors["admin"]
    adminproject_session, _ = actors["adminproject"]
    developer_session, developer_user = actors["developer"]

    adminproject_before = adminproject_session.get(f"{API}/account/notifications", timeout=25)
    assert adminproject_before.status_code == 200
    adminproject_pref_before = adminproject_before.json()

    unread_before = developer_session.get(f"{API}/notifications/unread-count", timeout=25)
    deliveries_before = developer_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    assert unread_before.status_code == 200 and deliveries_before.status_code == 200
    unread_count_before = unread_before.json().get("unread", 0)
    dev_deliv_before = len(deliveries_before.json())

    opt_out = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": False, "email": False, "whatsapp": False, "whatsapp_number": ""},
        timeout=25,
    )
    assert opt_out.status_code == 200

    trigger = admin_session.post(
        f"{API}/projects/project-1/tasks",
        json={
            "title": f"TEST_ITER26_NOTIFY_TRIGGER_{uuid.uuid4().hex[:6]}",
            "description": "notification opt-out behavior",
            "status": "Belum Mulai",
            "assigned_to": developer_user["id"],
        },
        timeout=30,
    )
    assert trigger.status_code == 200
    CREATED["tasks"].append(trigger.json()["id"])
    time.sleep(2)

    unread_after = developer_session.get(f"{API}/notifications/unread-count", timeout=25)
    deliveries_after = developer_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    assert unread_after.status_code == 200 and deliveries_after.status_code == 200
    assert unread_after.json().get("unread", 0) == unread_count_before
    assert len(deliveries_after.json()) == dev_deliv_before

    adminproject_after = adminproject_session.get(f"{API}/account/notifications", timeout=25)
    assert adminproject_after.status_code == 200
    assert adminproject_after.json().get("in_app") == adminproject_pref_before.get("in_app")
    assert adminproject_after.json().get("email") == adminproject_pref_before.get("email")

    opt_in = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": True, "whatsapp_number": "0812 3456 7890"},
        timeout=25,
    )
    assert opt_in.status_code == 200
    users = admin_session.get(f"{API}/users", timeout=30)
    assert users.status_code == 200
    dev_row = next((u for u in users.json() if u.get("id") == developer_user["id"]), None)
    assert dev_row and dev_row.get("whatsapp_opt_in_at")


def test_email_delivery_attempt_records_history(actors):
    admin_session, _ = actors["admin"]
    unique = uuid.uuid4().hex[:6]
    username = f"test_iter26_mail_{unique}"
    password = "TestIter26!1"

    created = admin_session.post(
        f"{API}/users",
        json={
            "name": f"TEST_ITER26 Mail Receiver {unique}",
            "username": username,
            "email": "delivered-test@maiharta.test",
            "password": password,
            "role": "Developer",
            "client_id": "",
        },
        timeout=30,
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["id"]
    CREATED["users"].append(user_id)

    receiver_session, _ = _login(username, password)
    pref = receiver_session.patch(
        f"{API}/account/notifications",
        json={"in_app": False, "email": True, "whatsapp": False, "whatsapp_number": ""},
        timeout=25,
    )
    assert pref.status_code == 200

    test_send = receiver_session.post(f"{API}/account/notifications/test", timeout=30)
    assert test_send.status_code in [200, 429], test_send.text
    time.sleep(3)
    deliveries = receiver_session.get(f"{API}/account/notifications/deliveries", timeout=30)
    assert deliveries.status_code == 200
    rows = deliveries.json()
    email_row = next((r for r in rows if r.get("channel") == "email"), None)
    assert email_row is not None
    assert email_row.get("status") in ["accepted", "failed", "skipped"]
    print(f"EMAIL_PROVIDER_RESULT:{email_row.get('status')} reason={email_row.get('reason', '')} id={email_row.get('id')}")


# Module: ClickUp session ownership, validation, conversion, hierarchy, idempotency, lease/concurrency
def _csv_hierarchy_valid() -> bytes:
    rows = [
        "Task ID,Task Name,Status,Assignee,Priority,Start Date,Due Date,Parent ID,Description,Tags,Time Estimate,Space Name,Folder Name,List Name",
        "TEST_ITER26-CU-ROOT,TEST_ITER26 CSV Root,To Do,,Normal,1738368000000,1738713600000,,Root desc,ops,3600000,Space A,Folder A,List A",
        "TEST_ITER26-CU-SUB,TEST_ITER26 CSV Sub,In Progress,,High,1738454400000,1738800000000,TEST_ITER26-CU-ROOT,Sub desc,dev,1800000,Space A,Folder A,List A",
    ]
    return ("\n".join(rows)).encode("utf-8")


def _csv_invalid_status_assignee() -> bytes:
    rows = [
        "Task ID,Task Name,Status,Assignee,Priority,Start Date,Due Date,Parent ID,Description,Tags,Time Estimate,Space Name,Folder Name,List Name",
        "TEST_ITER26-CU-BAD,TEST_ITER26 CSV Bad,UNKNOWN_STATUS,GHOST USER,Normal,01/02/2026,05/02/2026,,Bad row,ops,3600000,Space A,Folder A,List A",
    ]
    return ("\n".join(rows)).encode("utf-8")


def _analyze_csv(session: requests.Session, csv_bytes: bytes):
    return _multipart_post(
        session,
        f"{API}/imports/clickup/analyze",
        data={"project_id": "project-1"},
        files={"file": ("clickup-gap.csv", io.BytesIO(csv_bytes), "text/csv")},
        timeout=45,
    )


def test_clickup_session_ownership_unknown_mappings_blocking_and_conversion_hierarchy(actors):
    admin_session, _ = actors["admin"]
    adminproject_session, _ = actors["adminproject"]

    analyzed = _analyze_csv(admin_session, _csv_hierarchy_valid())
    assert analyzed.status_code == 200, analyzed.text
    session = analyzed.json()

    forbidden_preview = adminproject_session.post(
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
    assert forbidden_preview.status_code == 404

    invalid = _analyze_csv(admin_session, _csv_invalid_status_assignee())
    assert invalid.status_code == 200
    s_bad = invalid.json()
    bad_preview = admin_session.post(
        f"{API}/imports/clickup/{s_bad['session_id']}/preview",
        json={
            "columns": s_bad["columns"],
            "status_map": s_bad.get("status_map", {}),
            "user_map": s_bad.get("user_map", {}),
            "date_order": "DMY",
            "estimate_unit": "milliseconds",
        },
        timeout=40,
    )
    assert bad_preview.status_code == 200
    bad_body = bad_preview.json()
    assert bad_body.get("valid") is False
    assert any("Petakan" in e.get("message", "") for e in bad_body.get("errors", []))

    blocked_commit = admin_session.post(
        f"{API}/imports/clickup/{s_bad['session_id']}/commit",
        json={"preview_hash": bad_body["preview_hash"], "confirm": True},
        timeout=40,
    )
    assert blocked_commit.status_code == 409

    good_preview = admin_session.post(
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
    assert good_preview.status_code == 200, good_preview.text
    p = good_preview.json()
    assert p.get("tasks") == 1 and p.get("subtasks") == 1
    first = p["rows"][0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first.get("start_date", ""))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first.get("due_date", ""))
    assert first.get("estimate_hours") == 1.0

    invalid_confirm = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/commit",
        json={"preview_hash": p["preview_hash"], "confirm": False},
        timeout=40,
    )
    assert invalid_confirm.status_code == 422


def test_clickup_processing_lease_prevents_double_commit_and_replays_result(actors):
    admin_session, _ = actors["admin"]

    analyzed = _analyze_csv(admin_session, _csv_hierarchy_valid())
    assert analyzed.status_code == 200
    session = analyzed.json()
    preview = admin_session.post(
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
    assert preview.status_code == 200
    ph = preview.json()["preview_hash"]

    def _commit_once():
        return admin_session.post(
            f"{API}/imports/clickup/{session['session_id']}/commit",
            json={"preview_hash": ph, "confirm": True},
            timeout=60,
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(_commit_once)
        f2 = ex.submit(_commit_once)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status_code in [200, 409]
    assert r2.status_code in [200, 409]
    ok_bodies = [r.json() for r in [r1, r2] if r.status_code == 200]
    assert ok_bodies, "at least one commit should succeed"

    # Preview mutation must be blocked once commit in progress/completed for this session.
    after_preview = admin_session.post(
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
    assert after_preview.status_code == 409

    replay = admin_session.post(
        f"{API}/imports/clickup/{session['session_id']}/commit",
        json={"preview_hash": ph, "confirm": True},
        timeout=45,
    )
    assert replay.status_code == 200
    replay_body = replay.json()
    assert all(k in replay_body for k in ["imported", "skipped", "subtasks_imported", "project_id"])
