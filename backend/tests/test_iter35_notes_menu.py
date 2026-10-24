# Notes menu (read-only aggregated project notes) - GET /api/notes + setup.sh download + regression
import os, re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "Maiharta123!"


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = a + b if op == "+" else a - b if op == "-" else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD,
                                               "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login {username} failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin")


@pytest.fixture(scope="module")
def dev():
    return login("developer")


# Admin sees all notes with project info
def test_notes_admin(admin):
    r = admin.get(f"{BASE}/api/notes")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 3
    for n in rows:
        assert "_id" not in n
        assert n["project_name"] and n["project_code"]
        assert n["project_id"] and n["id"] and "title" in n
    assert len({n["project_id"] for n in rows}) >= 2
    ts = [n["updated_at"] for n in rows]
    assert ts == sorted(ts, reverse=True)


# Admin /api/notes matches per-project docs endpoint
def test_notes_match_project_docs(admin):
    rows = admin.get(f"{BASE}/api/notes").json()
    pids = {n["project_id"] for n in rows}
    for pid in pids:
        docs = admin.get(f"{BASE}/api/projects/{pid}/workspace/docs")
        assert docs.status_code == 200
        assert {d["id"] for d in docs.json()} == {n["id"] for n in rows if n["project_id"] == pid}


# Developer sees only assigned projects
def test_notes_developer_scope(admin, dev):
    r = dev.get(f"{BASE}/api/notes")
    assert r.status_code == 200
    rows = r.json()
    me = dev.get(f"{BASE}/api/auth/me").json()
    uid = me.get("id") or me.get("user", {}).get("id")
    projects = admin.get(f"{BASE}/api/projects").json()
    assigned = {p["id"] for p in projects if uid in (p.get("assigned_to") or [])}
    assert all(n["project_id"] in assigned for n in rows)
    all_rows = admin.get(f"{BASE}/api/notes").json()
    expected = {n["id"] for n in all_rows if n["project_id"] in assigned}
    assert {n["id"] for n in rows} == expected


@pytest.mark.parametrize("username", ["accounting", "client"])
def test_notes_other_roles_no_error(username):
    s = login(username)
    r = s.get(f"{BASE}/api/notes")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        for n in r.json():
            assert n.get("visibility") == "Client"


def test_notes_unauth():
    r = requests.get(f"{BASE}/api/notes")
    assert r.status_code == 401


def test_setup_sh_download():
    r = requests.get(f"{BASE}/setup.sh")
    assert r.status_code == 200
    assert r.text.startswith("#!")
    assert len(r.content) > 100000


# Regression: maintenance list still works
def test_maintenance_regression(admin):
    r = admin.get(f"{BASE}/api/work/maintenances")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
