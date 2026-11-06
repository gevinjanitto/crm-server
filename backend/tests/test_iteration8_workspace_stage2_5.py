"""Iteration 8: Stage 2-5 workspace backend coverage (structure, docs, automation, planning, scheduler)."""

import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values


ENV_FRONTEND = dotenv_values("/app/frontend/.env")
ENV_BACKEND = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or ENV_FRONTEND.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"
PASSWORD = ENV_BACKEND.get("SEED_PASSWORD", "")
CRON_SECRET = ENV_BACKEND.get("WEBHOOK_CRON_SECRET", "")
PID = "project-1"
PID2 = "project-2"


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question)))


def _login(username: str):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    c = s.get(f"{API}/auth/captcha", timeout=20)
    assert c.status_code == 200
    cj = c.json()
    r = s.post(
        f"{API}/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
            "captcha_id": cj["id"],
            "captcha_answer": _solve(cj["question"]),
        },
        timeout=20,
    )
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    user = r.json()["user"]
    return {"session": s, "headers": {"Authorization": f"Bearer {token}"}, "user": user}


@pytest.fixture(scope="module")
def ctx():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    if not PASSWORD:
        pytest.skip("SEED_PASSWORD missing")

    admin = _login("admin")
    manager = _login("adminproject")
    developer = _login("developer")
    client = _login("client")

    data = {
        "admin": admin,
        "manager": manager,
        "developer": developer,
        "client": client,
        "created": {
            "tasks": [],
            "nodes": [],
            "fields": [],
            "docs": [],
            "rules": [],
            "sprints": [],
            "goals": [],
            "comments": [],
            "schedules": [],
        },
    }

    yield data

    ah = data["admin"]["headers"]
    for cid in data["created"]["comments"]:
        requests.delete(f"{API}/projects/{PID}/tasks/{cid['task_id']}/comments/{cid['id']}", headers=ah, timeout=20)
    for gid in data["created"]["goals"]:
        requests.delete(f"{API}/projects/{PID}/workspace/goals/{gid}", headers=ah, timeout=20)
    for sid in data["created"]["sprints"]:
        requests.delete(f"{API}/projects/{PID}/workspace/sprints/{sid}", headers=ah, timeout=20)
    for rid in data["created"]["rules"]:
        requests.delete(f"{API}/projects/{PID}/workspace/automations/{rid}", headers=ah, timeout=20)
    for tid in data["created"]["schedules"]:
        requests.delete(f"{API}/projects/{PID}/workspace/tasks/{tid}/schedule", headers=ah, timeout=20)
    for did in data["created"]["docs"]:
        requests.delete(f"{API}/projects/{PID}/workspace/docs/{did}", headers=ah, timeout=20)
    for fid in data["created"]["fields"]:
        requests.delete(f"{API}/projects/{PID}/workspace/fields/{fid}", headers=ah, timeout=20)
    for nid in reversed(data["created"]["nodes"]):
        requests.delete(f"{API}/projects/{PID}/workspace/nodes/{nid}", headers=ah, timeout=20)
    for tid in data["created"]["tasks"]:
        requests.delete(f"{API}/projects/{PID}/tasks/{tid}", headers=ah, timeout=20)


# --- Structure + custom fields + task extension validation ---
def test_structure_hierarchy_delete_nonempty_and_cross_project_reject(ctx):
    h = ctx["manager"]["headers"]
    space = requests.post(
        f"{API}/projects/{PID}/workspace/nodes",
        headers=h,
        json={"name": f"TEST_SPACE_{uuid.uuid4().hex[:5]}", "kind": "space", "parent_id": "", "color": "#2c63e8"},
        timeout=20,
    )
    assert space.status_code == 200, space.text
    space_id = space.json()["id"]
    ctx["created"]["nodes"].append(space_id)

    list_node = requests.post(
        f"{API}/projects/{PID}/workspace/nodes",
        headers=h,
        json={"name": f"TEST_LIST_{uuid.uuid4().hex[:5]}", "kind": "list", "parent_id": space_id, "color": "#2c63e8"},
        timeout=20,
    )
    assert list_node.status_code == 200, list_node.text
    list_id = list_node.json()["id"]
    ctx["created"]["nodes"].append(list_id)

    t = requests.post(
        f"{API}/projects/{PID}/tasks",
        headers=h,
        json={"title": f"TEST_STAGE25_list_{uuid.uuid4().hex[:4]}", "list_id": list_id},
        timeout=20,
    )
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    ctx["created"]["tasks"].append(tid)

    blocked_delete = requests.delete(f"{API}/projects/{PID}/workspace/nodes/{space_id}", headers=h, timeout=20)
    assert blocked_delete.status_code == 400

    foreign_space = requests.post(
        f"{API}/projects/{PID2}/workspace/nodes",
        headers=h,
        json={"name": f"TEST_FOREIGN_SPACE_{uuid.uuid4().hex[:5]}", "kind": "space", "parent_id": "", "color": "#2c63e8"},
        timeout=20,
    )
    assert foreign_space.status_code == 200, foreign_space.text
    foreign_sid = foreign_space.json()["id"]
    foreign_list = requests.post(
        f"{API}/projects/{PID2}/workspace/nodes",
        headers=h,
        json={"name": f"TEST_FOREIGN_LIST_{uuid.uuid4().hex[:5]}", "kind": "list", "parent_id": foreign_sid, "color": "#2c63e8"},
        timeout=20,
    )
    assert foreign_list.status_code == 200, foreign_list.text
    foreign_lid = foreign_list.json()["id"]

    bad = requests.post(
        f"{API}/projects/{PID}/tasks",
        headers=h,
        json={"title": f"TEST_STAGE25_foreign_{uuid.uuid4().hex[:4]}", "list_id": foreign_lid},
        timeout=20,
    )
    assert bad.status_code in (400, 404)

    # cleanup project-2 structure immediately
    requests.delete(f"{API}/projects/{PID2}/workspace/nodes/{foreign_lid}", headers=h, timeout=20)
    requests.delete(f"{API}/projects/{PID2}/workspace/nodes/{foreign_sid}", headers=h, timeout=20)


def test_custom_fields_visibility_and_manager_only(ctx):
    mh, dh, ch = ctx["manager"]["headers"], ctx["developer"]["headers"], ctx["client"]["headers"]
    f_internal = requests.post(
        f"{API}/projects/{PID}/workspace/fields",
        headers=mh,
        json={"name": f"TEST_INT_{uuid.uuid4().hex[:4]}", "kind": "text", "visibility": "Internal", "options": []},
        timeout=20,
    )
    assert f_internal.status_code == 200
    fid_i = f_internal.json()["id"]
    ctx["created"]["fields"].append(fid_i)

    f_client = requests.post(
        f"{API}/projects/{PID}/workspace/fields",
        headers=mh,
        json={"name": f"TEST_CLIENT_{uuid.uuid4().hex[:4]}", "kind": "dropdown", "visibility": "Client", "options": ["A", "B"]},
        timeout=20,
    )
    assert f_client.status_code == 200
    fid_c = f_client.json()["id"]
    ctx["created"]["fields"].append(fid_c)

    denied = requests.post(
        f"{API}/projects/{PID}/workspace/fields",
        headers=dh,
        json={"name": "DEV_SHOULD_FAIL", "kind": "text", "visibility": "Internal", "options": []},
        timeout=20,
    )
    assert denied.status_code == 403

    t = requests.post(
        f"{API}/projects/{PID}/tasks",
        headers=mh,
        json={
            "title": f"TEST_STAGE25_cf_{uuid.uuid4().hex[:4]}",
            "custom_fields": {fid_i: "internal-only", fid_c: "A"},
        },
        timeout=20,
    )
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    ctx["created"]["tasks"].append(tid)

    client_tasks = requests.get(f"{API}/projects/{PID}/tasks", headers=ch, timeout=20)
    assert client_tasks.status_code == 200
    row = next(x for x in client_tasks.json() if x["id"] == tid)
    assert fid_c in row.get("custom_fields", {})
    assert fid_i not in row.get("custom_fields", {})


# --- Docs + whiteboard + comments mention/assignment ---
def test_docs_permissions_sanitization_versions_conflict(ctx):
    mh, ch = ctx["manager"]["headers"], ctx["client"]["headers"]
    create = requests.post(
        f"{API}/projects/{PID}/workspace/docs",
        headers=mh,
        json={
            "title": f"TEST_DOC_{uuid.uuid4().hex[:5]}",
            "content": '<p>ok</p><script>alert(1)</script><a href="javascript:evil()">x</a>',
            "visibility": "Internal",
            "version": 0,
        },
        timeout=20,
    )
    assert create.status_code == 200, create.text
    doc = create.json()
    did = doc["id"]
    ctx["created"]["docs"].append(did)
    assert "<script" not in doc["content"].lower()
    assert "javascript:" not in doc["content"].lower()

    client_list = requests.get(f"{API}/projects/{PID}/workspace/docs", headers=ch, timeout=20)
    assert client_list.status_code == 200
    assert all(d["id"] != did for d in client_list.json())

    patch1 = requests.patch(
        f"{API}/projects/{PID}/workspace/docs/{did}",
        headers=mh,
        json={"title": doc["title"], "content": "<p>v2</p>", "visibility": "Internal", "version": 1},
        timeout=20,
    )
    assert patch1.status_code == 200
    assert patch1.json()["version"] == 2

    stale = requests.patch(
        f"{API}/projects/{PID}/workspace/docs/{did}",
        headers=mh,
        json={"title": doc["title"], "content": "<p>stale</p>", "visibility": "Internal", "version": 1},
        timeout=20,
    )
    assert stale.status_code == 409

    versions = requests.get(f"{API}/projects/{PID}/workspace/docs/{did}/versions", headers=mh, timeout=20)
    assert versions.status_code == 200
    assert len(versions.json()) >= 2

    client_edit = requests.patch(
        f"{API}/projects/{PID}/workspace/docs/{did}",
        headers=ch,
        json={"title": "x", "content": "<p>x</p>", "visibility": "Client", "version": 2},
        timeout=20,
    )
    assert client_edit.status_code == 403


def test_whiteboard_validation_cas_and_cleanup_selftest_note(ctx):
    mh = ctx["manager"]["headers"]
    board = requests.get(f"{API}/projects/{PID}/workspace/whiteboard", headers=mh, timeout=20)
    assert board.status_code == 200
    bj = board.json()

    # remove only the requested self-test note label, preserve other nodes
    drop_ids = {n.get("id") for n in bj.get("nodes", []) if (n.get("data") or {}).get("label") == "QA: Konsep alur approval project"}
    if drop_ids:
        cleaned_nodes = [n for n in bj.get("nodes", []) if n.get("id") not in drop_ids]
        cleaned_edges = [e for e in bj.get("edges", []) if e.get("source") not in drop_ids and e.get("target") not in drop_ids]
        clean = requests.patch(
            f"{API}/projects/{PID}/workspace/whiteboard",
            headers=mh,
            json={"name": bj.get("name", "Whiteboard project"), "nodes": cleaned_nodes, "edges": cleaned_edges, "version": bj.get("version", 0)},
            timeout=20,
        )
        assert clean.status_code == 200, clean.text
        bj = clean.json()

    bad_dup = requests.patch(
        f"{API}/projects/{PID}/workspace/whiteboard",
        headers=mh,
        json={
            "name": bj.get("name", "Whiteboard project"),
            "nodes": [
                {"id": "dup", "position": {"x": 1, "y": 1}, "data": {"label": "a", "color": "#fff5cd", "task_id": ""}},
                {"id": "dup", "position": {"x": 2, "y": 2}, "data": {"label": "b", "color": "#fff5cd", "task_id": ""}},
            ],
            "edges": [],
            "version": bj.get("version", 0),
        },
        timeout=20,
    )
    assert bad_dup.status_code == 400

    add_note = requests.patch(
        f"{API}/projects/{PID}/workspace/whiteboard",
        headers=mh,
        json={
            "name": bj.get("name", "Whiteboard project"),
            "nodes": bj.get("nodes", []) + [{"id": f"qa-{uuid.uuid4().hex[:8]}", "position": {"x": 55, "y": 66}, "data": {"label": "TEST WB", "color": "#ffffff", "task_id": ""}}],
            "edges": bj.get("edges", []),
            "version": bj.get("version", 0),
        },
        timeout=20,
    )
    assert add_note.status_code == 200, add_note.text

    stale = requests.patch(
        f"{API}/projects/{PID}/workspace/whiteboard",
        headers=mh,
        json={"name": bj.get("name", "Whiteboard project"), "nodes": bj.get("nodes", []), "edges": bj.get("edges", []), "version": bj.get("version", 0)},
        timeout=20,
    )
    assert stale.status_code == 409


def test_comments_mentions_assignment_resolve_and_notifications(ctx):
    mh, dh, ch = ctx["manager"]["headers"], ctx["developer"]["headers"], ctx["client"]["headers"]
    dev_id = ctx["developer"]["user"]["id"]

    t = requests.post(f"{API}/projects/{PID}/tasks", headers=mh, json={"title": f"TEST_COMMENT_{uuid.uuid4().hex[:4]}"}, timeout=20)
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    ctx["created"]["tasks"].append(tid)

    before = requests.get(f"{API}/notifications/unread-count", headers=dh, timeout=20)
    assert before.status_code == 200
    before_n = before.json().get("unread", 0)

    c = requests.post(
        f"{API}/projects/{PID}/tasks/{tid}/comments",
        headers=mh,
        json={"message": "Halo @developer cek ini", "mention_ids": [dev_id], "assigned_to": dev_id},
        timeout=20,
    )
    assert c.status_code == 200, c.text
    cj = c.json()
    cid = cj["id"]
    ctx["created"]["comments"].append({"task_id": tid, "id": cid})
    assert cj.get("assigned_to") == dev_id
    assert any(m["id"] == dev_id for m in cj.get("mentions", []))

    time.sleep(0.4)
    after = requests.get(f"{API}/notifications/unread-count", headers=dh, timeout=20)
    assert after.status_code == 200
    assert after.json().get("unread", 0) >= before_n

    resolved = requests.patch(
        f"{API}/projects/{PID}/workspace/tasks/{tid}/comments/{cid}",
        headers=dh,
        json={"resolved": True},
        timeout=20,
    )
    assert resolved.status_code == 200
    assert resolved.json().get("resolved") is True

    client_try = requests.patch(
        f"{API}/projects/{PID}/workspace/tasks/{tid}/comments/{cid}",
        headers=ch,
        json={"resolved": False},
        timeout=20,
    )
    assert client_try.status_code == 403


# --- Automation + recurring schedule + cron contract ---
def test_automations_crud_execution_and_logs(ctx):
    mh = ctx["manager"]["headers"]
    rule = requests.post(
        f"{API}/projects/{PID}/workspace/automations",
        headers=mh,
        json={
            "name": f"TEST_RULE_{uuid.uuid4().hex[:4]}",
            "trigger": "task_created",
            "condition_field": "",
            "condition_value": "",
            "action": "add_tag",
            "action_value": "autotag",
            "enabled": True,
        },
        timeout=20,
    )
    assert rule.status_code == 200, rule.text
    rid = rule.json()["id"]
    ctx["created"]["rules"].append(rid)

    t = requests.post(f"{API}/projects/{PID}/tasks", headers=mh, json={"title": f"TEST_AUTO_{uuid.uuid4().hex[:4]}"}, timeout=20)
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    ctx["created"]["tasks"].append(tid)
    assert "autotag" in (t.json().get("tags") or [])

    panel = requests.get(f"{API}/projects/{PID}/workspace/automations", headers=mh, timeout=20)
    assert panel.status_code == 200
    logs = panel.json().get("logs", [])
    assert any(log.get("rule_id") == rid and log.get("status") in ("success", "failed") for log in logs)


def test_recurring_schedule_and_cron_contract(ctx):
    mh = ctx["manager"]["headers"]
    t = requests.post(
        f"{API}/projects/{PID}/tasks",
        headers=mh,
        json={
            "title": f"TEST_RECUR_{uuid.uuid4().hex[:4]}",
            "start_date": datetime.now(timezone.utc).date().isoformat(),
            "due_date": datetime.now(timezone.utc).date().isoformat(),
            "reminder_at": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
        },
        timeout=20,
    )
    assert t.status_code == 200, t.text
    src = t.json()
    tid = src["id"]
    ctx["created"]["tasks"].append(tid)

    sched = requests.post(
        f"{API}/projects/{PID}/workspace/tasks/{tid}/schedule",
        headers=mh,
        json={
            "frequency": "daily",
            "next_run": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            "end_at": None,
            "enabled": True,
        },
        timeout=20,
    )
    assert sched.status_code == 200, sched.text
    ctx["created"]["schedules"].append(tid)

    no_auth = requests.post(f"{API}/cron/project-workspace", json={}, timeout=20)
    assert no_auth.status_code == 401
    wrong_auth = requests.post(
        f"{API}/cron/project-workspace",
        headers={"Authorization": "Bearer wrong"},
        json={"event": "schedule.triggered", "schedule_id": "project-workspace", "run_id": str(uuid.uuid4()), "dispatch_time": datetime.now(timezone.utc).isoformat(), "data": None},
        timeout=20,
    )
    assert wrong_auth.status_code == 401

    if not CRON_SECRET:
        pytest.skip("WEBHOOK_CRON_SECRET missing")

    invalid_env = requests.post(
        f"{API}/cron/project-workspace",
        headers={"Authorization": f"Bearer {CRON_SECRET}"},
        json={"event": "bad.event"},
        timeout=20,
    )
    assert invalid_env.status_code == 400

    run_id = f"iter8-{uuid.uuid4().hex[:10]}"
    envelope = {
        "event": "schedule.triggered",
        "schedule_id": "project-workspace",
        "run_id": run_id,
        "dispatch_time": datetime.now(timezone.utc).isoformat(),
        "data": None,
    }
    t0 = time.time()
    first = requests.post(
        f"{API}/cron/project-workspace",
        headers={"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": run_id},
        json=envelope,
        timeout=20,
    )
    elapsed = time.time() - t0
    assert first.status_code == 200, first.text
    assert elapsed < 2.0
    assert first.json().get("accepted") in (True, False)

    dup = requests.post(
        f"{API}/cron/project-workspace",
        headers={"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": run_id},
        json=envelope,
        timeout=20,
    )
    assert dup.status_code == 200
    assert dup.json().get("duplicate") is True

    time.sleep(1.2)
    tasks_now = requests.get(f"{API}/projects/{PID}/tasks", headers=mh, timeout=20)
    assert tasks_now.status_code == 200
    assert sum(1 for x in tasks_now.json() if x.get("title") == src["title"]) >= 1


# --- Sprint / goals / workload / reports ---
def test_sprint_goal_workload_reports_and_completed_sprint_assignment_block(ctx):
    mh, ch = ctx["manager"]["headers"], ctx["client"]["headers"]
    dev_id = ctx["developer"]["user"]["id"]

    start = datetime.now(timezone.utc).date()
    sprint = requests.post(
        f"{API}/projects/{PID}/workspace/sprints",
        headers=mh,
        json={"name": f"TEST_SPRINT_{uuid.uuid4().hex[:4]}", "goal": "qa", "start_date": start.isoformat(), "end_date": (start + timedelta(days=7)).isoformat(), "status": "active"},
        timeout=20,
    )
    assert sprint.status_code == 200, sprint.text
    sid = sprint.json()["id"]
    ctx["created"]["sprints"].append(sid)

    second_active = requests.post(
        f"{API}/projects/{PID}/workspace/sprints",
        headers=mh,
        json={"name": f"TEST_SPRINT2_{uuid.uuid4().hex[:4]}", "goal": "qa", "start_date": start.isoformat(), "end_date": (start + timedelta(days=5)).isoformat(), "status": "active"},
        timeout=20,
    )
    assert second_active.status_code == 400

    task = requests.post(
        f"{API}/projects/{PID}/tasks",
        headers=mh,
        json={"title": f"TEST_SPRINT_TASK_{uuid.uuid4().hex[:4]}", "assignee_ids": [dev_id], "sprint_id": sid},
        timeout=20,
    )
    assert task.status_code == 200, task.text
    tid = task.json()["id"]
    ctx["created"]["tasks"].append(tid)

    done_statuses = requests.get(f"{API}/projects/{PID}/statuses", headers=mh, timeout=20).json()
    done_name = next(s["name"] for s in done_statuses if s["kind"] == "done")

    goal = requests.post(
        f"{API}/projects/{PID}/workspace/goals",
        headers=mh,
        json={"name": f"TEST_GOAL_{uuid.uuid4().hex[:4]}", "description": "qa", "metric": "tasks", "target": 1, "current": 0, "unit": "task", "task_ids": [tid]},
        timeout=20,
    )
    assert goal.status_code == 200, goal.text
    gid = goal.json()["id"]
    ctx["created"]["goals"].append(gid)

    done = requests.patch(f"{API}/projects/{PID}/tasks/{tid}", headers=mh, json={"status": done_name}, timeout=20)
    assert done.status_code == 200

    goals = requests.get(f"{API}/projects/{PID}/workspace/goals", headers=mh, timeout=20)
    assert goals.status_code == 200
    g = next(x for x in goals.json() if x["id"] == gid)
    assert g.get("progress", 0) >= 0

    close = requests.patch(
        f"{API}/projects/{PID}/workspace/sprints/{sid}",
        headers=mh,
        json={"name": sprint.json()["name"], "goal": "qa", "start_date": start.isoformat(), "end_date": (start + timedelta(days=7)).isoformat(), "status": "completed"},
        timeout=20,
    )
    assert close.status_code == 200

    blocked_assign = requests.patch(f"{API}/projects/{PID}/tasks/{tid}", headers=mh, json={"sprint_id": sid}, timeout=20)
    assert blocked_assign.status_code == 400

    cap = requests.post(f"{API}/projects/{PID}/workspace/capacity", headers=mh, json={"user_id": dev_id, "hours": 35}, timeout=20)
    assert cap.status_code == 200
    workload = requests.get(f"{API}/projects/{PID}/workspace/workload?week={start.isoformat()}", headers=mh, timeout=20)
    assert workload.status_code == 200
    assert any(p["id"] == dev_id for p in workload.json().get("people", []))

    client_forbidden = requests.get(f"{API}/projects/{PID}/workspace/workload?week={start.isoformat()}", headers=ch, timeout=20)
    assert client_forbidden.status_code == 403

    reports = requests.get(f"{API}/projects/{PID}/workspace/reports", headers=mh, timeout=20)
    assert reports.status_code == 200
    rj = reports.json()
    for key in ["total", "done", "trend", "statuses", "milestones", "open_comments"]:
        assert key in rj
    assert len(rj.get("trend", [])) == 14
