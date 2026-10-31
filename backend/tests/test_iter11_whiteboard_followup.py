"""Targeted regression for whiteboard validation/persistence boundaries and Follow Up workflow gate."""

import os
import re
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENV_VALUES = dotenv_values("/app/backend/.env")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or ENV_VALUES.get("SEED_PASSWORD") or "Maiharta!f3d19ae4fc46fca1"
MONGO_URL = os.environ.get("MONGO_URL") or ENV_VALUES.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or ENV_VALUES.get("DB_NAME")


def _solve_captcha(question: str) -> str:
    return str(sum(int(x) for x in re.findall(r"\d+", question)))


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return BASE_URL


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login_token(session: requests.Session, base_url: str, username: str, password: str) -> str:
    cap = session.get(f"{base_url}/api/auth/captcha", timeout=20)
    assert cap.status_code == 200
    c = cap.json()
    res = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "captcha_id": c["id"],
            "captcha_answer": _solve_captcha(c["question"]),
            "remember": False,
        },
        timeout=25,
    )
    assert res.status_code == 200, f"login failed {username}: {res.status_code} {res.text}"
    return res.json()["token"]


@pytest.fixture(scope="session")
def admin_h(session, base_url):
    return {"Authorization": f"Bearer {_login_token(session, base_url, 'admin', SEED_PASSWORD)}"}


@pytest.fixture(scope="session")
def developer_h(session, base_url):
    return {"Authorization": f"Bearer {_login_token(session, base_url, 'developer', SEED_PASSWORD)}"}


# Whiteboard module regression coverage (validation + persistence contract)
@pytest.fixture(scope="module")
def project1_board_snapshot(base_url, admin_h):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30)
    assert board.status_code == 200
    snapshot = board.json()
    yield snapshot
    latest = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30)
    if latest.status_code != 200:
        return
    latest_body = latest.json()
    restore_payload = {
        "name": snapshot.get("name", "Whiteboard project"),
        "nodes": snapshot.get("nodes", []),
        "edges": snapshot.get("edges", []),
        "version": latest_body.get("version", 0),
    }
    restored = requests.patch(
        f"{base_url}/api/projects/project-1/workspace/whiteboard",
        headers=admin_h,
        json=restore_payload,
        timeout=60,
    )
    if restored.status_code == 409:
        latest2 = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30)
        if latest2.status_code == 200:
            restore_payload["version"] = latest2.json().get("version", 0)
            requests.patch(
                f"{base_url}/api/projects/project-1/workspace/whiteboard",
                headers=admin_h,
                json=restore_payload,
                timeout=60,
            )


def _board_payload(version: int, nodes, edges=None):
    return {
        "name": "Whiteboard project",
        "nodes": nodes,
        "edges": edges or [],
        "version": version,
    }


def test_whiteboard_legacy_note_payload_roundtrip(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    payload = _board_payload(
        board["version"],
        [{"id": f"legacy-{uuid.uuid4().hex[:8]}", "position": {"x": 120, "y": 80}, "data": {"label": "LEGACY_NOTE", "color": "#fff5cd", "task_id": ""}}],
    )
    saved = requests.patch(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, json=payload, timeout=40)
    assert saved.status_code == 200, saved.text
    got = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30)
    assert got.status_code == 200
    nodes = got.json().get("nodes", [])
    assert len(nodes) == 1
    assert nodes[0]["type"] == "note"
    assert nodes[0]["data"]["label"] == "LEGACY_NOTE"


def test_whiteboard_reject_invalid_kind(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    payload = _board_payload(
        board["version"],
        [{"id": "bad-kind", "type": "image", "position": {"x": 0, "y": 0}, "data": {}}],
    )
    res = requests.patch(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, json=payload, timeout=30)
    assert res.status_code == 400


def test_whiteboard_reject_invalid_points(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    payload = _board_payload(
        board["version"],
        [{
            "id": "bad-points",
            "type": "drawing",
            "position": {"x": 5, "y": 5},
            "data": {"points": [[1, 2], ["nan", 3]], "color": "#112233", "width": 3},
        }],
    )
    res = requests.patch(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, json=payload, timeout=30)
    assert res.status_code in (400, 422)


def test_whiteboard_reject_duplicate_ids(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    node = {"id": "dup-node", "type": "note", "position": {"x": 10, "y": 10}, "data": {"label": "A", "color": "#fff5cd", "task_id": ""}}
    payload = _board_payload(board["version"], [node, {**node, "position": {"x": 30, "y": 30}}])
    res = requests.patch(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, json=payload, timeout=30)
    assert res.status_code == 400


def test_whiteboard_reject_more_than_300_nodes(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    nodes = [
        {"id": f"n{i}", "type": "note", "position": {"x": i * 5, "y": i * 3}, "data": {"label": "x", "color": "#fff5cd", "task_id": ""}}
        for i in range(301)
    ]
    res = requests.patch(
        f"{base_url}/api/projects/project-1/workspace/whiteboard",
        headers=admin_h,
        json=_board_payload(board["version"], nodes),
        timeout=60,
    )
    assert res.status_code == 422


def test_whiteboard_reject_payload_over_500kb(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    long_label = "L" * 2000
    nodes = [
        {
            "id": f"big{i}",
            "type": "note",
            "position": {"x": i, "y": i},
            "data": {"label": long_label, "color": "#fff5cd", "task_id": ""},
        }
        for i in range(300)
    ]
    res = requests.patch(
        f"{base_url}/api/projects/project-1/workspace/whiteboard",
        headers=admin_h,
        json=_board_payload(board["version"], nodes),
        timeout=90,
    )
    assert res.status_code == 400
    assert "terlalu besar" in res.text.lower()


def test_whiteboard_reject_edges_to_drawing_nodes(base_url, admin_h, project1_board_snapshot):
    board = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=admin_h, timeout=30).json()
    nodes = [
        {"id": "note-a", "type": "note", "position": {"x": 20, "y": 20}, "data": {"label": "A", "color": "#fff5cd", "task_id": ""}},
        {
            "id": "draw-b",
            "type": "drawing",
            "position": {"x": 50, "y": 50},
            "data": {"points": [[0, 0], [8, 6], [12, 14]], "color": "#112233", "width": 4},
        },
    ]
    edges = [{"id": "e1", "source": "note-a", "target": "draw-b"}]
    res = requests.patch(
        f"{base_url}/api/projects/project-1/workspace/whiteboard",
        headers=admin_h,
        json=_board_payload(board["version"], nodes, edges),
        timeout=40,
    )
    assert res.status_code == 400


def test_whiteboard_project_scope_unchanged(base_url, developer_h):
    own = requests.get(f"{base_url}/api/projects/project-1/workspace/whiteboard", headers=developer_h, timeout=30)
    assert own.status_code == 200
    cross = requests.get(f"{base_url}/api/projects/project-7/workspace/whiteboard", headers=developer_h, timeout=30)
    assert cross.status_code == 404


# Project journey module regression coverage (Follow Up sequence enforcement)
def test_follow_up_required_in_status_sequence_and_history(base_url, admin_h):
    if not (MONGO_URL and DB_NAME):
        pytest.skip("Mongo env missing for cleanup")

    suffix = uuid.uuid4().hex[:8]
    client_payload = {
        "name": f"TEST_I11_Client_{suffix}",
        "contact": "I11 Contact",
        "email": f"i11-{suffix}@example.com",
        "phone": "+62 811111111",
        "industry": "Testing",
        "address": "Bali",
    }
    created_client = requests.post(f"{base_url}/api/clients", headers=admin_h, json=client_payload, timeout=25)
    assert created_client.status_code == 200, created_client.text
    cid = created_client.json()["id"]

    pid = None
    try:
        project_payload = {
            "name": f"TEST_I11_Project_{suffix}",
            "client_id": cid,
            "description": "Follow Up sequence regression",
            "platforms": ["Web"],
            "type": "Besar",
            "value": 1000000,
            "start_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=20)).isoformat(),
            "assigned_to": ["user-developer"],
            "internal_notes": "iter11",
        }
        created_project = requests.post(f"{base_url}/api/projects", headers=admin_h, json=project_payload, timeout=30)
        assert created_project.status_code == 200, created_project.text
        pid = created_project.json()["id"]
        assert created_project.json()["status"] == "Project Masuk"

        skip = requests.post(
            f"{base_url}/api/projects/{pid}/status",
            headers=admin_h,
            json={"status": "Dokumen Disiapkan", "note": "skip-check"},
            timeout=25,
        )
        assert skip.status_code == 400

        follow = requests.post(
            f"{base_url}/api/projects/{pid}/status",
            headers=admin_h,
            json={"status": "Follow Up", "note": "to-follow-up"},
            timeout=25,
        )
        assert follow.status_code == 200
        assert follow.json()["status"] == "Follow Up"

        doc = requests.post(
            f"{base_url}/api/projects/{pid}/status",
            headers=admin_h,
            json={"status": "Dokumen Disiapkan", "note": "to-docs"},
            timeout=25,
        )
        assert doc.status_code == 200
        assert doc.json()["status"] == "Dokumen Disiapkan"

        hist = requests.get(f"{base_url}/api/projects/{pid}/history", headers=admin_h, timeout=25)
        assert hist.status_code == 200
        to_status = [row.get("to_status") for row in hist.json() if row.get("to_status")]
        assert "Follow Up" in to_status
        assert "Dokumen Disiapkan" in to_status

        dash = requests.get(f"{base_url}/api/dashboard", headers=admin_h, timeout=25)
        assert dash.status_code == 200
        assert "Follow Up" in dash.json().get("status_counts", {})
    finally:
        mongo = MongoClient(MONGO_URL)
        db = mongo[DB_NAME]
        if pid:
            db.projects.delete_one({"id": pid})
            for col in [
                "project_status_logs",
                "project_features",
                "project_documents",
                "revisions",
                "maintenances",
                "deployments",
                "tickets",
                "tasks",
                "expenses",
                "task_comments",
                "workspace_docs",
                "doc_versions",
                "workspace_boards",
                "workspace_nodes",
                "workspace_fields",
                "workspace_sprints",
                "workspace_goals",
                "workspace_capacities",
                "workspace_automations",
                "saved_views",
                "notifications",
                "activity_logs",
                "audit_logs",
            ]:
                db[col].delete_many({"project_id": pid})
            db.trash.delete_many({"project_id": pid})
        db.clients.delete_one({"id": cid})
        mongo.close()
