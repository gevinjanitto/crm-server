"""Focused tests for the Vercel/Railway deployment changes: health, CORS, Bearer auth,
Cloudinary-not-configured 503 upload behavior, and /api/auth/me lifecycle."""

import os
import re
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENV_VALUES = dotenv_values("/app/backend/.env")
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or ENV_VALUES.get("SEED_PASSWORD")


@pytest.fixture(scope="module")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return BASE_URL


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _solve(question):
    return str(sum(int(n) for n in re.findall(r"\d+", question)))


def _login(api, base_url, username, password):
    c = api.get(f"{base_url}/api/auth/captcha", timeout=15).json()
    return api.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "captcha_id": c["id"],
            "captcha_answer": _solve(c["question"]),
            "remember": False,
        },
        timeout=25,
    )


# Basic health endpoints
def test_health_endpoint(api, base_url):
    r = api.get(f"{base_url}/api/health", timeout=15)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"} or r.json().get("status") == "ok"


def test_root_api_endpoint(api, base_url):
    r = api.get(f"{base_url}/api/", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


# CORS preflight echoes origin and credentials
def test_cors_preflight_echoes_origin(base_url):
    origin = "https://example.com"
    r = requests.options(
        f"{base_url}/api/auth/captcha",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
        timeout=15,
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials", "").lower() == "true"


# Auth me lifecycle with Bearer token
@pytest.fixture(scope="module")
def admin_token(api, base_url):
    if not SEED_PASSWORD:
        pytest.skip("no seed password")
    r = _login(api, base_url, "admin", SEED_PASSWORD)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_auth_me_with_bearer(api, base_url, admin_token):
    r = api.get(
        f"{base_url}/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("username") == "admin"


def test_auth_me_without_token_401(api, base_url):
    # use a fresh session to avoid cookie
    s = requests.Session()
    r = s.get(f"{base_url}/api/auth/me", timeout=15)
    assert r.status_code == 401


def test_logout_invalidates_token(base_url):
    if not SEED_PASSWORD:
        pytest.skip("no seed password")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = _login(s, base_url, "admin", SEED_PASSWORD)
    assert r.status_code == 200
    token = r.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    me1 = s.get(f"{base_url}/api/auth/me", headers=auth, timeout=15)
    assert me1.status_code == 200
    out = s.post(f"{base_url}/api/auth/logout", headers=auth, timeout=15)
    assert out.status_code in (200, 204)
    # Fresh session with only bearer header (no cookie) to prove token revoked
    fresh = requests.Session()
    me2 = fresh.get(f"{base_url}/api/auth/me", headers=auth, timeout=15)
    assert me2.status_code == 401


# Cloudinary NOT configured -> upload 503 with Indonesian Cloudinary message
def test_document_upload_returns_503_when_cloudinary_missing(base_url, admin_token):
    files = {"file": ("TEST_tiny.txt", b"TEST_hello", "text/plain")}
    data = {"kind": "Kontrak", "visibility": "Internal"}
    r = requests.post(
        f"{base_url}/api/projects/project-1/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        files=files,
        data=data,
        timeout=45,
    )
    assert r.status_code == 503, f"expected 503 got {r.status_code}: {r.text[:300]}"
    body = r.json()
    detail = str(body.get("detail", "")).lower()
    assert "cloudinary" in detail, f"detail did not mention cloudinary: {body}"


# Role login smoke test — all 5 seed users can login and get /api/auth/me
@pytest.mark.parametrize("username", ["admin", "adminproject", "developer", "accounting", "client"])
def test_all_roles_login_and_me(api, base_url, username):
    if not SEED_PASSWORD:
        pytest.skip("no seed password")
    r = _login(api, base_url, username, SEED_PASSWORD)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    me = api.get(
        f"{base_url}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert me.status_code == 200
    assert me.json().get("username") == username
