"""Iteration 7: task workspace (assignees/dependencies/views/duplicate) + auth playbook checks."""

import re
import uuid
import os
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
from dotenv import dotenv_values

import pytest
import requests


BASE = dotenv_values(Path(__file__).parents[2] / 'frontend' / '.env')['REACT_APP_BACKEND_URL'] + '/api'
PASSWORD = dotenv_values(Path(__file__).parents[1] / '.env')['SEED_PASSWORD']
PID = "project-1"
FOREIGN_PID = "project-2"


def _solve_math(question: str) -> str:
    nums = [int(x) for x in re.findall(r"\d+", question)]
    return str(sum(nums))


def _login(username: str, password: str = PASSWORD):
    s = requests.Session()
    cap = s.get(f"{BASE}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    cj = cap.json()
    assert cj.get("provider") == "math", f"expected math provider, got {cj}"
    r = s.post(
        f"{BASE}/auth/login",
        json={
            "username": username,
            "password": password,
            "captcha_id": cj["id"],
            "captcha_answer": _solve_math(cj["question"]),
            "remember": False,
        },
        timeout=20,
    )
    return s, r


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def ctx():
    admin_s, admin_login = _login("admin")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["token"]

    ap_s, ap_login = _login("adminproject")
    assert ap_login.status_code == 200, ap_login.text
    ap_token = ap_login.json()["token"]

    dev_s, dev_login = _login("developer")
    assert dev_login.status_code == 200, dev_login.text
    dev_token = dev_login.json()["token"]
    dev_id = dev_login.json()["user"]["id"]

    client_s, client_login = _login("client")
    assert client_login.status_code == 200, client_login.text
    client_token = client_login.json()["token"]

    # create second developer test account
    suffix = uuid.uuid4().hex[:8]
    second_username = f"testdev_{suffix}"
    second_email = f"{second_username}@example.com"
    create_user = requests.post(
        f"{BASE}/users",
        headers=_auth(admin_token),
        json={
            "name": f"TEST Developer {suffix}",
            "username": second_username,
            "email": second_email,
            "password": PASSWORD,
            "role": "Developer",
            "client_id": "",
        },
        timeout=20,
    )
    assert create_user.status_code == 200, create_user.text
    second_user = create_user.json()
    second_id = second_user["id"]

    second_s, second_login = _login(second_username)
    assert second_login.status_code == 200, second_login.text
    second_token = second_login.json()["token"]

    # ensure second developer assigned to project-1 for shared assignee tests
    p1 = requests.get(f"{BASE}/projects/{PID}", headers=_auth(admin_token), timeout=20)
    assert p1.status_code == 200, p1.text
    p1j = p1.json()
    original_assigned = list(p1j.get("assigned_to") or [])
    if second_id not in original_assigned:
        patch = {
            "name": p1j["name"],
            "client_id": p1j["client_id"],
            "description": p1j.get("description", ""),
            "platforms": p1j.get("platforms") or ["Web"],
            "category": p1j.get("category", ""),
            "type": p1j.get("type", "Besar"),
            "value": p1j.get("value", 0),
            "start_date": p1j["start_date"],
            "due_date": p1j["due_date"],
            "assigned_to": list(dict.fromkeys(original_assigned + [second_id])),
            "internal_notes": p1j.get("internal_notes", ""),
        }
        upd = requests.patch(f"{BASE}/projects/{PID}", headers=_auth(admin_token), json=patch, timeout=20)
        assert upd.status_code == 200, upd.text

    data = {
        "admin": {"session": admin_s, "token": admin_token},
        "adminproject": {"session": ap_s, "token": ap_token},
        "developer": {"session": dev_s, "token": dev_token, "id": dev_id},
        "developer2": {"session": second_s, "token": second_token, "id": second_id, "username": second_username},
        "client": {"session": client_s, "token": client_token},
        "created": {"tasks": [], "views": [], "foreign_tasks": []},
        "original_assigned": original_assigned,
    }

    yield data

    # cleanup tasks
    for tid in data["created"]["tasks"]:
        requests.delete(f"{BASE}/projects/{PID}/tasks/{tid}", headers=_auth(admin_token), timeout=20)
    for tid in data["created"]["foreign_tasks"]:
        requests.delete(f"{BASE}/projects/{FOREIGN_PID}/tasks/{tid}", headers=_auth(admin_token), timeout=20)
    # cleanup saved views
    own_views = requests.get(f"{BASE}/projects/{PID}/task-views", headers=_auth(admin_token), timeout=20)
    if own_views.status_code == 200:
        for v in own_views.json():
            if v.get("name", "").startswith("TEST_iter7_"):
                requests.delete(f"{BASE}/projects/{PID}/task-views/{v['id']}", headers=_auth(admin_token), timeout=20)
    # restore assignment
    p1_now = requests.get(f"{BASE}/projects/{PID}", headers=_auth(admin_token), timeout=20)
    if p1_now.status_code == 200:
        p1j = p1_now.json()
        patch = {
            "name": p1j["name"],
            "client_id": p1j["client_id"],
            "description": p1j.get("description", ""),
            "platforms": p1j.get("platforms") or ["Web"],
            "category": p1j.get("category", ""),
            "type": p1j.get("type", "Besar"),
            "value": p1j.get("value", 0),
            "start_date": p1j["start_date"],
            "due_date": p1j["due_date"],
            "assigned_to": data["original_assigned"],
            "internal_notes": p1j.get("internal_notes", ""),
        }
        requests.patch(f"{BASE}/projects/{PID}", headers=_auth(admin_token), json=patch, timeout=20)
    # deactivate test developer account
    requests.patch(
        f"{BASE}/users/{data['developer2']['id']}",
        headers=_auth(admin_token),
        json={"active": False},
        timeout=20,
    )


# --- auth/captcha/cookie/cors checks ---
def test_login_sets_http_only_cookie_and_me_works_with_cookie_only():
    s, r = _login("admin")
    assert r.status_code == 200, r.text
    cookie_hdr = r.headers.get("set-cookie", "")
    assert "maiharta_session=" in cookie_hdr
    assert "HttpOnly" in cookie_hdr
    assert "Secure" in cookie_hdr
    me = s.get(f"{BASE}/auth/me", timeout=20)
    assert me.status_code == 200
    assert me.json().get("username") == "admin"


def test_cors_preflight_allows_credentials():
    r = requests.options(
        f"{BASE}/auth/login",
        headers={
            "Origin": BASE.removesuffix('/api'),
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-credentials") == "true"
    assert r.headers.get('access-control-allow-origin', '').startswith('https://')
    assert r.headers.get('access-control-allow-origin') != '*'
    # Preview ingress rewrites Origin to a cluster alias. The browser app/API are
    # same-origin and real credentialed login is tested above. Isolate application
    # middleware below to verify it reflects the caller's actual Origin correctly.
    async def application_preflight():
        import httpx
        try:
            from server import app
        except ModuleNotFoundError:
            backend_dir = Path(__file__).parents[1]
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from server import app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE.removesuffix('/api')) as client:
            return await client.options('/api/auth/login', headers={
                'Origin': BASE.removesuffix('/api'),
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            })
    isolated = asyncio.run(application_preflight())
    assert isolated.status_code == 200
    assert isolated.headers['access-control-allow-origin'] == BASE.removesuffix('/api')
    assert isolated.headers['access-control-allow-credentials'] == 'true'


def test_auth_lockout_preserves_existing_fifteen_attempt_policy():
    # User explicitly requested unchanged non-Project behavior. Existing auth.py
    # uses 15 failures in 10 minutes, not the generic integration example's five.
    # Use a unique nonexistent account to avoid locking the real admin out.
    username = 'test_lockout_' + uuid.uuid4().hex
    statuses = []
    for _ in range(16):
        _, r = _login(username, password="WrongPassword!123")
        statuses.append(r.status_code)
    assert statuses[:15] == [401] * 15
    assert statuses[-1] == 429, f"Expected 429 on 16th attempt, got statuses={statuses}"


# --- tasks / assignees / permissions ---
def test_create_task_multi_assignee_and_persistence(ctx):
    h = _auth(ctx["admin"]["token"])
    body = {
        "title": f"TEST_iter7_create_{uuid.uuid4().hex[:6]}",
        "assignee_ids": [ctx["developer"]["id"], ctx["developer2"]["id"]],
        "start_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=2)).isoformat(),
        "tags": ["iter7", "multi"],
        "priority": "Tinggi",
        "subtasks": ["sub a", "sub b"],
    }
    r = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json=body, timeout=20)
    assert r.status_code == 200, r.text
    t = r.json()
    ctx["created"]["tasks"].append(t["id"])
    assert t["assigned_to"] == ctx["developer"]["id"]
    assert set(t["assignee_ids"]) == set(body["assignee_ids"])
    assert len(t["assignees"]) == 2
    assert t["start_date"] == body["start_date"]
    assert t["due_date"] == body["due_date"]
    assert set(t["tags"]) == set(body["tags"])
    assert len(t["subtasks"]) == 2

    g = requests.get(f"{BASE}/projects/{PID}/tasks", headers=h, timeout=20)
    assert g.status_code == 200
    fetched = next(x for x in g.json() if x["id"] == t["id"])
    assert set(fetched["assignee_ids"]) == set(body["assignee_ids"])


def test_create_task_invalid_dates_400(ctx):
    h = _auth(ctx["admin"]["token"])
    r = requests.post(
        f"{BASE}/projects/{PID}/tasks",
        headers=h,
        json={
            "title": f"TEST_iter7_bad_date_{uuid.uuid4().hex[:6]}",
            "start_date": (date.today() + timedelta(days=3)).isoformat(),
            "due_date": date.today().isoformat(),
        },
        timeout=20,
    )
    assert r.status_code == 400


def test_patch_null_dates_clear_and_backward_compat_assigned_to(ctx):
    h = _auth(ctx["admin"]["token"])
    create = requests.post(
        f"{BASE}/projects/{PID}/tasks",
        headers=h,
        json={
            "title": f"TEST_iter7_patch_{uuid.uuid4().hex[:6]}",
            "assigned_to": ctx["developer"]["id"],
            "start_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=1)).isoformat(),
        },
        timeout=20,
    )
    assert create.status_code == 200, create.text
    t = create.json()
    ctx["created"]["tasks"].append(t["id"])
    assert t["assigned_to"] == ctx["developer"]["id"]
    assert ctx["developer"]["id"] in t.get("assignee_ids", [])

    clear = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{t['id']}",
        headers=h,
        json={"start_date": None, "due_date": None},
        timeout=20,
    )
    assert clear.status_code == 200, clear.text
    cj = clear.json()
    assert cj.get("start_date") is None
    assert cj.get("due_date") is None


def test_assignee_permissions_and_foreign_project_denied(ctx):
    admin_h = _auth(ctx["admin"]["token"])
    d2_h = _auth(ctx["developer2"]["token"])
    client_h = _auth(ctx["client"]["token"])

    create = requests.post(
        f"{BASE}/projects/{PID}/tasks",
        headers=admin_h,
        json={
            "title": f"TEST_iter7_perm_{uuid.uuid4().hex[:6]}",
            "assigned_to": ctx["developer"]["id"],
            "assignee_ids": [ctx["developer"]["id"]],
        },
        timeout=20,
    )
    assert create.status_code == 200, create.text
    task = create.json()
    tid = task["id"]
    ctx["created"]["tasks"].append(tid)

    # non-assigned developer cannot edit
    d2_try = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{tid}",
        headers=d2_h,
        json={"status": "Dikerjakan"},
        timeout=20,
    )
    assert d2_try.status_code == 403

    # add second assignee then developer2 can update status/time/subtasks but not manager fields
    add_second = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{tid}",
        headers=admin_h,
        json={"assignee_ids": [ctx["developer"]["id"], ctx["developer2"]["id"]]},
        timeout=20,
    )
    assert add_second.status_code == 200, add_second.text

    d2_status = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{tid}",
        headers=d2_h,
        json={"status": "Dikerjakan"},
        timeout=20,
    )
    assert d2_status.status_code == 200, d2_status.text

    d2_time = requests.post(f"{BASE}/projects/{PID}/tasks/{tid}/time", headers=d2_h, json={"minutes": 5, "note": "iter7"}, timeout=20)
    assert d2_time.status_code == 200

    d2_sub = requests.post(f"{BASE}/projects/{PID}/tasks/{tid}/subtasks", headers=d2_h, json={"title": "from d2", "assigned_to": ""}, timeout=20)
    assert d2_sub.status_code == 200

    d2_title_forbidden = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{tid}",
        headers=d2_h,
        json={"title": "hijack"},
        timeout=20,
    )
    assert d2_title_forbidden.status_code == 403

    client_mutate = requests.patch(
        f"{BASE}/projects/{PID}/tasks/{tid}",
        headers=client_h,
        json={"status": "Selesai"},
        timeout=20,
    )
    assert client_mutate.status_code == 403

    foreign = requests.get(f"{BASE}/projects/{FOREIGN_PID}/tasks", headers=d2_h, timeout=20)
    assert foreign.status_code in (403, 404)


# --- dependencies ---
def test_dependency_rules_and_bulk_completion(ctx):
    h = _auth(ctx["admin"]["token"])

    a = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depA_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    b = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depB_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    c = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depC_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    d = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depD_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    e = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depE_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    f = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depF_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    x = requests.post(f"{BASE}/projects/{FOREIGN_PID}/tasks", headers=h, json={"title": f"TEST_iter7_foreign_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    for tid in [a["id"], b["id"], c["id"], d["id"], e["id"], f["id"]]:
        ctx["created"]["tasks"].append(tid)
    ctx["created"]["foreign_tasks"].append(x["id"])

    link = requests.patch(f"{BASE}/projects/{PID}/tasks/{b['id']}", headers=h, json={"dependencies": [a["id"]]}, timeout=20)
    assert link.status_code == 200, link.text
    assert link.json().get("dependencies") == [a["id"]]

    self_dep = requests.patch(f"{BASE}/projects/{PID}/tasks/{a['id']}", headers=h, json={"dependencies": [a["id"]]}, timeout=20)
    assert self_dep.status_code == 400

    cycle_1 = requests.patch(f"{BASE}/projects/{PID}/tasks/{d['id']}", headers=h, json={"dependencies": [c["id"]]}, timeout=20)
    assert cycle_1.status_code == 200
    cycle_2 = requests.patch(f"{BASE}/projects/{PID}/tasks/{c['id']}", headers=h, json={"dependencies": [d["id"]]}, timeout=20)
    assert cycle_2.status_code == 400

    foreign_dep = requests.patch(f"{BASE}/projects/{PID}/tasks/{a['id']}", headers=h, json={"dependencies": [x["id"]]}, timeout=20)
    assert foreign_dep.status_code == 400

    blocked = requests.patch(f"{BASE}/projects/{PID}/tasks/{b['id']}", headers=h, json={"status": "Selesai"}, timeout=20)
    assert blocked.status_code == 400
    finish_a = requests.patch(f"{BASE}/projects/{PID}/tasks/{a['id']}", headers=h, json={"status": "Selesai"}, timeout=20)
    assert finish_a.status_code == 200
    finish_b = requests.patch(f"{BASE}/projects/{PID}/tasks/{b['id']}", headers=h, json={"status": "Selesai"}, timeout=20)
    assert finish_b.status_code == 200

    dep_f = requests.patch(f"{BASE}/projects/{PID}/tasks/{f['id']}", headers=h, json={"dependencies": [e["id"]]}, timeout=20)
    assert dep_f.status_code == 200
    bulk = requests.post(
        f"{BASE}/projects/{PID}/tasks/bulk",
        headers=h,
        json={"ids": [e["id"], f["id"]], "status": "Selesai"},
        timeout=20,
    )
    assert bulk.status_code == 200, bulk.text

    # deleting prerequisite should remove stale dependency refs
    z = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depZ_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    y = requests.post(f"{BASE}/projects/{PID}/tasks", headers=h, json={"title": f"TEST_iter7_depY_{uuid.uuid4().hex[:4]}"}, timeout=20).json()
    ctx["created"]["tasks"].extend([z["id"], y["id"]])
    set_dep = requests.patch(f"{BASE}/projects/{PID}/tasks/{y['id']}", headers=h, json={"dependencies": [z["id"]]}, timeout=20)
    assert set_dep.status_code == 200
    del_z = requests.delete(f"{BASE}/projects/{PID}/tasks/{z['id']}", headers=h, timeout=20)
    assert del_z.status_code == 200
    tasks_now = requests.get(f"{BASE}/projects/{PID}/tasks", headers=h, timeout=20).json()
    y_now = next(t for t in tasks_now if t["id"] == y["id"])
    assert z["id"] not in (y_now.get("dependencies") or [])


def test_duplicate_task_and_manager_only(ctx):
    admin_h = _auth(ctx["admin"]["token"])
    d2_h = _auth(ctx["developer2"]["token"])

    pre = requests.post(
        f"{BASE}/projects/{PID}/tasks",
        headers=admin_h,
        json={"title": f"TEST_iter7_dup_pre_{uuid.uuid4().hex[:4]}"},
        timeout=20,
    ).json()
    src = requests.post(
        f"{BASE}/projects/{PID}/tasks",
        headers=admin_h,
        json={
            "title": f"TEST_iter7_dup_src_{uuid.uuid4().hex[:4]}",
            "description": "desc iter7",
            "assignee_ids": [ctx["developer"]["id"], ctx["developer2"]["id"]],
            "start_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
            "priority": "Mendesak",
            "tags": ["dup", "iter7"],
            "estimate_hours": 6,
            "subtasks": ["a", "b"],
            "dependencies": [pre["id"]],
        },
        timeout=20,
    ).json()
    ctx["created"]["tasks"].extend([pre["id"], src["id"]])

    # make source non-default status and one done subtask; duplicate should reset
    requests.patch(f"{BASE}/projects/{PID}/tasks/{src['id']}", headers=admin_h, json={"status": "Dikerjakan"}, timeout=20)
    if src.get("subtasks"):
        sid = src["subtasks"][0]["id"]
        requests.patch(f"{BASE}/projects/{PID}/tasks/{src['id']}/subtasks/{sid}", headers=admin_h, json={"done": True}, timeout=20)

    dup = requests.post(f"{BASE}/projects/{PID}/tasks/{src['id']}/duplicate", headers=admin_h, timeout=20)
    assert dup.status_code == 200, dup.text
    dj = dup.json()
    ctx["created"]["tasks"].append(dj["id"])
    assert "(salinan)" in dj["title"]
    assert dj["description"] == "desc iter7"
    assert set(dj.get("tags") or []) == {"dup", "iter7"}
    assert set(dj.get("assignee_ids") or []) == {ctx["developer"]["id"], ctx["developer2"]["id"]}
    assert dj.get("start_date") == date.today().isoformat()
    assert dj.get("due_date") == (date.today() + timedelta(days=2)).isoformat()
    assert dj.get("estimate_hours") == 6
    assert dj["status"] == "Belum Mulai"
    assert all(not s.get("done") for s in dj.get("subtasks") or [])
    assert all("source_id" not in s for s in dj.get("subtasks") or [])
    assert "time_entries" in dj and dj["time_entries"] == []

    non_manager = requests.post(f"{BASE}/projects/{PID}/tasks/{src['id']}/duplicate", headers=d2_h, timeout=20)
    assert non_manager.status_code in (403, 404)


def test_saved_views_scope_validation_crud(ctx):
    admin_h = _auth(ctx["admin"]["token"])
    ap_h = _auth(ctx["adminproject"]["token"])

    invalid_blank = requests.post(
        f"{BASE}/projects/{PID}/task-views",
        headers=admin_h,
        json={"name": "", "view": "list", "filters": {}},
        timeout=20,
    )
    assert invalid_blank.status_code == 422

    invalid_filters = requests.post(
        f"{BASE}/projects/{PID}/task-views",
        headers=admin_h,
        json={"name": "TEST_iter7_invalid", "view": "list", "filters": {"priority": "INVALID"}},
        timeout=20,
    )
    assert invalid_filters.status_code == 422

    name = f"TEST_iter7_view_{uuid.uuid4().hex[:6]}"
    create = requests.post(
        f"{BASE}/projects/{PID}/task-views",
        headers=admin_h,
        json={
            "name": name,
            "view": "timeline",
            "filters": {"mine": True, "priority": "Tinggi", "overdue": False, "status": "", "assignee": "", "q": "", "tag": ""},
        },
        timeout=20,
    )
    assert create.status_code == 200, create.text
    view = create.json()
    ctx["created"]["views"].append(view["id"])

    own = requests.get(f"{BASE}/projects/{PID}/task-views", headers=admin_h, timeout=20)
    assert own.status_code == 200
    assert any(v["id"] == view["id"] for v in own.json())

    other = requests.get(f"{BASE}/projects/{PID}/task-views", headers=ap_h, timeout=20)
    assert other.status_code == 200
    assert all(v["id"] != view["id"] for v in other.json())

    other_delete = requests.delete(f"{BASE}/projects/{PID}/task-views/{view['id']}", headers=ap_h, timeout=20)
    assert other_delete.status_code == 404

    own_delete = requests.delete(f"{BASE}/projects/{PID}/task-views/{view['id']}", headers=admin_h, timeout=20)
    assert own_delete.status_code == 200
