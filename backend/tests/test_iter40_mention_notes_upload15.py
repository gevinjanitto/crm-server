# Iter40: dashboard mention notes (/api/notes/mentions/mine) + 15 MB upload limits
import os, re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "Maiharta123!"
MB = 1024 * 1024


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = a + b if op == "+" else a - b if op == "-" else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login {username} failed {r.status_code} {r.text}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    s.user = r.json()["user"]
    return s


@pytest.fixture(scope="module")
def admin(): return login("admin")

@pytest.fixture(scope="module")
def dev(): return login("developer")

@pytest.fixture(scope="module")
def client(): return login("client")


@pytest.fixture(scope="module")
def shared_pid(admin, dev, client):
    dp = {p["id"] for p in dev.get(f"{BASE}/api/projects").json()}
    cp = [p["id"] for p in admin.get(f"{BASE}/api/projects").json() if p.get("client_id") == client.user.get("client_id")]
    both = [p for p in cp if p in dp]
    if not both: pytest.skip("no project shared by developer and client")
    return both[0]


@pytest.fixture(scope="module")
def created(admin):
    ids = []
    yield ids
    for pid, did in ids:
        admin.delete(f"{BASE}/api/projects/{pid}/workspace/docs/{did}")


def task_html(checked, who):
    chk = ' checked="checked"' if checked else ''
    return (f'<ul data-type="taskList"><li data-type="taskItem" data-checked="{"true" if checked else "false"}">'
            f'<label><input type="checkbox"{chk}><span></span></label>'
            f'<div><p>TEST_Kerjakan @{who}</p></div></li></ul>')


def mine(s): 
    r = s.get(f"{BASE}/api/notes/mentions/mine"); assert r.status_code == 200, r.text; return r.json()


# Mentions: checklist unchecked -> visible w/ checklist true; paragraph -> checklist false; check -> disappears
def test_mentions_checklist_flow(admin, dev, shared_pid, created):
    content = task_html(False, "developer") + "<p>TEST_Paragraf untuk @developer tolong cek</p><p>TEST_bukan @developerx</p><p>TEST_email a@developer</p>"
    r = admin.post(f"{BASE}/api/projects/{shared_pid}/workspace/docs", json={"title": "TEST_mention_doc", "content": content, "visibility": "Internal"})
    assert r.status_code == 200, r.text
    d = r.json(); created.append((shared_pid, d["id"]))
    rows = [m for m in mine(dev) if m["doc_id"] == d["id"]]
    assert len(rows) == 2, rows
    chk = [m for m in rows if m["checklist"]]; par = [m for m in rows if not m["checklist"]]
    assert len(chk) == 1 and "TEST_Kerjakan @developer" in chk[0]["text"]
    assert len(par) == 1 and "Paragraf" in par[0]["text"]
    for m in rows:
        assert m["project_id"] == shared_pid and m["doc_title"] == "TEST_mention_doc" and m["project_name"]
    # admin not mentioned
    assert not [m for m in mine(admin) if m["doc_id"] == d["id"]]
    # check item
    r2 = admin.patch(f"{BASE}/api/projects/{shared_pid}/workspace/docs/{d['id']}", json={"title": d["title"], "content": task_html(True, "developer") + "<p>TEST_Paragraf untuk @developer tolong cek</p>", "visibility": "Internal", "version": d["version"]})
    assert r2.status_code == 200, r2.text
    rows = [m for m in mine(dev) if m["doc_id"] == d["id"]]
    assert len(rows) == 1 and rows[0]["checklist"] is False, rows


# Client sees only docs with visibility Client
def test_client_visibility(admin, client, shared_pid, created):
    cu = client.user.get("username") or "client"
    r1 = admin.post(f"{BASE}/api/projects/{shared_pid}/workspace/docs", json={"title": "TEST_internal_c", "content": f"<p>TEST_int @{cu}</p>", "visibility": "Internal"})
    r2 = admin.post(f"{BASE}/api/projects/{shared_pid}/workspace/docs", json={"title": "TEST_client_c", "content": f"<p>TEST_cli @{cu}</p>", "visibility": "Client"})
    assert r1.status_code == 200 and r2.status_code == 200
    created.extend([(shared_pid, r1.json()["id"]), (shared_pid, r2.json()["id"])])
    ids = {m["doc_id"] for m in mine(client)}
    assert r2.json()["id"] in ids
    assert r1.json()["id"] not in ids


# Developer doesn't see mentions in projects not assigned to them
def test_dev_scope(admin, dev, created):
    dp = {p["id"] for p in dev.get(f"{BASE}/api/projects").json()}
    other = [p["id"] for p in admin.get(f"{BASE}/api/projects").json() if p["id"] not in dp]
    if not other: pytest.skip("no unassigned project")
    r = admin.post(f"{BASE}/api/projects/{other[0]}/workspace/docs", json={"title": "TEST_scope", "content": "<p>TEST @developer</p>", "visibility": "Internal"})
    assert r.status_code == 200; created.append((other[0], r.json()["id"]))
    assert r.json()["id"] not in {m["doc_id"] for m in mine(dev)}


def test_mentions_requires_auth():
    assert requests.get(f"{BASE}/api/notes/mentions/mine").status_code in (401, 403)


# ---- Upload limits 15 MB ----
@pytest.fixture(scope="module")
def task_ref(admin, shared_pid):
    r = admin.get(f"{BASE}/api/projects/{shared_pid}/tasks")
    if r.status_code != 200 or not r.json(): pytest.skip(f"no tasks {r.status_code}")
    return shared_pid, r.json()[0]["id"]


def test_task_comment_upload_limits(admin, task_ref):
    pid, tid = task_ref
    ok = admin.post(f"{BASE}/api/projects/{pid}/tasks/{tid}/comments/upload", data={"message": "TEST_15mb"}, files=[("files", ("TEST_14.txt", b"a" * (14 * MB), "text/plain"))])
    assert ok.status_code == 200, ok.text[:300]
    big = admin.post(f"{BASE}/api/projects/{pid}/tasks/{tid}/comments/upload", data={"message": "TEST_16mb"}, files=[("files", ("TEST_16.txt", b"a" * (15 * MB + 10), "text/plain"))])
    assert big.status_code == 400 and "15 MB" in big.text, big.text[:300]


def test_project_document_upload_limits(admin, shared_pid):
    ok = admin.post(f"{BASE}/api/projects/{shared_pid}/documents", data={"kind": "Lampiran Project", "visibility": "Internal", "name": "TEST_14mb"}, files={"file": ("TEST_14.txt", b"a" * (14 * MB), "text/plain")})
    assert ok.status_code == 200, ok.text[:300]
    admin.delete(f"{BASE}/api/projects/{shared_pid}/documents/{ok.json()['id']}")
    big = admin.post(f"{BASE}/api/projects/{shared_pid}/documents", data={"kind": "Lampiran Project", "visibility": "Internal"}, files={"file": ("TEST_16.txt", b"a" * (15 * MB + 10), "text/plain")})
    assert big.status_code == 400 and "15 MB" in big.text, big.text[:300]


def test_ticket_attachment_limits(client, admin):
    tickets = client.get(f"{BASE}/api/tickets").json()
    if not tickets: pytest.skip("no tickets for client")
    tid = None
    for t in tickets:
        full = client.get(f"{BASE}/api/tickets/{t['id']}").json()
        if len(full.get("attachments") or []) < 4: tid = t["id"]; break
    if not tid: pytest.skip("no ticket with room for attachments")
    ok = client.post(f"{BASE}/api/tickets/{tid}/attachments", files=[("files", ("TEST_14.txt", b"a" * (14 * MB), "text/plain"))])
    assert ok.status_code == 200, ok.text[:300]
    big = client.post(f"{BASE}/api/tickets/{tid}/attachments", files=[("files", ("TEST_16.txt", b"a" * (15 * MB + 10), "text/plain"))])
    assert big.status_code == 400 and "15 MB" in big.text, big.text[:300]
