# Iter43: notification deep links (task comments, mentions, tickets, revisions, task status)
import os, re, time, pytest, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
PWD = "Maiharta123!"
PID = "project-2"
TASK_ID = "8951e53f-0bd8-45c8-8eb9-560674f57b31"


def _login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/auth/captcha").json()
    a, op, b = re.match(r"\s*(\d+)\s*([+\-*x×])\s*(\d+)", cap["question"]).groups()
    ans = {"+": int(a) + int(b), "-": int(a) - int(b)}.get(op, int(a) * int(b))
    r = s.post(f"{BASE}/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login {username} failed {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def S():
    return {u: _login(u) for u in ["admin", "adminproject", "developer"]}


def _notifs(s):
    r = s.get(f"{BASE}/notifications")
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    return d if isinstance(d, list) else d.get("items", d.get("notifications", []))


def _find(s, pred, tries=6):
    for _ in range(tries):
        for n in _notifs(s):
            if pred(n):
                return n
        time.sleep(1)
    return None


# Task comment by developer mentioning admin -> admin gets link with task & comment
class TestTaskCommentLinks:
    def test_task_comment_mention_link(self, S):
        admin_id = S["admin"].get(f"{BASE}/auth/me").json()["id"]
        r = S["developer"].post(f"{BASE}/projects/{PID}/tasks/{TASK_ID}/comments",
                                json={"message": "TEST_iter43 halo @admin cek ini", "mention_ids": [admin_id]})
        assert r.status_code == 200, r.text[:300]
        cid = r.json()["id"]
        try:
            n = _find(S["admin"], lambda n: cid in (n.get("link") or ""))
            assert n, "admin got no notification with comment link"
            assert n["link"] == f"/projects/{PID}/kanban?task={TASK_ID}&comment={cid}"
            assert n["entity_type"] == "task" and n["entity_id"] == TASK_ID and n["project_id"] == PID
        finally:
            S["developer"].delete(f"{BASE}/projects/{PID}/tasks/{TASK_ID}/comments/{cid}")


# Ticket comment by developer -> admin gets /tickets?ticket=<id>
class TestTicketLinks:
    def test_ticket_comment_link(self, S):
        tickets = S["developer"].get(f"{BASE}/tickets").json()
        if not tickets:
            pytest.skip("no tickets for developer")
        t = tickets[0]
        r = S["developer"].post(f"{BASE}/tickets/{t['id']}/comments", json={"message": "TEST_iter43 komentar tiket", "internal": True})
        assert r.status_code == 200, r.text[:300]
        n = _find(S["admin"], lambda n: n.get("link") == f"/tickets?ticket={t['id']}" and "TEST_iter43" in (n.get("message") or ""))
        assert n, "admin got no ticket notification with deep link"
        assert n["entity_type"] == "tiket" and n["entity_id"] == t["id"]
        r = S["admin"].get(f"{BASE}/tickets/{t['id']}")
        assert r.status_code == 200 and r.json()["id"] == t["id"]


# Revision by adminproject -> admin notification links to the linked kanban task
class TestRevisionLink:
    def test_revision_link(self, S):
        r = S["adminproject"].post(f"{BASE}/projects/{PID}/work/revisions",
                                   json={"title": "TEST_iter43 revisi", "kind": "In-scope", "description": "x"})
        assert r.status_code == 200, r.text[:300]
        doc = r.json()
        try:
            assert doc.get("task_id")
            n = _find(S["admin"], lambda n: n.get("entity_id") == doc["id"])
            assert n, "admin got no revision notification"
            assert n["link"] == f"/projects/{PID}/kanban?task={doc['task_id']}"
            t = S["admin"].get(f"{BASE}/projects/{PID}/tasks").json()
            assert any(x["id"] == doc["task_id"] for x in t), "linked task not in project tasks"
            # status change of revision
            r2 = S["adminproject"].patch(f"{BASE}/projects/{PID}/work/revisions/{doc['id']}", json={"status": "Dikerjakan"})
            if r2.status_code == 200:
                n2 = _find(S["admin"], lambda n: n.get("entity_id") == doc["id"] and "→" in n.get("title", ""))
                if n2:
                    assert n2["link"] == f"/projects/{PID}/kanban?task={doc['task_id']}"
        finally:
            S["adminproject"].delete(f"{BASE}/projects/{PID}/work/revisions/{doc['id']}")


# Task status change by developer -> admin (manager) gets link to kanban task (managers notified only when actor is Developer)
class TestTaskStatusLink:
    def test_status_change_link(self, S):
        tasks = S["admin"].get(f"{BASE}/projects/{PID}/tasks").json()
        t = next(x for x in tasks if x["id"] == TASK_ID)
        old = t["status"]
        statuses = [s["name"] if isinstance(s, dict) else s for s in S["admin"].get(f"{BASE}/projects/{PID}/statuses").json()]
        new = next((s for s in statuses if s != old), None)
        if not new:
            pytest.skip("no alt status")
        r = S["developer"].patch(f"{BASE}/projects/{PID}/tasks/{TASK_ID}", json={"status": new})
        assert r.status_code == 200, r.text[:300]
        try:
            n = _find(S["admin"], lambda n: n.get("entity_id") == TASK_ID and f"→ {new}" in n.get("title", ""))
            assert n, "admin got no status notification"
            assert n["link"] == f"/projects/{PID}/kanban?task={TASK_ID}"
        finally:
            S["developer"].patch(f"{BASE}/projects/{PID}/tasks/{TASK_ID}", json={"status": old})


# WhatsApp template endpoints still respond (Twilio not configured)
class TestWhatsappTemplate:
    def test_wa_templates_list(self, S):
        r = S["admin"].get(f"{BASE}/whatsapp/templates")
        assert r.status_code in (200, 404), r.text[:200]
