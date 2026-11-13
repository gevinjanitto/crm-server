# Iter41: doc mention notifications for any role, mentionable list, no-access mention rows, inbox
import os, re, time
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
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login {username} failed {r.status_code} {r.text}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    s.user = r.json()["user"]
    return s


@pytest.fixture(scope="module")
def S():
    return {n: login(n) for n in ["admin", "adminproject", "developer", "accounting", "client"]}


@pytest.fixture(scope="module")
def created(S):
    ids = []
    yield ids
    for pid, did in ids:
        S["admin"].delete(f"{BASE}/api/projects/{pid}/workspace/docs/{did}")


@pytest.fixture(scope="module")
def client_pid(S):
    cp = [p["id"] for p in S["admin"].get(f"{BASE}/api/projects").json() if p.get("client_id") == S["client"].user.get("client_id")]
    if not cp: pytest.skip("no client project")
    return cp[0]


@pytest.fixture(scope="module")
def nodev_pid(S):
    dp = {p["id"] for p in S["developer"].get(f"{BASE}/api/projects").json()}
    rest = [p["id"] for p in S["admin"].get(f"{BASE}/api/projects").json() if p["id"] not in dp]
    if not rest: pytest.skip("no project without developer")
    return rest[0]


def unread(s):
    r = s.get(f"{BASE}/api/notifications/unread-count"); assert r.status_code == 200; return r.json()["unread"]


def mention_notifs(s, doc_id):
    items = s.get(f"{BASE}/api/notifications", params={"unread": True}).json()["items"]
    return [n for n in items if n["kind"] == "mention" and n["entity_id"] == doc_id]


def mk(s, pid, content, vis="Internal", created=None):
    r = s.post(f"{BASE}/api/projects/{pid}/workspace/docs", json={"title": f"TMP iter41 {time.time()}", "content": content, "visibility": vis})
    assert r.status_code == 200, r.text
    d = r.json()
    if created is not None: created.append((pid, d["id"]))
    return d


# --- mentionable meta
def test_meta_mentionable_all_users(S, client_pid):
    r = S["adminproject"].get(f"{BASE}/api/projects/{client_pid}/workspace/meta")
    assert r.status_code == 200
    names = {m["username"] for m in r.json()["mentionable"]}
    for n in ["admin", "adminproject", "developer", "accounting", "client"]:
        assert n in names, f"{n} missing from mentionable {names}"


def test_meta_mentionable_nodev_project_includes_developer(S, nodev_pid):
    names = {m["username"] for m in S["admin"].get(f"{BASE}/api/projects/{nodev_pid}/workspace/meta").json()["mentionable"]}
    assert "developer" in names and "accounting" in names


# --- admin -> admin mention
def test_adminproject_tags_admin_creates_notification(S, client_pid, created):
    d = mk(S["adminproject"], client_pid, "<p>Halo @admin tolong cek</p>", created=created)
    time.sleep(0.5)
    ns = mention_notifs(S["admin"], d["id"])
    assert len(ns) == 1
    assert ns[0]["link"] == f"/projects/{client_pid}/docs?doc={d['id']}"


def test_retag_same_user_and_case_insensitive(S, client_pid, created):
    d = mk(S["adminproject"], client_pid, "<p>@admin satu</p>", created=created)
    r = S["adminproject"].patch(f"{BASE}/api/projects/{client_pid}/workspace/docs/{d['id']}",
                                json={"title": d["title"], "content": d["content"] + "<p>@Admin dua</p>", "visibility": "Internal", "version": d["version"]})
    assert r.status_code == 200, r.text
    time.sleep(0.5)
    assert len(mention_notifs(S["admin"], d["id"])) == 2
    # unchanged save -> no new notification
    d2 = r.json()
    r = S["adminproject"].patch(f"{BASE}/api/projects/{client_pid}/workspace/docs/{d['id']}",
                                json={"title": d2["title"], "content": d2["content"] + "<p>teks lain</p>", "visibility": "Internal", "version": d2["version"]})
    assert r.status_code == 200
    time.sleep(0.5)
    assert len(mention_notifs(S["admin"], d["id"])) == 2


def test_admin_tags_adminproject(S, client_pid, created):
    d = mk(S["admin"], client_pid, "<p>@adminproject cek</p>", created=created)
    time.sleep(0.5)
    assert len(mention_notifs(S["adminproject"], d["id"])) == 1


def test_self_mention_no_notification(S, client_pid, created):
    d = mk(S["admin"], client_pid, "<p>@admin catatan saya</p>", created=created)
    time.sleep(0.5)
    assert len(mention_notifs(S["admin"], d["id"])) == 0


# --- in_app disabled still receives mention
def test_mention_ignores_in_app_pref(S, client_pid, created):
    s = S["accounting"]
    pref = s.get(f"{BASE}/api/account/notifications").json()
    body = {k: pref[k] for k in ["in_app", "email", "whatsapp", "whatsapp_number"] if k in pref}
    try:
        r = s.patch(f"{BASE}/api/account/notifications", json={**body, "in_app": False})
        assert r.status_code == 200, r.text
        d = mk(S["admin"], client_pid, "<p>@accounting cek biaya</p>", created=created)
        time.sleep(0.5)
        ns = mention_notifs(s, d["id"])
        assert len(ns) == 1
        assert ns[0]["link"] == "/"  # accounting cannot open Internal doc
    finally:
        s.patch(f"{BASE}/api/account/notifications", json=body)


# --- no-access users
def test_developer_not_assigned_gets_notification_and_static_row(S, nodev_pid, created):
    d = mk(S["admin"], nodev_pid, "<p>@developer lihat ini TMPDEV</p>", created=created)
    time.sleep(0.5)
    ns = mention_notifs(S["developer"], d["id"])
    assert len(ns) == 1 and ns[0]["link"] == "/"
    rows = [m for m in S["developer"].get(f"{BASE}/api/notes/mentions/mine").json() if m["doc_id"] == d["id"]]
    assert len(rows) == 1 and rows[0]["can_open"] is False


def test_accounting_mentions_row_no_access(S, client_pid, created):
    d = mk(S["admin"], client_pid, "<p>@accounting internal TMPACC</p>", created=created)
    rows = [m for m in S["accounting"].get(f"{BASE}/api/notes/mentions/mine").json() if m["doc_id"] == d["id"]]
    assert len(rows) == 1 and rows[0]["can_open"] is False


def test_accounting_client_doc_can_open_consistent(S, client_pid, created):
    """If can_open is True for accounting on Client-visibility doc, accounting must really be able to GET docs."""
    d = mk(S["admin"], client_pid, "<p>@accounting client doc TMPACC2</p>", vis="Client", created=created)
    rows = [m for m in S["accounting"].get(f"{BASE}/api/notes/mentions/mine").json() if m["doc_id"] == d["id"]]
    assert len(rows) == 1
    r = S["accounting"].get(f"{BASE}/api/projects/{client_pid}/workspace/docs")
    really = r.status_code == 200 and any(x["id"] == d["id"] for x in r.json())
    assert rows[0]["can_open"] == really, f"can_open={rows[0]['can_open']} but docs GET status={r.status_code}"


def test_client_tagged_on_client_doc_gets_openable_link(S, client_pid, created):
    d = mk(S["admin"], client_pid, "<p>@client mohon review TMPCLI</p>", vis="Client", created=created)
    time.sleep(0.5)
    ns = mention_notifs(S["client"], d["id"])
    assert len(ns) == 1
    assert ns[0]["link"] == f"/projects/{client_pid}/docs?doc={d['id']}", f"client got link {ns[0]['link']}"
    rows = [m for m in S["client"].get(f"{BASE}/api/notes/mentions/mine").json() if m["doc_id"] == d["id"]]
    assert len(rows) == 1 and rows[0]["can_open"] is True


def test_client_tagged_on_internal_doc(S, client_pid, created):
    d = mk(S["admin"], client_pid, "<p>@client internal TMPCLI2</p>", created=created)
    time.sleep(0.5)
    ns = mention_notifs(S["client"], d["id"])
    assert len(ns) == 1 and ns[0]["link"] == "/"


# --- inbox
def test_inbox_lists_new_comment(S, client_pid):
    admin = S["admin"]
    tasks = admin.get(f"{BASE}/api/projects/{client_pid}/tasks")
    if tasks.status_code != 200 or not tasks.json(): pytest.skip("no tasks")
    t = tasks.json()[0]
    r = admin.post(f"{BASE}/api/projects/{client_pid}/tasks/{t['id']}/comments", json={"message": "TEST_iter41 inbox comment"})
    if r.status_code not in (200, 201): pytest.skip(f"comment create {r.status_code} {r.text[:200]}")
    cid = r.json().get("id")
    rows = S["adminproject"].get(f"{BASE}/api/inbox").json()["items"]
    row = next((x for x in rows if x["task_id"] == t["id"]), None)
    assert row and any(c["id"] == cid for c in row["comments"])
    assert row["unread"] >= 1
    admin.delete(f"{BASE}/api/projects/{client_pid}/tasks/{t['id']}/comments/{cid}")
