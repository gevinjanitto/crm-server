"""Iteration 9 targeted regression: docs title update persistence."""

import os
import re
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


ENV_FRONTEND = dotenv_values(Path(__file__).parents[2] / "frontend" / ".env")
ENV_BACKEND = dotenv_values(Path(__file__).parents[1] / ".env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or ENV_FRONTEND.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"
PASSWORD = ENV_BACKEND.get("SEED_PASSWORD", "")
PID = "project-1"


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question)))


def _login(username: str):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    cap = s.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    cj = cap.json()
    r = s.post(
        f"{API}/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
            "captcha_id": cj["id"],
            "captcha_answer": _solve(cj["question"]),
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_docs_title_update_persists_after_patch_and_list_reload():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    if not PASSWORD:
        pytest.skip("SEED_PASSWORD missing")

    h = _login("adminproject")

    created = requests.post(
        f"{API}/projects/{PID}/workspace/docs",
        headers=h,
        json={"title": f"TEST_I9_DOC_{uuid.uuid4().hex[:6]}", "content": "<p>a</p>", "visibility": "Internal"},
        timeout=20,
    )
    assert created.status_code == 200, created.text
    doc = created.json()

    updated_title = f"TEST_I9_DOC_UPDATED_{uuid.uuid4().hex[:5]}"
    patched = requests.patch(
        f"{API}/projects/{PID}/workspace/docs/{doc['id']}",
        headers=h,
        json={
            "title": updated_title,
            "content": "<p>b</p>",
            "visibility": "Internal",
            "version": doc["version"],
        },
        timeout=20,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == updated_title

    listed = requests.get(f"{API}/projects/{PID}/workspace/docs", headers=h, timeout=20)
    assert listed.status_code == 200
    row = next(x for x in listed.json() if x["id"] == doc["id"])
    assert row["title"] == updated_title

    requests.delete(f"{API}/projects/{PID}/workspace/docs/{doc['id']}", headers=h, timeout=20)
