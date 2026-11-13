# Maintenance legacy rincian merge -> one Kanban card per maintenance; setup.sh download
import os, re, subprocess
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PID = "project-5"


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = a + b if op == "+" else a - b if op == "-" else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": "Maiharta123!", "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200: pytest.skip(f"login failed {r.status_code}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def admin(): return login("admin")


def tasks_for(admin, mid):
    return [t for t in admin.get(f"{BASE}/api/projects/{PID}/tasks").json() if t.get("source") == "maintenance" and t.get("source_id") == mid]


def check_merged(admin, m, title):
    ts = tasks_for(admin, m["id"])
    assert len(ts) == 1, [t["title"] for t in ts]
    t = ts[0]
    assert t["title"] == title
    assert m.get("task_id") == t["id"]
    assert "Rincian maintenance" not in (t.get("tags") or [])
    subs = t["subtasks"]
    titles = [s["title"] for s in subs]
    for x in ["Kondisi Saat ini", "cek", "Penyesuaian"]: assert x in titles, titles
    by = {s["title"]: s for s in subs}
    assert by["cek"]["parent_id"] == by["Kondisi Saat ini"]["id"]
    assert not by["Kondisi Saat ini"]["parent_id"] and not by["Penyesuaian"]["parent_id"]
    return t


def test_existing_legacy_merged(admin):
    rows = admin.get(f"{BASE}/api/projects/{PID}/work/maintenances").json()
    for title in ["LEGACY", "LEGACY2", "LEGACY3 Belum digabung"]:
        ms = [r for r in rows if r["title"].startswith(title) and (title != "LEGACY" or r["title"] in ("LEGACY", "LEGACY Rincian lama")) ]
        found = [r for r in rows if title.split()[0] in r["title"]]
        print(title, [(r["title"], len(tasks_for(admin, r["id"]))) for r in found])
    for r in rows:
        if "LEGACY" in r["title"] and not r.get("ticket_id"):
            assert len(tasks_for(admin, r["id"])) == 1, r["title"]


def test_no_separate_rincian_cards(admin):
    ts = admin.get(f"{BASE}/api/projects/{PID}/tasks").json()
    bad = [t["title"] for t in ts if t.get("source") == "maintenance" and t["title"] in ("Kondisi Saat ini", "Penyesuaian")]
    assert not bad, bad
    assert not [t for t in ts if "Rincian maintenance" in (t.get("tags") or [])]


@pytest.mark.parametrize("endpoint", [f"/api/projects/{PID}/work/maintenances", "/api/work/maintenances"])
def test_fresh_legacy_merge(admin, endpoint):
    title = f"TEST_LEGACY merge {endpoint.count('/')}"
    out = subprocess.run(["python3", "/app/backend/tests/seed_legacy_rincian.py", title], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    mid, t1, t2 = out.stdout.strip().split()[-3:]
    rows = admin.get(f"{BASE}{endpoint}").json()
    rows = rows if isinstance(rows, list) else rows.get("items", rows)
    m = next(r for r in rows if r["id"] == mid)
    t = check_merged(admin, m, title)
    assert t["id"] == t1
    assert admin.get(f"{BASE}/api/projects/{PID}/tasks/{t2}").status_code in (404, 405) or t2 not in [x["id"] for x in admin.get(f"{BASE}/api/projects/{PID}/tasks").json()]
    # idempotent
    admin.get(f"{BASE}{endpoint}")
    t_again = check_merged(admin, m, title)
    assert len(t_again["subtasks"]) == len(t["subtasks"])
    admin.delete(f"{BASE}/api/projects/{PID}/work/maintenances/{mid}")


def test_new_maintenance_single_card(admin):
    r = admin.post(f"{BASE}/api/projects/{PID}/work/maintenances", json={"title": "TEST_iter37 new", "kind": "Corrective", "priority": "Sedang",
                                                                          "subtasks": [{"title": "a", "children": [{"title": "a1"}]}, {"title": "b"}]})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    admin.get(f"{BASE}/api/projects/{PID}/work/maintenances")
    ts = tasks_for(admin, mid)
    assert len(ts) == 1 and ts[0]["title"] == "TEST_iter37 new"
    assert [s["title"] for s in ts[0]["subtasks"]] == ["a", "a1", "b"]
    admin.delete(f"{BASE}/api/projects/{PID}/work/maintenances/{mid}")


def test_setup_sh_download():
    r = requests.get(f"{BASE}/setup.sh")
    print(r.status_code, r.headers.get("content-type"), r.text[:80])
    assert r.status_code == 200 and r.text.startswith("#!")
