"""Iteration 5 regression: reCAPTCHA, Platforms, Maintenance new fields, Trash, Audit."""
import os, sys, subprocess, requests, pytest
from pathlib import Path

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def _tok(u):
    return subprocess.check_output([sys.executable, "/app/tests/make_token.py", u]).decode().strip()


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": "Bearer " + _tok("admin")}


@pytest.fixture(scope="module")
def ap_h():
    return {"Authorization": "Bearer " + _tok("adminproject")}


# ------------------ AUTH / captcha ------------------
def test_captcha_endpoint_is_recaptcha():
    r = requests.get(f"{BASE}/auth/captcha")
    assert r.status_code == 200
    data = r.json()
    assert data.get("provider") == "recaptcha"
    assert data.get("site_key")


def test_login_invalid_recaptcha_returns_400():
    r = requests.post(f"{BASE}/auth/login", json={
        "username": "admin", "password": os.environ.get("SEED_PASSWORD", ""), "recaptcha_token": "invalid_xxx"
    })
    assert r.status_code == 400


# ------------------ PROJECTS / platforms ------------------
@pytest.fixture(scope="module")
def created_project(admin_h):
    cl = requests.get(f"{BASE}/clients", headers=admin_h).json()[0]
    r = requests.post(f"{BASE}/projects", headers=admin_h, json={
        "name": "TEST_iter5_platform", "client_id": cl["id"],
        "platforms": ["Web", "Mobile Android"],
        "start_date": "2026-06-01", "due_date": "2026-09-01",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_project_platforms_and_category(created_project):
    assert created_project["platforms"] == ["Web", "Mobile Android"]
    assert "Web" in created_project["category"] and "Mobile Android" in created_project["category"]


def test_project_empty_platforms_rejected(admin_h):
    cl = requests.get(f"{BASE}/clients", headers=admin_h).json()[0]
    r = requests.post(f"{BASE}/projects", headers=admin_h, json={
        "name": "TEST_iter5_noplat", "client_id": cl["id"], "platforms": [],
        "start_date": "2026-06-01", "due_date": "2026-09-01",
    })
    assert r.status_code == 422


def test_all_projects_have_platforms(admin_h):
    projs = requests.get(f"{BASE}/projects", headers=admin_h).json()
    assert all("platforms" in p for p in projs)


# ------------------ Upload lampiran ------------------
def test_upload_and_download_lampiran(admin_h, created_project):
    files = {"file": ("lamp.txt", b"hello-lamp", "text/plain")}
    r = requests.post(f"{BASE}/projects/{created_project['id']}/documents",
                      headers=admin_h, files=files,
                      data={"kind": "Lampiran Project", "visibility": "Internal"})
    assert r.status_code == 200
    did = r.json()["id"]
    d = requests.get(f"{BASE}/projects/{created_project['id']}/documents/{did}/download", headers=admin_h)
    assert d.status_code == 200 and d.content == b"hello-lamp"


# ------------------ Maintenance ------------------
@pytest.fixture(scope="module")
def prod_project(admin_h):
    prod = [p for p in requests.get(f"{BASE}/projects", headers=admin_h).json() if p.get("production_at")]
    assert prod, "need a production project seed"
    return prod[0]


def test_maintenance_create_default_status(admin_h, prod_project):
    r = requests.post(f"{BASE}/projects/{prod_project['id']}/work/maintenances", headers=admin_h, json={
        "title": "TEST_iter5_maint1", "kind": "Adaptive", "priority": "Tinggi",
        "entry_date": "2026-06-10", "started_date": None, "due_date": None, "estimate": 0,
    })
    assert r.status_code == 200
    m = r.json()
    assert m["status"] == "Belum dikerjakan"
    assert m["priority"] == "Tinggi"
    # linked task
    tasks = requests.get(f"{BASE}/projects/{prod_project['id']}/tasks", headers=admin_h).json()
    linked = [t for t in tasks if t["source_id"] == m["id"]]
    assert linked and linked[0]["priority"] == "Tinggi"
    requests.delete(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{m['id']}", headers=admin_h)


def test_maintenance_started_date_forces_development(admin_h, prod_project):
    r = requests.post(f"{BASE}/projects/{prod_project['id']}/work/maintenances", headers=admin_h, json={
        "title": "TEST_iter5_maint_started", "kind": "Adaptive", "priority": "Sedang",
        "entry_date": "2026-06-10", "started_date": "2026-06-12", "due_date": None, "estimate": 0,
    })
    assert r.status_code == 200
    m = r.json()
    assert m["status"] == "Development"
    requests.delete(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{m['id']}", headers=admin_h)


def test_maintenance_status_transitions_and_task_sync(admin_h, prod_project):
    r = requests.post(f"{BASE}/projects/{prod_project['id']}/work/maintenances", headers=admin_h, json={
        "title": "TEST_iter5_maint_sync", "kind": "Adaptive", "priority": "Sedang",
        "entry_date": "2026-06-10", "started_date": None, "due_date": None, "estimate": 0,
    })
    m = r.json(); mid = m["id"]
    for status, task_expected in [("Development", "Dikerjakan"), ("Testing", "Testing"), ("Selesai", "Selesai")]:
        rr = requests.patch(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{mid}",
                            headers=admin_h, json={"status": status})
        assert rr.status_code == 200 and rr.json()["status"] == status
        tasks = requests.get(f"{BASE}/projects/{prod_project['id']}/tasks", headers=admin_h).json()
        t = [x for x in tasks if x["source_id"] == mid][0]
        assert t["status"] == task_expected
    # invalid status
    bad = requests.patch(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{mid}",
                        headers=admin_h, json={"status": "Terbuka"})
    assert bad.status_code == 400
    requests.delete(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{mid}", headers=admin_h)


def test_task_to_maintenance_reverse_sync(admin_h, prod_project):
    r = requests.post(f"{BASE}/projects/{prod_project['id']}/work/maintenances", headers=admin_h, json={
        "title": "TEST_iter5_reverse", "kind": "Adaptive", "priority": "Sedang",
        "entry_date": "2026-06-10", "started_date": None, "due_date": None, "estimate": 0,
    })
    mid = r.json()["id"]
    tasks = requests.get(f"{BASE}/projects/{prod_project['id']}/tasks", headers=admin_h).json()
    t = [x for x in tasks if x["source_id"] == mid][0]
    upd = requests.patch(f"{BASE}/projects/{prod_project['id']}/tasks/{t['id']}", headers=admin_h,
                        json={"status": "Selesai"})
    assert upd.status_code == 200
    ml = requests.get(f"{BASE}/projects/{prod_project['id']}/work/maintenances", headers=admin_h).json()
    assert [x for x in ml if x["id"] == mid][0]["status"] == "Selesai"
    requests.delete(f"{BASE}/projects/{prod_project['id']}/work/maintenances/{mid}", headers=admin_h)


# ------------------ Trash & Audit ------------------
def test_trash_restore_and_permissions(admin_h, ap_h, created_project):
    # create a doc, delete it, restore
    files = {"file": ("t.txt", b"data", "text/plain")}
    up = requests.post(f"{BASE}/projects/{created_project['id']}/documents",
                      headers=admin_h, files=files,
                      data={"kind": "Lampiran Project", "visibility": "Internal"}).json()
    requests.delete(f"{BASE}/projects/{created_project['id']}/documents/{up['id']}", headers=admin_h)
    tr = requests.get(f"{BASE}/trash", headers=admin_h).json()
    item = [x for x in tr if x["entity_type"] == "dokumen" and x.get("name") == "t.txt"]
    assert item
    tid = item[0]["id"]
    # adminproject cannot purge
    r = requests.delete(f"{BASE}/trash/{tid}", headers=ap_h)
    assert r.status_code == 403
    # admin restore
    r = requests.post(f"{BASE}/trash/{tid}/restore", headers=admin_h)
    assert r.status_code == 200


def test_audit_admin_only_and_filter(admin_h, ap_h):
    assert requests.get(f"{BASE}/audit", headers=ap_h).status_code == 403
    r = requests.get(f"{BASE}/audit?entity_type=task&limit=5", headers=admin_h)
    assert r.status_code == 200
    data = r.json()
    assert all(x["entity_type"] == "task" for x in data)


# cleanup created project
def test_zzz_cleanup(admin_h, created_project):
    # move to trash then purge
    requests.delete(f"{BASE}/projects/{created_project['id']}", headers=admin_h)
    tr = requests.get(f"{BASE}/trash", headers=admin_h).json()
    for it in tr:
        if it["entity_type"] == "project" and it["name"] == "TEST_iter5_platform":
            requests.delete(f"{BASE}/trash/{it['id']}", headers=admin_h)
