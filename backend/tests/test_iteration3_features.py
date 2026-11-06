"""Iteration 3: kanban tasks, cost types/expenses, work-task sync, ticket-task sync, auto client account."""

import os
import re
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENV = dotenv_values("/app/backend/.env")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or ENV.get("SEED_PASSWORD")


def solve(q):
    return str(sum(int(n) for n in re.findall(r"\d+", q)))


def login(session, username, password):
    c = session.get(f"{BASE_URL}/api/auth/captcha", timeout=15).json()
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password,
              "captcha_id": c["id"], "captcha_answer": solve(c["question"]), "remember": False},
        timeout=20,
    )
    return r


def auth(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="session")
def s():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return requests.Session()


@pytest.fixture(scope="session")
def tokens(s):
    out = {}
    for u in ["admin", "adminproject", "developer", "accounting", "client"]:
        r = login(s, u, SEED_PASSWORD)
        assert r.status_code == 200, f"{u}: {r.text}"
        out[u] = r.json()["token"]
    return out


# ---- Kanban tasks ----
class TestKanbanTasks:
    def test_admin_create_task_with_subtasks(self, s, tokens):
        h = auth(tokens["admin"])
        payload = {
            "title": f"TEST_task_{uuid.uuid4().hex[:6]}",
            "assigned_to": "user-developer",
            "subtasks": ["step a", "step b"],
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
        }
        r = s.post(f"{BASE_URL}/api/projects/project-1/tasks", headers=h, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["subtasks"]) == 2
        assert data["assigned_name"] == "Kadek Putra"
        assert data["status"] == "Belum Mulai"
        assert data["server"] == "Belum Naik"
        pytest.tid = data["id"]

        # GET /api/tasks includes it
        all_tasks = s.get(f"{BASE_URL}/api/tasks", headers=h, timeout=20).json()
        assert any(t["id"] == data["id"] for t in all_tasks)
        # project scope
        proj_tasks = s.get(f"{BASE_URL}/api/projects/project-1/tasks", headers=h, timeout=20).json()
        assert any(t["id"] == data["id"] for t in proj_tasks)

    def test_admin_patch_status_and_server(self, s, tokens):
        h = auth(tokens["admin"])
        tid = pytest.tid
        r = s.patch(f"{BASE_URL}/api/projects/project-1/tasks/{tid}", headers=h,
                    json={"status": "Dikerjakan", "server": "Dev Server"}, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "Dikerjakan"
        assert j["server"] == "Dev Server"

    def test_subtasks_crud_and_toggle(self, s, tokens):
        h = auth(tokens["admin"])
        tid = pytest.tid
        # Add subtask
        r = s.post(f"{BASE_URL}/api/projects/project-1/tasks/{tid}/subtasks", headers=h,
                   json={"title": "TEST_extra_sub", "assigned_to": ""}, timeout=20)
        assert r.status_code == 200
        subs = r.json()["subtasks"]
        new_sub = next(s2 for s2 in subs if s2["title"] == "TEST_extra_sub")
        # Toggle done
        r2 = s.patch(f"{BASE_URL}/api/projects/project-1/tasks/{tid}/subtasks/{new_sub['id']}",
                     headers=h, json={"done": True}, timeout=20)
        assert r2.status_code == 200
        toggled = next(x for x in r2.json()["subtasks"] if x["id"] == new_sub["id"])
        assert toggled["done"] is True
        # Delete
        r3 = s.delete(f"{BASE_URL}/api/projects/project-1/tasks/{tid}/subtasks/{new_sub['id']}",
                      headers=h, timeout=20)
        assert r3.status_code == 200

    def test_developer_status_ok_title_forbidden(self, s, tokens):
        h = auth(tokens["developer"])
        tid = pytest.tid
        # PATCH status allowed
        r = s.patch(f"{BASE_URL}/api/projects/project-1/tasks/{tid}", headers=h,
                    json={"status": "Testing"}, timeout=20)
        assert r.status_code == 200
        # PATCH title forbidden
        r2 = s.patch(f"{BASE_URL}/api/projects/project-1/tasks/{tid}", headers=h,
                     json={"title": "hijacked"}, timeout=20)
        assert r2.status_code == 403

    def test_client_read_only(self, s, tokens):
        h = auth(tokens["client"])
        assert s.get(f"{BASE_URL}/api/tasks", headers=h, timeout=20).status_code == 200
        r = s.post(f"{BASE_URL}/api/projects/project-1/tasks", headers=h,
                   json={"title": "should fail"}, timeout=20)
        assert r.status_code == 403

    def test_delete_task(self, s, tokens):
        h = auth(tokens["admin"])
        tid = pytest.tid
        r = s.delete(f"{BASE_URL}/api/projects/project-1/tasks/{tid}", headers=h, timeout=20)
        assert r.status_code == 200


# ---- Revision -> task sync ----
class TestRevisionTaskSync:
    def test_create_revision_creates_task_and_sync(self, s, tokens):
        h = auth(tokens["admin"])
        payload = {
            "title": f"TEST_rev_{uuid.uuid4().hex[:6]}",
            "description": "sync test",
            "kind": "In-scope",
            "assigned_to": "user-developer",
            "due_date": (date.today() + timedelta(days=4)).isoformat(),
            "estimate": 0,
            "subtasks": ["x"],
        }
        r = s.post(f"{BASE_URL}/api/projects/project-1/work/revisions", headers=h, json=payload, timeout=25)
        assert r.status_code == 200, r.text
        rev = r.json()
        assert rev.get("task_id")
        pytest.rev_id = rev["id"]
        pytest.rev_task_id = rev["task_id"]

        tasks = s.get(f"{BASE_URL}/api/projects/project-1/tasks", headers=h, timeout=20).json()
        t = next((x for x in tasks if x["id"] == rev["task_id"]), None)
        assert t and t["status"] == "Revisi" and t["source"] == "revision"

    def test_patch_revision_syncs_task(self, s, tokens):
        h = auth(tokens["admin"])
        r = s.patch(f"{BASE_URL}/api/projects/project-1/work/revisions/{pytest.rev_id}",
                    headers=h, json={"status": "Dikerjakan", "approved": True}, timeout=20)
        assert r.status_code == 200
        tasks = s.get(f"{BASE_URL}/api/projects/project-1/tasks", headers=h, timeout=20).json()
        t = next(x for x in tasks if x["id"] == pytest.rev_task_id)
        assert t["status"] == "Dikerjakan"

    def test_patch_task_selesai_syncs_revision(self, s, tokens):
        h = auth(tokens["admin"])
        r = s.patch(f"{BASE_URL}/api/projects/project-1/tasks/{pytest.rev_task_id}",
                    headers=h, json={"status": "Selesai"}, timeout=20)
        assert r.status_code == 200
        revs = s.get(f"{BASE_URL}/api/projects/project-1/work/revisions", headers=h, timeout=20).json()
        rev = next(x for x in revs if x["id"] == pytest.rev_id)
        assert rev["status"] == "Selesai"


# ---- Ticket accepted -> task ----
class TestTicketTaskAndNotifications:
    def test_ticket_accept_creates_task_and_notification(self, s, tokens):
        client_h = auth(tokens["client"])
        admin_h = auth(tokens["admin"])
        # Create a fresh ticket as client
        r = s.post(f"{BASE_URL}/api/tickets", headers=client_h, json={
            "project_id": "project-1", "title": f"TEST_tkt_{uuid.uuid4().hex[:6]}",
            "description": "test task from ticket", "category": "Bug / Problem", "priority": "Sedang",
        }, timeout=20)
        assert r.status_code == 200
        tid = r.json()["id"]
        # Baru -> Ditinjau
        assert s.patch(f"{BASE_URL}/api/tickets/{tid}", headers=admin_h,
                       json={"status": "Ditinjau", "assigned_to": "user-developer"}, timeout=20).status_code == 200
        # Ditinjau -> Diterima
        r3 = s.patch(f"{BASE_URL}/api/tickets/{tid}", headers=admin_h,
                     json={"status": "Diterima", "assigned_to": "user-developer"}, timeout=20)
        assert r3.status_code == 200, r3.text
        body = r3.json()
        assert body.get("task_id")
        # Task exists
        tasks = s.get(f"{BASE_URL}/api/projects/project-1/tasks", headers=admin_h, timeout=20).json()
        t = next(x for x in tasks if x["id"] == body["task_id"])
        assert t["source"] == "ticket"
        # Notifications list has a skipped entry
        notifs = s.get(f"{BASE_URL}/api/notifications", headers=admin_h, timeout=20).json()
        assert isinstance(notifs, list)
        assert any(n.get("status") == "skipped" for n in notifs)


# ---- Cost types & expenses ----
class TestCostTypesExpenses:
    def test_admin_project_forbidden(self, s, tokens):
        r = s.get(f"{BASE_URL}/api/cost-types", headers=auth(tokens["adminproject"]), timeout=20)
        assert r.status_code == 403

    def test_admin_accounting_can_list(self, s, tokens):
        for role in ["admin", "accounting"]:
            r = s.get(f"{BASE_URL}/api/cost-types", headers=auth(tokens[role]), timeout=20)
            assert r.status_code == 200

    def test_expense_updates_project_server_cost(self, s, tokens):
        h = auth(tokens["admin"])
        # Ensure the cost-hosting type exists (seed)
        cts = s.get(f"{BASE_URL}/api/cost-types", headers=h, timeout=20).json()
        hosting = next((c for c in cts if c["id"] == "cost-hosting"), None)
        if not hosting:
            pytest.skip("Seed cost-hosting missing")
        before = s.get(f"{BASE_URL}/api/projects/project-1/costs", headers=h, timeout=20).json()
        r = s.post(f"{BASE_URL}/api/projects/project-1/expenses", headers=h, json={
            "cost_type_id": "cost-hosting", "amount": 1000,
            "date": date.today().isoformat(), "note": "TEST_exp",
        }, timeout=20)
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        after = s.get(f"{BASE_URL}/api/projects/project-1/costs", headers=h, timeout=20).json()
        assert after["server_cost"] == before["server_cost"] + 1000
        # Delete restores
        r2 = s.delete(f"{BASE_URL}/api/projects/project-1/expenses/{eid}", headers=h, timeout=20)
        assert r2.status_code == 200
        restored = s.get(f"{BASE_URL}/api/projects/project-1/costs", headers=h, timeout=20).json()
        assert restored["server_cost"] == before["server_cost"]

    def test_delete_cost_type_in_use_400(self, s, tokens):
        h = auth(tokens["admin"])
        # Create cost type, attach expense, try delete
        name = f"TEST_ct_{uuid.uuid4().hex[:6]}"
        r = s.post(f"{BASE_URL}/api/cost-types", headers=h,
                   json={"name": name, "group": "Lainnya"}, timeout=20)
        assert r.status_code == 200
        cid = r.json()["id"]
        e = s.post(f"{BASE_URL}/api/projects/project-1/expenses", headers=h, json={
            "cost_type_id": cid, "amount": 100, "date": date.today().isoformat(),
        }, timeout=20)
        assert e.status_code == 200
        eid = e.json()["id"]
        d = s.delete(f"{BASE_URL}/api/cost-types/{cid}", headers=h, timeout=20)
        assert d.status_code == 400
        # Cleanup: remove expense then cost type
        s.delete(f"{BASE_URL}/api/projects/project-1/expenses/{eid}", headers=h, timeout=20)
        s.delete(f"{BASE_URL}/api/cost-types/{cid}", headers=h, timeout=20)


# ---- Auto client account & must_change_password ----
class TestAutoClientAccount:
    def test_full_flow(self, s, tokens):
        h = auth(tokens["admin"])
        suffix = uuid.uuid4().hex[:8]
        email = f"test_{suffix}@example.com"
        r = s.post(f"{BASE_URL}/api/clients", headers=h, json={
            "name": f"TEST_ClientAuto_{suffix}", "contact": "TEST Kontak",
            "email": email, "phone": "", "industry": "", "address": "",
        }, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["account"]["created"] is True
        assert j["account"]["username"] == email.lower()
        assert j["account"]["password"] == "12345678"

        # Login with new client
        fresh = requests.Session()
        lr = login(fresh, email.lower(), "12345678")
        assert lr.status_code == 200
        token = lr.json()["token"]
        me = fresh.get(f"{BASE_URL}/api/auth/me", headers=auth(token), timeout=15).json()
        assert me.get("must_change_password") is True

        # Change password
        newpass = "NewPass9876543"
        pc = fresh.post(f"{BASE_URL}/api/auth/password", headers=auth(token),
                        json={"current_password": "12345678", "new_password": newpass}, timeout=20)
        assert pc.status_code == 200

        # Re-login with new password
        fresh2 = requests.Session()
        lr2 = login(fresh2, email.lower(), newpass)
        assert lr2.status_code == 200
        token2 = lr2.json()["token"]
        me2 = fresh2.get(f"{BASE_URL}/api/auth/me", headers=auth(token2), timeout=15).json()
        assert me2.get("must_change_password") is False

        # Cleanup: deactivate user
        uid_ = me.get("id")
        s.patch(f"{BASE_URL}/api/users/{uid_}", headers=h, json={"active": False}, timeout=20)
        # Delete client (still linked user -> won't allow, first drop user)
        # Try delete client; if 400 due to linked user, skip
        s.delete(f"{BASE_URL}/api/clients/{j['id']}", headers=h, timeout=20)
