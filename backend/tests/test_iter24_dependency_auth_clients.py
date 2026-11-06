"""Regression tests for dependency lock integrity, auth smoke, and client password behavior."""

import os
import re
import uuid
import secrets
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME", "")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or BACKEND_ENV.get("SEED_PASSWORD", "")


def _require_env():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME missing")
    if not SEED_PASSWORD:
        pytest.skip("SEED_PASSWORD missing")


def _solve_math(question: str) -> str:
    match = re.search(r"(\d+)\s*\+\s*(\d+)", question or "")
    if not match:
        raise AssertionError(f"Cannot parse captcha question: {question}")
    return str(int(match.group(1)) + int(match.group(2)))


def _get_captcha(api_client: requests.Session):
    res = api_client.get(f"{BASE_URL}/api/auth/captcha", timeout=20)
    assert res.status_code == 200
    data = res.json()
    assert data.get("provider") in {"math", "recaptcha"}
    assert data.get("provider") == "math", "Preview expected arithmetic captcha for this test scope"
    return data


def _login(api_client: requests.Session, username: str, password: str, remember: bool = False):
    cap = _get_captcha(api_client)
    payload = {
        "username": username,
        "password": password,
        "captcha_id": cap.get("id", ""),
        "captcha_answer": _solve_math(cap.get("question", "")),
        "remember": remember,
    }
    return api_client.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=30)


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def tracker():
    _require_env()
    t = {
        "client_ids": [],
        "user_ids": [],
        "usernames": [],
        "emails": [],
    }
    yield t

    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]

    if t["client_ids"]:
        db.clients.delete_many({"id": {"$in": t["client_ids"]}})
        db.projects.delete_many({"client_id": {"$in": t["client_ids"]}})

    if t["user_ids"]:
        db.users.delete_many({"id": {"$in": t["user_ids"]}})
        db.sessions.delete_many({"user_id": {"$in": t["user_ids"]}})
        db.notifications.delete_many({"user_id": {"$in": t["user_ids"]}})
        db.activity_logs.delete_many({"user_id": {"$in": t["user_ids"]}})
        db.audit_logs.delete_many({"user_id": {"$in": t["user_ids"]}})

    if t["usernames"]:
        db.login_attempts.delete_many({"key": {"$in": [__import__("hashlib").sha256(u.encode()).hexdigest() for u in t["usernames"]]}})

    if t["emails"]:
        db.notifications.delete_many({"message": {"$regex": "TEST_DEPENDENCY_"}})

    mongo.close()


# Modules: dependency lock validation and install-regression guardrails.
def test_requirements_lock_is_public_runtime_only():
    req_path = Path("/app/backend/requirements.txt")
    assert req_path.exists()
    lines = [ln.strip() for ln in req_path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    assert len(lines) == 31
    text = "\n".join(lines).lower()
    blocked = [
        "emergentintegrations",
        "customer-assets.emergentagent.com",
        "litellm",
        "openai",
        "anthropic",
    ]
    for token in blocked:
        assert token not in text


# Modules: runtime direct dependencies and lock-generator source-of-truth.
def test_requirements_in_direct_dependencies_preserved():
    req_in = Path("/app/backend/requirements.in").read_text(encoding="utf-8")
    direct = [ln.strip() for ln in req_in.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert len(direct) == 16
    assert "fastapi==0.110.1" in direct
    assert "uvicorn==0.25.0" in direct
    assert "python-multipart==0.0.32" in direct
    assert "email-validator==2.3.0" in direct


# Modules: auth/cors/session smoke via public preview endpoints.
def test_health_login_cookie_and_dashboard_smoke(api_client: requests.Session):
    _require_env()
    health = api_client.get(f"{BASE_URL}/api/health", timeout=20)
    assert health.status_code == 200
    assert health.json().get("status") == "ok"

    login = _login(api_client, "admin", SEED_PASSWORD)
    assert login.status_code == 200
    data = login.json()
    assert data.get("user", {}).get("username") == "admin"
    assert isinstance(data.get("token"), str) and len(data["token"]) > 20

    set_cookie = login.headers.get("set-cookie", "").lower()
    assert "maiharta_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=none" in set_cookie

    me = api_client.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"}, timeout=20)
    assert me.status_code == 200
    assert me.json().get("username") == "admin"

    dash = api_client.get(f"{BASE_URL}/api/dashboard", headers={"Authorization": f"Bearer {data['token']}"}, timeout=30)
    assert dash.status_code == 200
    assert isinstance(dash.json().get("projects"), list)


# Modules: password hash policy and stored hash format.
def test_admin_password_hash_uses_bcrypt_2b_prefix():
    _require_env()
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    admin = db.users.find_one({"username": "admin"}, {"_id": 0, "password_hash": 1})
    mongo.close()
    assert admin and isinstance(admin.get("password_hash"), str)
    assert admin["password_hash"].startswith("$2b$")


# Modules: client auto-account defaults and first-login password-change enforcement.
def test_create_client_auto_account_default_password_flow(api_client: requests.Session, tracker):
    _require_env()
    admin_login = _login(api_client, "admin", SEED_PASSWORD)
    assert admin_login.status_code == 200
    token = admin_login.json()["token"]

    suffix = uuid.uuid4().hex[:8]
    client_email = f"test_dependency_{suffix}@example.com"
    payload = {
        "name": f"TEST_DEPENDENCY_CLIENT_{suffix}",
        "contact": f"TEST_DEPENDENCY_CONTACT_{suffix}",
        "email": client_email,
        "phone": "081234567890",
        "industry": "QA",
        "address": "TEST_DEPENDENCY_ADDRESS",
    }
    create = api_client.post(
        f"{BASE_URL}/api/clients",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert create.status_code == 200
    created = create.json()
    tracker["client_ids"].append(created["id"])

    account = created.get("account", {})
    assert account.get("created") is True
    assert account.get("username") == client_email.lower()
    assert account.get("password") == "12345678"

    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    created_user = db.users.find_one({"username": client_email.lower()}, {"_id": 0, "id": 1, "must_change_password": 1})
    mongo.close()
    assert created_user and created_user.get("must_change_password") is True
    tracker["user_ids"].append(created_user["id"])
    tracker["usernames"].append(client_email.lower())
    tracker["emails"].append(client_email)

    client_login = _login(api_client, client_email.lower(), "12345678")
    assert client_login.status_code == 200
    client_user = client_login.json().get("user", {})
    assert client_user.get("must_change_password") is True
    assert client_user.get("username") == client_email.lower()


# Modules: existing account must not reset when creating client with pre-existing email.
def test_existing_email_account_not_reset_on_new_client(api_client: requests.Session, tracker):
    _require_env()
    admin_login = _login(api_client, "admin", SEED_PASSWORD)
    assert admin_login.status_code == 200
    token = admin_login.json()["token"]

    suffix = uuid.uuid4().hex[:8]
    shared_email = f"test_dependency_existing_{suffix}@example.com"
    first_payload = {
        "name": f"TEST_DEPENDENCY_EXISTING_EMAIL_1_{suffix}",
        "contact": "TEST_DEPENDENCY_CONTACT",
        "email": shared_email,
        "phone": "",
        "industry": "",
        "address": "",
    }
    create_first = api_client.post(
        f"{BASE_URL}/api/clients",
        json=first_payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert create_first.status_code == 200
    first_body = create_first.json()
    tracker["client_ids"].append(first_body["id"])

    account = first_body.get("account", {})
    assert account.get("created") is True

    # Second client with same email should not recreate/reset existing account.
    second_payload = {
        "name": f"TEST_DEPENDENCY_EXISTING_EMAIL_2_{suffix}",
        "contact": "TEST_DEPENDENCY_CONTACT",
        "email": shared_email,
        "phone": "",
        "industry": "",
        "address": "",
    }
    create_second = api_client.post(
        f"{BASE_URL}/api/clients",
        json=second_payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert create_second.status_code == 200
    second_body = create_second.json()
    tracker["client_ids"].append(second_body["id"])

    account = second_body.get("account", {})
    assert account.get("created") is False
    assert account.get("username") == shared_email

    # Verify admin credentials remain valid after the client creation call.
    relogin = _login(api_client, "admin", SEED_PASSWORD)
    assert relogin.status_code == 200


# Modules: manual /users creation must honor admin-specified password, not default client password.
def test_manual_user_creation_uses_specified_password(api_client: requests.Session, tracker):
    _require_env()
    admin_login = _login(api_client, "admin", SEED_PASSWORD)
    assert admin_login.status_code == 200
    token = admin_login.json()["token"]

    suffix = uuid.uuid4().hex[:8]
    username = f"test_dependency_user_{suffix}"
    password = secrets.token_urlsafe(24)
    payload = {
        "name": f"TEST_DEPENDENCY_USER_{suffix}",
        "username": username,
        "email": f"test_dependency_user_{suffix}@example.com",
        "password": password,
        "role": "Developer",
        "client_id": "",
    }
    created = api_client.post(
        f"{BASE_URL}/api/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body.get("username") == username

    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    row = db.users.find_one({"username": username}, {"_id": 0, "id": 1})
    mongo.close()
    assert row
    tracker["user_ids"].append(row["id"])
    tracker["usernames"].append(username)

    login_ok = _login(api_client, username, password)
    assert login_ok.status_code == 200

    login_default = _login(api_client, username, "12345678")
    assert login_default.status_code == 401


# Modules: CORS credentials behavior (application-level headers, not ingress rewrite).
def test_cors_preflight_has_credentials_header(api_client: requests.Session):
    _require_env()
    origin = BASE_URL
    res = api_client.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert res.status_code in (200, 204)
    assert res.headers.get("access-control-allow-credentials", "").lower() == "true"
    allow_origin = res.headers.get("access-control-allow-origin", "")
    # Preview ingress may rewrite Origin host; ensure app still returns an explicit origin.
    assert isinstance(allow_origin, str) and allow_origin.startswith("https://")
