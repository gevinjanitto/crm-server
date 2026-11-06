# Maintenance -> single Kanban card with nested subtasks; edit appends subtasks; revisi regression
import os, re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "Maiharta123!"
PID = "project-5"


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = a + b if op == "+" else a - b if op == "-" else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD,
                                               "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    tok = r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin")


@pytest.fixture(scope="module")
def created(admin):
    before = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    payload = {"title": "TEST_Maint subtasks iter36", "description": "desc", "kind": "Corrective", "priority": "Sedang",
               "subtasks": [{"title": "TEST_sub A", "children": [{"title": "TEST_sub A1"}]}, {"title": "TEST_sub B"}]}
    r = admin.post(f"{BASE}/api/projects/{PID}/work/maintenances", json=payload)
    assert r.status_code == 200, r.text
    doc = r.json()
    yield {"doc": doc, "before": before}
    admin.delete(f"{BASE}/api/projects/{PID}/work/maintenances/{doc['id']}")


# Create maintenance -> exactly one kanban task with nested subtasks
def test_single_task_created(admin, created):
    doc = created["doc"]
    assert doc.get("task_id")
    tasks = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    assert len(tasks) == len(created["before"]) + 1
    linked = [t for t in tasks if t.get("source_id") == doc["id"]]
    assert len(linked) == 1
    t = linked[0]
    assert t["id"] == doc["task_id"]
    assert t["title"] == "TEST_Maint subtasks iter36"
    titles = [s["title"] for s in t["subtasks"]]
    assert titles == ["TEST_sub A", "TEST_sub A1", "TEST_sub B"]
    a = next(s for s in t["subtasks"] if s["title"] == "TEST_sub A")
    a1 = next(s for s in t["subtasks"] if s["title"] == "TEST_sub A1")
    assert a1["parent_id"] == a["id"]


# Listing maintenances: new record has task_id and details length <= 1; no split into extra tasks
def test_list_not_split(admin, created):
    doc = created["doc"]
    rows = admin.get(f"{BASE}/api/work/maintenances").json()
    row = next(r for r in rows if r["id"] == doc["id"])
    assert row["task_id"] == doc["task_id"]
    assert len(row.get("details") or []) <= 1
    rows2 = admin.get(f"{BASE}/api/projects/{PID}/work/maintenances").json()
    assert any(r["id"] == doc["id"] for r in rows2)
    tasks = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    assert len([t for t in tasks if t.get("source_id") == doc["id"]]) == 1


# Edit: add subtasks via tree endpoint appends to the same card
def test_append_subtasks(admin, created):
    doc = created["doc"]
    r = admin.post(f"{BASE}/api/projects/{PID}/tasks/{doc['task_id']}/subtasks/tree",
                   json={"items": [{"title": "TEST_sub C", "children": []}]})
    assert r.status_code == 200, r.text
    tasks = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    linked = [t for t in tasks if t.get("source_id") == doc["id"]]
    assert len(linked) == 1
    assert [s["title"] for s in linked[0]["subtasks"]][-1] == "TEST_sub C"
    assert len(linked[0]["subtasks"]) == 4


# Status update syncs task
def test_status_sync(admin, created):
    doc = created["doc"]
    r = admin.patch(f"{BASE}/api/projects/{PID}/work/maintenances/{doc['id']}", json={"status": "Development"})
    assert r.status_code == 200, r.text
    tasks = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    t = next(t for t in tasks if t["id"] == doc["task_id"])
    assert t["status"] == "Dikerjakan"


# Maintenance not allowed on non-Selesai project
def test_non_selesai_rejected(admin):
    projects = admin.get(f"{BASE}/api/projects").json()
    p = next((p for p in projects if p.get("status") != "Selesai"), None)
    if not p:
        pytest.skip("no non-selesai project")
    r = admin.post(f"{BASE}/api/projects/{p['id']}/work/maintenances", json={"title": "TEST_x maint", "kind": "Corrective"})
    assert r.status_code == 400


# Regression: revisi create with subtasks + edit + delete
def test_revision_regression(admin):
    r = admin.post(f"{BASE}/api/projects/{PID}/work/revisions",
                   json={"title": "TEST_Rev iter36", "kind": "In-scope", "subtasks": [{"title": "TEST_rs1"}]})
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        tasks = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
        t = next(t for t in tasks if t["id"] == doc["task_id"])
        assert [s["title"] for s in t["subtasks"]] == ["TEST_rs1"]
        u = admin.patch(f"{BASE}/api/projects/{PID}/work/revisions/{doc['id']}", json={"status": "Dikerjakan"})
        assert u.status_code == 200, u.text
    finally:
        d = admin.delete(f"{BASE}/api/projects/{PID}/work/revisions/{doc['id']}")
        assert d.status_code == 200


# Regression: notes
def test_notes_regression(admin):
    r = admin.get(f"{BASE}/api/notes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
