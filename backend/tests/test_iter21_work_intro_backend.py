"""Iteration 21 backend regression: auth captcha/login + revisions/maintenance CRUD persistence."""

import os
import re
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


# Module scope: public preview API auth and work CRUD paths used by UI flows.
BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
)
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or dotenv_values("/app/backend/.env")["SEED_PASSWORD"]


def _url(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    return f"{BASE_URL.rstrip('/')}{path}"


def _solve(question: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", question or "")]
    return str(sum(nums))


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def admin_headers(api_client):
    captcha = api_client.get(_url("/api/auth/captcha"), timeout=30)
    assert captcha.status_code == 200
    captcha_body = captcha.json()
    assert "id" in captcha_body and "question" in captcha_body

    login = api_client.post(
        _url("/api/auth/login"),
        json={
            "username": "admin",
            "password": SEED_PASSWORD,
            "captcha_id": captcha_body["id"],
            "captcha_answer": _solve(captcha_body["question"]),
        },
        timeout=30,
    )
    assert login.status_code == 200
    token = login.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    return {"Authorization": f"Bearer {token}"}


def _create_work(api_client, headers, project_id, kind, title, due_days):
    payload = {
        "title": title,
        "description": "TEST_ITER21 generated record",
        "kind": "Adaptive" if kind == "maintenances" else "In-scope",
        "assigned_to": "user-developer",
        "entry_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=due_days)).isoformat(),
        "priority": "Sedang",
        "estimate": 0,
        "subtasks": [],
    }
    created = api_client.post(
        _url(f"/api/projects/{project_id}/work/{kind}"),
        headers=headers,
        json=payload,
        timeout=30,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["title"] == title
    assert body["project_id"] == project_id
    assert body["status"] in ["Terbuka", "Belum dikerjakan"]
    return body


def _find_by_id(rows, work_id):
    return next((r for r in rows if r.get("id") == work_id), None)


def test_auth_captcha_login_and_me(api_client, admin_headers):
    me = api_client.get(_url("/api/auth/me"), headers=admin_headers, timeout=30)
    assert me.status_code == 200
    user = me.json()
    assert user["username"] == "admin"
    assert user["role"] == "Admin"


def test_login_allows_empty_recaptcha_token_field(api_client):
    """UI sends recaptcha_token="" on arithmetic captcha mode; login should still succeed."""
    captcha = api_client.get(_url("/api/auth/captcha"), timeout=30)
    assert captcha.status_code == 200
    captcha_body = captcha.json()

    login = api_client.post(
        _url("/api/auth/login"),
        json={
            "username": "admin",
            "password": SEED_PASSWORD,
            "captcha_id": captcha_body["id"],
            "captcha_answer": _solve(captcha_body["question"]),
            "recaptcha_token": "",
        },
        timeout=30,
    )
    assert login.status_code == 200


def test_revisions_create_update_refresh_archive(api_client, admin_headers):
    title = f"TEST_ITER21_REV_{date.today().isoformat()}"
    created = _create_work(api_client, admin_headers, "project-8", "revisions", title, 7)

    created_id = created["id"]
    listed = api_client.get(_url("/api/work/revisions"), headers=admin_headers, timeout=30)
    assert listed.status_code == 200
    rows = listed.json()
    inserted = _find_by_id(rows, created_id)
    assert inserted is not None
    assert inserted["title"] == title

    patch_payload = {
        "status": "Dikerjakan",
        "started_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=9)).isoformat(),
        "priority": "Tinggi",
        "estimate": 250000,
    }
    patched = api_client.patch(
        _url(f"/api/projects/project-8/work/revisions/{created_id}"),
        headers=admin_headers,
        json=patch_payload,
        timeout=30,
    )
    assert patched.status_code == 200

    refreshed = api_client.get(_url("/api/work/revisions"), headers=admin_headers, timeout=30)
    assert refreshed.status_code == 200
    updated = _find_by_id(refreshed.json(), created_id)
    assert updated is not None
    assert updated["status"] == "Dikerjakan"
    assert updated["priority"] == "Tinggi"
    assert updated["estimate"] == 250000

    archived = api_client.delete(
        _url(f"/api/projects/project-8/work/revisions/{created_id}"),
        headers=admin_headers,
        timeout=30,
    )
    assert archived.status_code == 200

    after_delete = api_client.get(_url("/api/work/revisions"), headers=admin_headers, timeout=30)
    assert after_delete.status_code == 200
    assert _find_by_id(after_delete.json(), created_id) is None


def test_maintenance_create_update_refresh_archive(api_client, admin_headers):
    title = f"TEST_ITER21_MTN_{date.today().isoformat()}"
    created = _create_work(api_client, admin_headers, "project-4", "maintenances", title, 6)

    created_id = created["id"]
    listed = api_client.get(_url("/api/work/maintenances"), headers=admin_headers, timeout=30)
    assert listed.status_code == 200
    rows = listed.json()
    inserted = _find_by_id(rows, created_id)
    assert inserted is not None
    assert inserted["title"] == title

    patch_payload = {
        "status": "Testing",
        "started_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=10)).isoformat(),
        "priority": "Mendesak",
        "estimate": 300000,
    }
    patched = api_client.patch(
        _url(f"/api/projects/project-4/work/maintenances/{created_id}"),
        headers=admin_headers,
        json=patch_payload,
        timeout=30,
    )
    assert patched.status_code == 200

    refreshed = api_client.get(_url("/api/work/maintenances"), headers=admin_headers, timeout=30)
    assert refreshed.status_code == 200
    updated = _find_by_id(refreshed.json(), created_id)
    assert updated is not None
    assert updated["status"] == "Testing"
    assert updated["priority"] == "Mendesak"
    assert updated["estimate"] == 300000

    archived = api_client.delete(
        _url(f"/api/projects/project-4/work/maintenances/{created_id}"),
        headers=admin_headers,
        timeout=30,
    )
    assert archived.status_code == 200

    after_delete = api_client.get(_url("/api/work/maintenances"), headers=admin_headers, timeout=30)
    assert after_delete.status_code == 200
    assert _find_by_id(after_delete.json(), created_id) is None


def test_cleanup_iter21_temporary_records(api_client, admin_headers):
    """Best-effort cleanup for temporary UI/API records created during iteration 21 testing."""
    prefixes = ("TEST_ITER21_", "TEST_ITER21")
    for kind in ["revisions", "maintenances"]:
        listed = api_client.get(_url(f"/api/work/{kind}"), headers=admin_headers, timeout=30)
        assert listed.status_code == 200
        rows = listed.json()
        leftovers = [r for r in rows if (r.get("title") or "").startswith(prefixes)]
        for row in leftovers:
            api_client.delete(
                _url(f"/api/projects/{row['project_id']}/work/{kind}/{row['id']}"),
                headers=admin_headers,
                timeout=30,
            )

        verify = api_client.get(_url(f"/api/work/{kind}"), headers=admin_headers, timeout=30)
        assert verify.status_code == 200
        remain = [r for r in verify.json() if (r.get("title") or "").startswith(prefixes)]
        assert len(remain) == 0
