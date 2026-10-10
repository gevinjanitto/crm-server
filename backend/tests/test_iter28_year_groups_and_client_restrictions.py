"""Iteration 28: yearly project grouping fixtures + client restrictions regression."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    MongoClient = None


# Module: environment + auth helpers
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or BACKEND_ENV.get("SEED_PASSWORD")
MONGO_URL = os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME")

ARTIFACT_DIR = "/app/test_reports/artifacts_iter3"
FIXTURE_FILE = f"{ARTIFACT_DIR}/iter28_fixture_ids.json"
PREFIX = f"TEST_YEAR_ACCESS_{uuid.uuid4().hex[:6]}"


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question or "")))


def _login(username: str, password: str | None = None) -> tuple[requests.Session, dict]:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    cap = session.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    cap_data = cap.json()
    auth = session.post(
        f"{API}/auth/login",
        json={
            "username": username,
            "password": password or SEED_PASSWORD,
            "captcha_id": cap_data.get("id", ""),
            "captcha_answer": _solve(cap_data.get("question", "")),
            "remember": False,
        },
        timeout=30,
    )
    assert auth.status_code == 200, f"login failed {username}: {auth.status_code} {auth.text}"
    token = auth.json()["token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, auth.json()["user"]


def _mongo_db():
    if not MongoClient or not MONGO_URL or not DB_NAME:
        return None
    return MongoClient(MONGO_URL)[DB_NAME]


def _mk_project_payload(name: str, client_id: str, start: date, due: date):
    return {
        "name": name,
        "client_id": client_id,
        "description": "iteration 28 fixture",
        "platforms": ["Web"],
        "type": "Kecil",
        "value": 0,
        "start_date": start.isoformat(),
        "due_date": due.isoformat(),
        "assigned_to": [],
        "internal_notes": "",
    }


@pytest.fixture(scope="module")
def actors():
    return {
        "admin": _login("admin"),
        "adminproject": _login("adminproject"),
        "developer": _login("developer"),
        "accounting": _login("accounting"),
        "client": _login("client"),
    }


@pytest.fixture(scope="module")
def fixture_data(actors):
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    admin_session, _ = actors["admin"]

    own_p = admin_session.get(f"{API}/projects/project-1", timeout=20)
    foreign_p = admin_session.get(f"{API}/projects/project-2", timeout=20)
    assert own_p.status_code == 200
    assert foreign_p.status_code == 200
    client_1 = own_p.json()["client_id"]
    client_2 = foreign_p.json()["client_id"]

    created_ids: list[str] = []
    pagination_year = 2025

    # 9+ projects in one year for pagination checks
    for i in range(10):
        long_name = (
            (PREFIX + "_" + ("P" * 140))[:150]
            if i == 0
            else f"{PREFIX}_Y{pagination_year}_{i:02d}"
        )
        payload = _mk_project_payload(
            long_name,
            client_1,
            date(pagination_year, 1, 2) + timedelta(days=i),
            date(pagination_year, 12, 1),
        )
        created = admin_session.post(f"{API}/projects", json=payload, timeout=35)
        assert created.status_code == 200, created.text
        created_ids.append(created.json()["id"])

    # 2024 and 2026 groups
    for year in [2024, 2026]:
        payload = _mk_project_payload(
            f"{PREFIX}_Y{year}",
            client_1,
            date(year, 3, 1),
            date(year, 10, 1),
        )
        created = admin_session.post(f"{API}/projects", json=payload, timeout=35)
        assert created.status_code == 200, created.text
        created_ids.append(created.json()["id"])

    # foreign-client project for ticket ownership rejection
    foreign_payload = _mk_project_payload(
        f"{PREFIX}_FOREIGN_CLIENT",
        client_2,
        date(2025, 4, 2),
        date(2025, 9, 2),
    )
    foreign_created = admin_session.post(f"{API}/projects", json=foreign_payload, timeout=35)
    assert foreign_created.status_code == 200, foreign_created.text
    foreign_id = foreign_created.json()["id"]
    created_ids.append(foreign_id)

    # closed project must be excluded from /ticket-projects
    closed_payload = _mk_project_payload(
        f"{PREFIX}_CLOSED_TICKETS",
        client_1,
        date(2025, 5, 4),
        date(2025, 11, 4),
    )
    closed_created = admin_session.post(f"{API}/projects", json=closed_payload, timeout=35)
    assert closed_created.status_code == 200, closed_created.text
    closed_id = closed_created.json()["id"]
    created_ids.append(closed_id)

    # Mark one fixture as undated via local DB per requirement
    db = _mongo_db()
    if db is not None:
        db.projects.update_one({"id": created_ids[0]}, {"$set": {"start_date": None}})
        db.projects.update_one({"id": closed_id}, {"$set": {"tickets_closed": True}})

    fixture = {
        "prefix": PREFIX,
        "created_project_ids": created_ids,
        "foreign_fixture_project_id": foreign_id,
        "closed_fixture_project_id": closed_id,
        "client_1": client_1,
        "client_2": client_2,
    }
    with open(FIXTURE_FILE, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)
    return fixture


# Module: /projects and report role matrix
def test_projects_and_reports_role_matrix(actors):
    anon = requests.Session()
    anon_projects = anon.get(f"{API}/projects", timeout=20)
    anon_csv = anon.get(f"{API}/reports/projects.csv", timeout=20)
    anon_xlsx = anon.get(f"{API}/reports/projects.xlsx", timeout=20)
    assert anon_projects.status_code == 401
    assert anon_csv.status_code == 401
    assert anon_xlsx.status_code == 401

    client_session, _ = actors["client"]
    client_projects = client_session.get(f"{API}/projects", timeout=20)
    client_csv = client_session.get(f"{API}/reports/projects.csv", timeout=20)
    client_xlsx = client_session.get(f"{API}/reports/projects.xlsx", timeout=20)
    assert client_projects.status_code == 403
    assert client_csv.status_code == 403
    assert client_xlsx.status_code == 403

    for key in ["admin", "adminproject", "accounting", "developer"]:
        session, _ = actors[key]
        assert session.get(f"{API}/projects", timeout=20).status_code == 200
        assert session.get(f"{API}/reports/projects.csv", timeout=20).status_code == 200
        assert session.get(f"{API}/reports/projects.xlsx", timeout=20).status_code == 200


def test_developer_projects_are_scoped_to_assigned(actors):
    dev_session, dev_user = actors["developer"]
    result = dev_session.get(f"{API}/projects", timeout=20)
    assert result.status_code == 200
    rows = result.json()
    assert rows, "Developer should receive assigned projects"
    assert all(dev_user["id"] in (p.get("assigned_to") or []) for p in rows)


def test_client_project_detail_access_own_and_foreign(actors):
    client_session, _ = actors["client"]
    own = client_session.get(f"{API}/projects/project-1", timeout=20)
    foreign = client_session.get(f"{API}/projects/project-2", timeout=20)
    assert own.status_code == 200
    assert foreign.status_code == 404


def test_dashboard_scoped_for_client(actors):
    client_session, _ = actors["client"]
    dash = client_session.get(f"{API}/dashboard", timeout=25)
    assert dash.status_code == 200
    data = dash.json()
    assert isinstance(data.get("projects"), list)
    assert all(p.get("client_id") == "client-1" for p in data["projects"])


# Module: /ticket-projects and /tickets create permission matrix
def test_ticket_projects_requires_client_role(actors):
    anon = requests.Session().get(f"{API}/ticket-projects", timeout=20)
    assert anon.status_code == 401

    for key in ["admin", "adminproject", "developer", "accounting"]:
        session, _ = actors[key]
        res = session.get(f"{API}/ticket-projects", timeout=20)
        assert res.status_code == 403


def test_ticket_projects_returns_minimal_open_owned_data(actors, fixture_data):
    client_session, _ = actors["client"]
    res = client_session.get(f"{API}/ticket-projects", timeout=25)
    assert res.status_code == 200
    rows = res.json()
    assert rows
    assert all(set(r.keys()) == {"id", "code", "name"} for r in rows)

    ids = {r["id"] for r in rows}
    assert fixture_data["closed_fixture_project_id"] not in ids
    assert fixture_data["foreign_fixture_project_id"] not in ids

    # validate returned fixtures are owned + open using detail endpoint
    sample = [r for r in rows if r["id"] in fixture_data["created_project_ids"]][:2]
    for item in sample:
        detail = client_session.get(f"{API}/projects/{item['id']}", timeout=20)
        assert detail.status_code == 200
        project = detail.json()
        assert project["client_id"] == fixture_data["client_1"]
        assert project.get("tickets_closed") is not True


def test_client_can_create_ticket_on_eligible_own_project(actors, fixture_data):
    client_session, _ = actors["client"]
    own_id = next(
        pid
        for pid in fixture_data["created_project_ids"]
        if pid not in {fixture_data["closed_fixture_project_id"], fixture_data["foreign_fixture_project_id"]}
    )
    payload = {
        "project_id": own_id,
        "title": f"{fixture_data['prefix']}_ticket_ok",
        "description": "Valid ticket created by client for owned eligible project",
        "description_html": "<p>Valid ticket created by client for owned eligible project</p>",
        "category": "Bug / Problem",
        "priority": "Sedang",
        "cc_emails": [],
    }
    created = client_session.post(f"{API}/tickets", json=payload, timeout=30)
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["project_id"] == own_id
    assert row["title"] == payload["title"]


def test_client_cannot_create_ticket_for_foreign_project(actors, fixture_data):
    client_session, _ = actors["client"]
    payload = {
        "project_id": fixture_data["foreign_fixture_project_id"],
        "title": f"{fixture_data['prefix']}_ticket_forbidden",
        "description": "Client should not create ticket for foreign project",
        "description_html": "<p>Client should not create ticket for foreign project</p>",
        "category": "Bug / Problem",
        "priority": "Sedang",
        "cc_emails": [],
    }
    denied = client_session.post(f"{API}/tickets", json=payload, timeout=30)
    assert denied.status_code in [403, 404]


def test_internal_roles_forbidden_to_create_ticket(actors, fixture_data):
    own_id = next(
        pid
        for pid in fixture_data["created_project_ids"]
        if pid not in {fixture_data["closed_fixture_project_id"], fixture_data["foreign_fixture_project_id"]}
    )
    payload = {
        "project_id": own_id,
        "title": f"{fixture_data['prefix']}_ticket_internal_forbidden",
        "description": "Internal roles cannot create client ticket",
        "description_html": "<p>Internal roles cannot create client ticket</p>",
        "category": "Bug / Problem",
        "priority": "Sedang",
        "cc_emails": [],
    }
    for key in ["admin", "adminproject", "developer", "accounting"]:
        session, _ = actors[key]
        denied = session.post(f"{API}/tickets", json=payload, timeout=30)
        assert denied.status_code == 403, f"{key} expected 403 got {denied.status_code}"
