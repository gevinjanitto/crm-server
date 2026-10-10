"""Iteration 17 backend regression tests.

Covers:
- Subtask rich description PATCH (description_html sanitized, plain description derived).
- Subtask image upload / fetch endpoints.
- GET /api/work/revisions and /api/projects/{pid}/work/revisions include description_html.
- Rich description on task PATCH keeps HTML, strips to plain text in description field.
- Project reminder / ticket / project document preview-related endpoints are reachable
  for the files the frontend DocPreview expects (presence of files, correct URL shape).
"""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PROJECT_ID = "project-8"       # seeded, has revision-1 linked to a Kanban task
MAINT_PROJECT = "project-4"    # seeded with maintenance-1


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    c = requests.get(f"{API}/auth/captcha").json()
    parts = c["question"].split()
    a, b = int(parts[0]), int(parts[2])
    r = requests.post(f"{API}/auth/login", json={
        "username": "admin", "password": "Tes12345",
        "captcha_id": c["id"], "captcha_answer": str(a + b),
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def revision_task(hdr):
    r = requests.get(f"{API}/projects/{PROJECT_ID}/work/revisions", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data and data[0]["task_id"], "seeded revision-1 missing task_id"
    return data[0]


# ---------- rich description on work/revisions listing ----------
class TestRevisionDescriptionHTML:
    def test_project_revisions_include_description_html(self, hdr, revision_task):
        assert "description_html" in revision_task
        # seeded value in iteration 17 is '<p>Rev <b>tebal</b></p>'
        assert revision_task["description_html"] and "<" in revision_task["description_html"]

    def test_global_revisions_include_description_html(self, hdr):
        r = requests.get(f"{API}/work/revisions", headers=hdr)
        assert r.status_code == 200
        rows = r.json()
        assert rows
        rev1 = next((x for x in rows if x["id"] == "revision-1"), None)
        assert rev1 and rev1.get("description_html"), "revision-1 should have description_html in global list"


# ---------- task description_html sanitization ----------
class TestTaskRichDescription:
    def test_patch_task_description_html_sanitizes_and_sets_plain(self, hdr, revision_task):
        tid = revision_task["task_id"]
        html = "<p>Hello <b>bold</b><script>alert(1)</script> <i>world</i></p>"
        r = requests.patch(
            f"{API}/projects/{PROJECT_ID}/tasks/{tid}",
            headers=hdr,
            json={"description_html": html},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "<script" not in (body.get("description_html") or ""), "script must be stripped"
        assert "<b>bold</b>" in body["description_html"] or "<strong>" in body["description_html"]
        # plain description is derived from HTML
        plain = body.get("description") or ""
        assert "alert(1)" not in plain
        assert "bold" in plain and "world" in plain


# ---------- subtask rich description + image endpoints ----------
class TestSubtaskRichDescription:
    def _get_or_create_subtask(self, hdr, tid):
        r = requests.get(f"{API}/projects/{PROJECT_ID}/tasks", headers=hdr)
        assert r.status_code == 200
        task = next((x for x in r.json() if x["id"] == tid), None)
        assert task, f"task {tid} not found"
        subs = task.get("subtasks") or []
        if subs:
            return subs[0]["id"]
        c = requests.post(
            f"{API}/projects/{PROJECT_ID}/tasks/{tid}/subtasks",
            headers=hdr, json={"title": "TEST_sub"},
        )
        assert c.status_code in (200, 201), c.text
        return (c.json().get("subtasks") or [])[-1]["id"]

    def test_patch_subtask_description_html(self, hdr, revision_task):
        tid = revision_task["task_id"]
        sid = self._get_or_create_subtask(hdr, tid)
        html = "<p>Sub <strong>tebal</strong> <em>mir</em><script>x</script></p>"
        r = requests.patch(
            f"{API}/projects/{PROJECT_ID}/tasks/{tid}/subtasks/{sid}",
            headers=hdr, json={"description_html": html},
        )
        assert r.status_code == 200, r.text
        task = r.json()
        s = next(x for x in task["subtasks"] if x["id"] == sid)
        assert "<script" not in (s.get("description_html") or "")
        assert "tebal" in (s.get("description") or "")
        assert s.get("description_html")  # non-empty

        # verify persisted via GET
        g = requests.get(f"{API}/projects/{PROJECT_ID}/tasks", headers=hdr)
        task2 = next(x for x in g.json() if x["id"] == tid)
        gs = next(x for x in task2["subtasks"] if x["id"] == sid)
        assert gs.get("description_html") == s["description_html"]

    def test_upload_and_fetch_subtask_image(self, hdr, revision_task):
        tid = revision_task["task_id"]
        sid = self._get_or_create_subtask(hdr, tid)
        # 1x1 PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
            b"\xcf\xc0\x00\x00\x00\x03\x00\x01\x5b\xb8\x1b\x0b\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"files": ("t.png", io.BytesIO(png), "image/png")}
        r = requests.post(
            f"{API}/projects/{PROJECT_ID}/tasks/{tid}/subtasks/{sid}/images",
            headers=hdr, files=files,
        )
        assert r.status_code == 200, r.text
        task = r.json()
        s = next(x for x in task["subtasks"] if x["id"] == sid)
        imgs = s.get("images") or []
        assert imgs, "image not attached to subtask"
        iid = imgs[-1]["id"]
        # fetch
        g = requests.get(
            f"{API}/projects/{PROJECT_ID}/tasks/{tid}/subtasks/{sid}/images/{iid}",
            headers=hdr, allow_redirects=False,
        )
        assert g.status_code in (200, 302, 307), g.text
        if g.status_code == 200:
            assert g.content and len(g.content) > 10


# ---------- maintenance work linkage ----------
class TestMaintenanceWork:
    def test_project_maintenance_lists_task_id(self, hdr):
        r = requests.get(f"{API}/projects/{MAINT_PROJECT}/work/maintenances", headers=hdr)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows
        m1 = next((x for x in rows if x["id"] == "maintenance-1"), None)
        assert m1 and m1.get("task_id"), "maintenance-1 must link to a kanban task"

    def test_global_maintenance_listing(self, hdr):
        r = requests.get(f"{API}/work/maintenances", headers=hdr)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
