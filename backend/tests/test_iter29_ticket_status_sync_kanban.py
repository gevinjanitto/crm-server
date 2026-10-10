"""Iteration 29: Kanban↔ticket status synchronization regressions."""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
PASSWORD = os.environ.get("SEED_PASSWORD") or dotenv_values("/app/backend/.env")["SEED_PASSWORD"]
PROJECT_ID = "project-1"


def _solve(question: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", question or "")]
    return str(sum(nums))


def _login(username: str) -> tuple[requests.Session, dict]:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    cap = s.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    c = cap.json()
    auth = s.post(
        f"{API}/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
            "captcha_id": c["id"],
            "captcha_answer": _solve(c["question"]),
        },
        timeout=25,
    )
    assert auth.status_code == 200, f"login failed for {username}: {auth.status_code} {auth.text}"
    body = auth.json()
    s.headers.update({"Authorization": f"Bearer {body['token']}"})
    return s, body["user"]


def _project_payload(name: str, client_id: str, developer_id: str) -> dict:
    return {
        "name": name,
        "client_id": client_id,
        "description": "iter29 isolated automation fixture",
        "platforms": ["Web"],
        "type": "Kecil",
        "value": 0,
        "start_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "assigned_to": [developer_id],
        "internal_notes": "",
    }


def _get_ticket_comments(session: requests.Session, ticket_id: str) -> list[dict]:
    r = session.get(f"{API}/tickets/{ticket_id}/comments", timeout=20)
    assert r.status_code == 200
    return r.json()


def _kanban_status_comments_count(comments: list[dict]) -> int:
    return sum(1 for c in comments if "Status diperbarui melalui Kanban" in (c.get("message") or ""))


@pytest.fixture(scope="module")
def actors():
    admin, admin_user = _login("admin")
    admin_project, ap_user = _login("adminproject")
    developer, dev_user = _login("developer")
    client, client_user = _login("client")
    accounting, accounting_user = _login("accounting")
    return {
        "admin": (admin, admin_user),
        "adminproject": (admin_project, ap_user),
        "developer": (developer, dev_user),
        "client": (client, client_user),
        "accounting": (accounting, accounting_user),
    }


@pytest.fixture(scope="module")
def ctx(actors):
    state = {
        "ticket_ids": [],
        "task_ids": [],
        "status_ids": [],
        "project_ids": [],
        "rule_ids": [],
    }
    yield state
    admin = actors["admin"][0]
    ap = actors["adminproject"][0]

    for rid in state["rule_ids"]:
        for pid in state["project_ids"]:
            ap.delete(f"{API}/projects/{pid}/workspace/automations/{rid}", timeout=20)

    for sid in state["status_ids"]:
        ap.delete(f"{API}/projects/{PROJECT_ID}/statuses/{sid}?move_to=Belum%20Mulai", timeout=20)

    for tid in state["task_ids"]:
        ap.delete(f"{API}/projects/{PROJECT_ID}/tasks/{tid}", timeout=20)

    for pid in state["project_ids"]:
        admin.delete(f"{API}/projects/{pid}", timeout=30)


def _create_ticket(client_session: requests.Session, project_id: str, title: str, category: str = "Bug / Problem") -> dict:
    created = client_session.post(
        f"{API}/tickets",
        json={
            "project_id": project_id,
            "title": title,
            "description": "iter29 regression ticket",
            "category": category,
            "priority": "Sedang",
        },
        timeout=30,
    )
    assert created.status_code == 200, created.text
    return created.json()


def _project_tasks(session: requests.Session, project_id: str) -> list[dict]:
    r = session.get(f"{API}/projects/{project_id}/tasks", timeout=25)
    assert r.status_code == 200
    return r.json()


def _ticket_by_id(session: requests.Session, ticket_id: str) -> dict:
    r = session.get(f"{API}/tickets/{ticket_id}", timeout=20)
    assert r.status_code == 200
    return r.json()


# Module: ticket/task sync on Kanban column move
def test_ticket_status_sync_across_main_column_moves_and_lists(actors, ctx):
    client = actors["client"][0]
    ap = actors["adminproject"][0]
    admin = actors["admin"][0]

    uniq = uuid.uuid4().hex[:8]
    ticket = _create_ticket(client, PROJECT_ID, f"TEST_SYNC_FLOW_{uniq}")
    ctx["ticket_ids"].append(ticket["id"])
    task_id = ticket["task_id"]
    assert task_id

    tasks = _project_tasks(ap, PROJECT_ID)
    linked = next(t for t in tasks if t["id"] == task_id)
    assert linked["status"] == "Belum Mulai"
    assert linked["source"] == "ticket"

    move = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": "Dikerjakan", "order": 8101.1}, timeout=25)
    assert move.status_code == 200, move.text

    # detail + project list + global list + maintenance live view + summary
    detail = _ticket_by_id(admin, ticket["id"])
    assert detail["status"] == "Dikerjakan"

    p_rows = admin.get(f"{API}/projects/{PROJECT_ID}/tickets", timeout=20)
    assert p_rows.status_code == 200
    p_ticket = next(r for r in p_rows.json() if r["id"] == ticket["id"])
    assert p_ticket["status"] == "Dikerjakan"

    g_rows = admin.get(f"{API}/tickets", timeout=20)
    assert g_rows.status_code == 200
    g_ticket = next(r for r in g_rows.json() if r["id"] == ticket["id"])
    assert g_ticket["status"] == "Dikerjakan"

    maintenance_rows = admin.get(f"{API}/projects/{PROJECT_ID}/work/maintenances", timeout=20)
    assert maintenance_rows.status_code == 200
    row = next(r for r in maintenance_rows.json() if r.get("ticket_id") == ticket["id"])
    assert row["ticket_status"] == "Dikerjakan"

    summary = admin.get(f"{API}/projects/{PROJECT_ID}/tickets/summary", timeout=20)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] >= 1 and body["active"] >= 1

    # full move cycle + reload persistence + no duplicate ticket-task link
    for status, expected in [
        ("Testing", "Dikerjakan"),
        ("Revisi", "Dikerjakan"),
        ("Selesai", "Selesai"),
        ("Dikerjakan", "Dikerjakan"),
        ("Belum Mulai", "Diterima"),
    ]:
        moved = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": status}, timeout=25)
        assert moved.status_code == 200, moved.text
        current = _ticket_by_id(admin, ticket["id"])
        assert current["status"] == expected

    refresh_tasks = _project_tasks(ap, PROJECT_ID)
    linked_tasks = [t for t in refresh_tasks if t.get("source") == "ticket" and t.get("source_id") == ticket["id"]]
    assert len(linked_tasks) == 1


# Module: custom statuses, idempotent update, bulk and status-column mutation sync
def test_custom_columns_idempotent_bulk_and_kind_edit_sync(actors, ctx):
    ap = actors["adminproject"][0]
    admin = actors["admin"][0]
    client = actors["client"][0]

    stamp = int(time.time())
    todo_name = f"TEST_TODO_{stamp}"
    active_name = f"TEST_ACTIVE_{stamp}"
    done_name = f"TEST_DONE_{stamp}"

    statuses = ap.get(f"{API}/projects/{PROJECT_ID}/statuses", timeout=20)
    assert statuses.status_code == 200

    for name, color, kind in [
        (todo_name, "#9ca3af", "todo"),
        (active_name, "#3b82f6", "active"),
        (done_name, "#16a34a", "done"),
    ]:
        created = ap.post(f"{API}/projects/{PROJECT_ID}/statuses", json={"name": name, "color": color, "kind": kind}, timeout=20)
        assert created.status_code == 200, created.text
        sid = next(c["id"] for c in created.json() if c["name"] == name)
        ctx["status_ids"].append(sid)

    ticket = _create_ticket(client, PROJECT_ID, f"TEST_CUSTOM_COLS_{uuid.uuid4().hex[:6]}")
    tid = ticket["id"]
    task_id = ticket["task_id"]
    ctx["ticket_ids"].append(tid)

    move_active = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": active_name}, timeout=25)
    assert move_active.status_code == 200
    assert _ticket_by_id(admin, tid)["status"] == "Dikerjakan"

    comments_before = _get_ticket_comments(admin, tid)
    count_before = _kanban_status_comments_count(comments_before)
    idempotent = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": active_name}, timeout=25)
    assert idempotent.status_code == 200
    comments_after = _get_ticket_comments(admin, tid)
    assert _kanban_status_comments_count(comments_after) == count_before

    renamed = f"{active_name}_REN"
    sid_active = next(s for s in ctx["status_ids"] if s)
    cols = ap.get(f"{API}/projects/{PROJECT_ID}/statuses", timeout=20).json()
    sid_active = next(c["id"] for c in cols if c["name"] == active_name)
    patch_name = ap.patch(f"{API}/projects/{PROJECT_ID}/statuses/{sid_active}", json={"name": renamed}, timeout=25)
    assert patch_name.status_code == 200
    assert _ticket_by_id(admin, tid)["status"] == "Dikerjakan"
    after_rename_comments = _get_ticket_comments(admin, tid)
    assert _kanban_status_comments_count(after_rename_comments) == count_before

    # Editing column kind should sync all linked tickets in that status.
    patch_kind = ap.patch(f"{API}/projects/{PROJECT_ID}/statuses/{sid_active}", json={"kind": "done"}, timeout=25)
    assert patch_kind.status_code == 200, patch_kind.text
    assert _ticket_by_id(admin, tid)["status"] == "Selesai"

    # bulk update across two ordinary tickets
    t2 = _create_ticket(client, PROJECT_ID, f"TEST_BULK_SYNC_A_{uuid.uuid4().hex[:6]}")
    t3 = _create_ticket(client, PROJECT_ID, f"TEST_BULK_SYNC_B_{uuid.uuid4().hex[:6]}")
    ctx["ticket_ids"] += [t2["id"], t3["id"]]
    bulk = ap.post(
        f"{API}/projects/{PROJECT_ID}/tasks/bulk",
        json={"ids": [t2["task_id"], t3["task_id"]], "status": done_name},
        timeout=30,
    )
    assert bulk.status_code == 200, bulk.text
    assert _ticket_by_id(admin, t2["id"])["status"] == "Selesai"
    assert _ticket_by_id(admin, t3["id"])["status"] == "Selesai"


# Module: automation set_status synchronization using isolated project fixture
def test_status_changed_automation_set_status_syncs_ticket_and_task(actors, ctx):
    admin, _ = actors["admin"]
    ap, _ = actors["adminproject"]
    client, _ = actors["client"]
    developer_user = actors["developer"][1]

    project_1 = admin.get(f"{API}/projects/{PROJECT_ID}", timeout=20)
    assert project_1.status_code == 200
    client_id = project_1.json()["client_id"]

    project_name = f"TEST_ISOLATED_AUTOMATION_{uuid.uuid4().hex[:6]}"
    created_project = admin.post(
        f"{API}/projects",
        json=_project_payload(project_name, client_id, developer_user["id"]),
        timeout=35,
    )
    assert created_project.status_code == 200, created_project.text
    isolated_pid = created_project.json()["id"]
    ctx["project_ids"].append(isolated_pid)

    rule = ap.post(
        f"{API}/projects/{isolated_pid}/workspace/automations",
        json={
            "name": f"TEST_SET_STATUS_{uuid.uuid4().hex[:6]}",
            "trigger": "status_changed",
            "condition_field": "status",
            "condition_value": "Dikerjakan",
            "action": "set_status",
            "action_value": "Selesai",
            "enabled": True,
        },
        timeout=25,
    )
    assert rule.status_code == 200, rule.text
    ctx["rule_ids"].append(rule.json()["id"])

    ticket = _create_ticket(client, isolated_pid, f"TEST_AUTO_TICKET_{uuid.uuid4().hex[:6]}")
    task_id = ticket["task_id"]

    move = ap.patch(f"{API}/projects/{isolated_pid}/tasks/{task_id}", json={"status": "Dikerjakan"}, timeout=30)
    assert move.status_code == 200, move.text
    assert move.json()["status"] == "Selesai"

    synced_ticket = _ticket_by_id(admin, ticket["id"])
    assert synced_ticket["status"] == "Selesai"


# Module: paid change-request guards and no partial mutations
def test_change_request_rejected_before_task_write_for_single_bulk_and_status_delete(actors, ctx):
    client = actors["client"][0]
    ap = actors["adminproject"][0]
    admin = actors["admin"][0]

    ordinary = _create_ticket(client, PROJECT_ID, f"TEST_ORD_{uuid.uuid4().hex[:6]}", "Bug / Problem")
    change_req = _create_ticket(client, PROJECT_ID, f"TEST_CR_{uuid.uuid4().hex[:6]}", "Change Request")
    ctx["ticket_ids"] += [ordinary["id"], change_req["id"]]

    # Single move on CR to active should be blocked.
    denied_single = ap.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{change_req['task_id']}",
        json={"status": "Dikerjakan"},
        timeout=25,
    )
    assert denied_single.status_code == 400
    assert "estimasi" in denied_single.text.lower()
    unchanged = _ticket_by_id(admin, change_req["id"])
    assert unchanged["status"] == "Baru"

    # Bulk should fail atomically, preserving other task status too.
    before_ord = ap.get(f"{API}/projects/{PROJECT_ID}/tasks", timeout=25).json()
    ord_task_before = next(t for t in before_ord if t["id"] == ordinary["task_id"])["status"]
    cr_task_before = next(t for t in before_ord if t["id"] == change_req["task_id"])["status"]

    denied_bulk = ap.post(
        f"{API}/projects/{PROJECT_ID}/tasks/bulk",
        json={"ids": [ordinary["task_id"], change_req["task_id"]], "status": "Dikerjakan"},
        timeout=30,
    )
    assert denied_bulk.status_code == 400

    after_bulk = ap.get(f"{API}/projects/{PROJECT_ID}/tasks", timeout=25).json()
    assert next(t for t in after_bulk if t["id"] == ordinary["task_id"])["status"] == ord_task_before
    assert next(t for t in after_bulk if t["id"] == change_req["task_id"])["status"] == cr_task_before

    # Delete status with move_to active should also fail and keep status column.
    todo_name = f"TEST_CR_TODO_{int(time.time())}"
    add_todo = ap.post(
        f"{API}/projects/{PROJECT_ID}/statuses",
        json={"name": todo_name, "color": "#94a3b8", "kind": "todo"},
        timeout=25,
    )
    assert add_todo.status_code == 200
    sid = next(c["id"] for c in add_todo.json() if c["name"] == todo_name)
    ctx["status_ids"].append(sid)

    move_to_custom_todo = ap.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{change_req['task_id']}",
        json={"status": todo_name},
        timeout=25,
    )
    assert move_to_custom_todo.status_code == 200

    denied_delete = ap.delete(f"{API}/projects/{PROJECT_ID}/statuses/{sid}?move_to=Dikerjakan", timeout=25)
    assert denied_delete.status_code == 400

    cols_after = ap.get(f"{API}/projects/{PROJECT_ID}/statuses", timeout=20)
    assert cols_after.status_code == 200
    assert any(c["id"] == sid for c in cols_after.json())


# Module: role permissions and reopen/closed guards
def test_role_permissions_and_closed_ticket_cannot_reopen_via_board(actors, ctx):
    ap, ap_user = actors["adminproject"]
    client = actors["client"][0]
    accounting = actors["accounting"][0]
    developer, developer_user = actors["developer"]
    admin = actors["admin"][0]

    target = _create_ticket(client, PROJECT_ID, f"TEST_ROLE_PERM_{uuid.uuid4().hex[:6]}")
    ctx["ticket_ids"].append(target["id"])
    task_id = target["task_id"]

    deny_client = client.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": "Dikerjakan"}, timeout=20)
    assert deny_client.status_code == 403
    deny_accounting = accounting.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": "Dikerjakan"}, timeout=20)
    assert deny_accounting.status_code == 403

    team = admin.get(f"{API}/team", timeout=20)
    assert team.status_code == 200
    manager = next(u for u in team.json() if u.get("role") in ["Admin", "Admin Project"] and u["id"] != ap_user["id"])

    assigned = ap.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{task_id}",
        json={"assigned_to": developer_user["id"], "assignee_ids": [developer_user["id"]]},
        timeout=25,
    )
    assert assigned.status_code == 200

    foreign = _create_ticket(client, PROJECT_ID, f"TEST_DEV_FOREIGN_{uuid.uuid4().hex[:6]}")
    ctx["ticket_ids"].append(foreign["id"])
    foreign_assign = ap.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{foreign['task_id']}",
        json={"assigned_to": manager["id"], "assignee_ids": [manager["id"]]},
        timeout=25,
    )
    assert foreign_assign.status_code == 200

    dev_ok = developer.patch(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", json={"status": "Dikerjakan"}, timeout=25)
    assert dev_ok.status_code == 200
    dev_deny = developer.patch(f"{API}/projects/{PROJECT_ID}/tasks/{foreign['task_id']}", json={"status": "Dikerjakan"}, timeout=25)
    assert dev_deny.status_code == 403

    # Close a fresh ticket and ensure board cannot reopen.
    close_case = _create_ticket(client, PROJECT_ID, f"TEST_CLOSED_GUARD_{uuid.uuid4().hex[:6]}")
    ctx["ticket_ids"].append(close_case["id"])
    close_task_id = close_case["task_id"]
    for status in ["Ditinjau", "Diterima", "Dikerjakan", "Selesai", "Ditutup"]:
        changed = ap.patch(f"{API}/tickets/{close_case['id']}", json={"status": status, "assigned_to": developer_user["id"]}, timeout=25)
        assert changed.status_code == 200, f"failed transition to {status}: {changed.status_code} {changed.text}"

    deny_reopen_closed = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{close_task_id}", json={"status": "Dikerjakan"}, timeout=25)
    assert deny_reopen_closed.status_code == 400

    # Selesai can reopen by board move back to active.
    reopen_case = _create_ticket(client, PROJECT_ID, f"TEST_REOPEN_DONE_{uuid.uuid4().hex[:6]}")
    ctx["ticket_ids"].append(reopen_case["id"])
    move_done = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{reopen_case['task_id']}", json={"status": "Selesai"}, timeout=25)
    assert move_done.status_code == 200
    assert _ticket_by_id(admin, reopen_case["id"])["status"] == "Selesai"
    reopen = ap.patch(f"{API}/projects/{PROJECT_ID}/tasks/{reopen_case['task_id']}", json={"status": "Dikerjakan"}, timeout=25)
    assert reopen.status_code == 200
    assert _ticket_by_id(admin, reopen_case["id"])["status"] == "Dikerjakan"
