"""Iteration 22 backend regression: auth activity + 15-minute idle expiry behavior."""

import os
import re
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Module scope: real preview auth session lifecycle and local-db timestamp checks.
BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
)
MONGO_URL = os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or dotenv_values("/app/backend/.env").get("SEED_PASSWORD")


def _url(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    return f"{BASE_URL.rstrip('/')}{path}"


def _solve(question: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", question or "")]
    return str(sum(nums))


def _to_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def mongo_sessions():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL or DB_NAME missing")
    client = MongoClient(MONGO_URL)
    coll = client[DB_NAME]["sessions"]
    yield coll
    client.close()


@pytest.fixture
def auth_session(api_client):
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
            "remember": True,
        },
        timeout=30,
    )
    assert login.status_code == 200
    data = login.json()
    token = data.get("token")
    assert isinstance(token, str) and len(token) > 20
    payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256"])
    session_id = payload["jti"]
    headers = {"Authorization": f"Bearer {token}"}

    yield {"token": token, "headers": headers, "session_id": session_id, "user": data.get("user", {})}

    api_client.post(_url("/api/auth/logout"), headers=headers, timeout=30)


def _read_session(coll, session_id: str):
    return coll.find_one({"id": session_id}, {"_id": 0})


def _set_session_activity(coll, session_id: str, activity_time: datetime):
    coll.update_one({"id": session_id}, {"$set": {"last_activity_at": activity_time}})


def test_auth_activity_bounds_and_success(api_client, auth_session):
    bad_low = api_client.post(_url("/api/auth/activity"), headers=auth_session["headers"], json={"idle_for_ms": -1}, timeout=30)
    assert bad_low.status_code == 422

    bad_high = api_client.post(_url("/api/auth/activity"), headers=auth_session["headers"], json={"idle_for_ms": 900000}, timeout=30)
    assert bad_high.status_code == 422

    ok = api_client.post(_url("/api/auth/activity"), headers=auth_session["headers"], json={"idle_for_ms": 0}, timeout=30)
    assert ok.status_code == 200
    assert ok.json().get("idle_timeout_seconds") == 900


def test_auth_me_does_not_extend_session_activity(api_client, auth_session, mongo_sessions):
    session_id = auth_session["session_id"]
    base = datetime.now(timezone.utc) - timedelta(seconds=120)
    _set_session_activity(mongo_sessions, session_id, base)

    me = api_client.get(_url("/api/auth/me"), headers=auth_session["headers"], timeout=30)
    assert me.status_code == 200

    doc = _read_session(mongo_sessions, session_id)
    assert doc is not None
    last_activity = _to_utc(doc.get("last_activity_at"))
    assert abs((last_activity - base).total_seconds()) < 2


def test_auth_activity_updates_only_on_activity_endpoint(api_client, auth_session, mongo_sessions):
    session_id = auth_session["session_id"]
    before = datetime.now(timezone.utc) - timedelta(seconds=180)
    _set_session_activity(mongo_sessions, session_id, before)

    pulse = api_client.post(
        _url("/api/auth/activity"),
        headers=auth_session["headers"],
        json={"idle_for_ms": 5000},
        timeout=30,
    )
    assert pulse.status_code == 200

    doc = _read_session(mongo_sessions, session_id)
    assert doc is not None
    after = _to_utc(doc.get("last_activity_at"))
    assert after > before
    expected = datetime.now(timezone.utc) - timedelta(milliseconds=5000)
    assert abs((after - expected).total_seconds()) < 4


def test_delayed_pulse_does_not_rewind_activity_age(api_client, auth_session, mongo_sessions):
    session_id = auth_session["session_id"]
    fresh = datetime.now(timezone.utc) - timedelta(seconds=20)
    _set_session_activity(mongo_sessions, session_id, fresh)

    delayed = api_client.post(
        _url("/api/auth/activity"),
        headers=auth_session["headers"],
        json={"idle_for_ms": 120000},
        timeout=30,
    )
    assert delayed.status_code == 200

    doc = _read_session(mongo_sessions, session_id)
    assert doc is not None
    after = _to_utc(doc.get("last_activity_at"))
    assert abs((after - fresh).total_seconds()) < 2


def test_idle_threshold_boundary_and_expiry_rejection(api_client, auth_session, mongo_sessions):
    session_id = auth_session["session_id"]

    alive_time = datetime.now(timezone.utc) - timedelta(seconds=899)
    _set_session_activity(mongo_sessions, session_id, alive_time)
    ok_me = api_client.get(_url("/api/auth/me"), headers=auth_session["headers"], timeout=30)
    assert ok_me.status_code == 200

    expired_time = datetime.now(timezone.utc) - timedelta(seconds=901)
    _set_session_activity(mongo_sessions, session_id, expired_time)

    expired_me = api_client.get(_url("/api/auth/me"), headers=auth_session["headers"], timeout=30)
    assert expired_me.status_code == 401
    assert "15 menit" in (expired_me.json().get("detail") or "")

    deleted = _read_session(mongo_sessions, session_id)
    assert deleted is None

    expired_activity = api_client.post(
        _url("/api/auth/activity"),
        headers=auth_session["headers"],
        json={"idle_for_ms": 1000},
        timeout=30,
    )
    assert expired_activity.status_code == 401


def test_logout_revokes_token_and_session_deleted(api_client, auth_session, mongo_sessions):
    session_id = auth_session["session_id"]
    me_before = api_client.get(_url("/api/auth/me"), headers=auth_session["headers"], timeout=30)
    assert me_before.status_code == 200

    logout = api_client.post(_url("/api/auth/logout"), headers=auth_session["headers"], timeout=30)
    assert logout.status_code == 200

    me_after = api_client.get(_url("/api/auth/me"), headers=auth_session["headers"], timeout=30)
    assert me_after.status_code == 401

    doc = _read_session(mongo_sessions, session_id)
    assert doc is None
