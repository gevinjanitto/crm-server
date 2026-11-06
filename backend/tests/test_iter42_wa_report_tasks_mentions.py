# Iter42: WhatsApp report, admin tasks-by-user, unified mentions, admin dashboard finance removal
import os, re, pytest, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
PWD = "Maiharta123!"
TASK_ID = "8951e53f-0bd8-45c8-8eb9-560674f57b31"


def _login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/auth/captcha").json()
    a, op, b = re.match(r"\s*(\d+)\s*([+\-*x×])\s*(\d+)", cap["question"]).groups()
    ans = {"+": int(a) + int(b), "-": int(a) - int(b)}.get(op, int(a) * int(b))
    r = s.post(f"{BASE}/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login {username} failed {r.status_code} {r.text[:200]}")
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def sessions():
    return {u: _login(u) for u in ["admin", "adminproject", "developer", "accounting", "client"]}


# Dashboard finance only for Accounting
class TestDashboardFinance:
    def test_admin_no_finance(self, sessions):
        r = sessions["admin"].get(f"{BASE}/dashboard")
        assert r.status_code == 200
        assert "finance" not in r.json()

    def test_accounting_has_finance(self, sessions):
        r = sessions["accounting"].get(f"{BASE}/dashboard")
        assert r.status_code == 200
        f = r.json().get("finance")
        assert f and "profit" in f and "value" in f


# Unified mentions endpoint
class TestMentions:
    @pytest.mark.parametrize("user", ["admin", "adminproject", "developer", "accounting", "client"])
    def test_mentions_all_roles(self, sessions, user):
        r = sessions[user].get(f"{BASE}/mentions/mine")
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), list)

    def test_old_notes_mentions(self, sessions):
        r = sessions["admin"].get(f"{BASE}/notes/mentions/mine")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_mentions_include_sources(self, sessions):
        data = sessions["admin"].get(f"{BASE}/mentions/mine").json()
        srcs = {m["source"] for m in data}
        print("admin mention sources:", srcs, len(data))
        tc = [m for m in data if m["source"] == "task_comment"]
        tk = [m for m in data if m["source"] == "ticket_comment"]
        assert tc, "expected task comment mention for admin"
        assert tk, "expected ticket comment mention for admin"
        assert any(TASK_ID in m["link"] and m["link"].startswith("/projects/project-2/kanban?task=") for m in tc)
        assert all(m["source_label"] == "Komentar task" for m in tc)
        assert all(m["source_label"] == "Komentar tiket" for m in tk)
        for m in data:
            assert m["source_label"] in ("Notes", "Komentar task", "Komentar tiket")
            for k in ("id", "text", "link", "project_name", "location", "can_open"):
                assert k in m

    def test_unique_ids(self, sessions):
        data = sessions["admin"].get(f"{BASE}/mentions/mine").json()
        ids = [m["id"] for m in data]
        assert len(ids) == len(set(ids))


# Admin tasks grouped by user
class TestTasksByUser:
    def test_admin_ok(self, sessions):
        r = sessions["admin"].get(f"{BASE}/admin/tasks-by-user")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and data
        for g in data:
            assert {"user_id", "name", "role", "tasks"} <= set(g)
            for t in g["tasks"]:
                assert {"id", "project_id", "project_name", "title", "status"} <= set(t)

    def test_only_unfinished(self, sessions):
        s = sessions["admin"]
        data = s.get(f"{BASE}/admin/tasks-by-user").json()
        statuses = {t["status"] for g in data for t in g["tasks"]}
        print("statuses:", statuses)
        assert not ({"Selesai", "Done", "done", "Complete"} & statuses)

    @pytest.mark.parametrize("user", ["adminproject", "developer", "accounting", "client"])
    def test_non_admin_403(self, sessions, user):
        assert sessions[user].get(f"{BASE}/admin/tasks-by-user").status_code == 403


# WhatsApp report (not configured in preview)
class TestWhatsAppReport:
    def test_report_not_configured(self, sessions):
        r = sessions["admin"].get(f"{BASE}/admin/whatsapp-report")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["configuration_note"]
        assert d["messages"] == []
        assert isinstance(d["crm_failures"], list)

    def test_report_failed_filter(self, sessions):
        r = sessions["admin"].get(f"{BASE}/admin/whatsapp-report?status=failed")
        assert r.status_code == 200

    def test_resend_400(self, sessions):
        r = sessions["admin"].post(f"{BASE}/admin/whatsapp-report/resend", json={"message_sid": "SMxxx"})
        assert r.status_code == 400
        assert r.json().get("detail")

    @pytest.mark.parametrize("user", ["adminproject", "developer", "accounting", "client"])
    def test_non_admin_403(self, sessions, user):
        s = sessions[user]
        assert s.get(f"{BASE}/admin/whatsapp-report").status_code == 403
        assert s.post(f"{BASE}/admin/whatsapp-report/resend", json={"message_sid": "SMx"}).status_code == 403
