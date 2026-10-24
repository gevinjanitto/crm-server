"""Iteration 30 regression: notification contracts, ClickUp removal, guide assets, auth/cors, kanban sync smoke."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest
import requests
from dotenv import dotenv_values

# Module: environment + auth helpers
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or BACKEND_ENV.get("SEED_PASSWORD")


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r"\d+", question or "")))


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(username: str, password: str | None = None, remember: bool = False) -> tuple[requests.Session, requests.Response]:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    session = _new_session()
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
            "remember": remember,
        },
        timeout=30,
    )
    assert auth.status_code == 200, f"login failed for {username}: {auth.status_code} {auth.text}"
    token = auth.json()["token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, auth


@pytest.fixture(scope="module")
def actors():
    admin = _login("admin")
    developer = _login("developer")
    client = _login("client")
    return {"admin": admin, "developer": developer, "client": client}


@pytest.fixture(scope="module", autouse=True)
def restore_developer_notification_preferences(actors):
    """Module cleanup: restore developer notification preferences and phone after tests."""
    developer_session, _ = actors["developer"]
    before = developer_session.get(f"{API}/account/notifications", timeout=20)
    assert before.status_code == 200
    baseline = before.json()
    yield
    developer_session.patch(
        f"{API}/account/notifications",
        json={
            "in_app": baseline.get("in_app", True),
            "email": baseline.get("email", True),
            "whatsapp": baseline.get("whatsapp", False),
            "whatsapp_number": baseline.get("whatsapp_number", ""),
        },
        timeout=25,
    )


# Module: auth + cookie + cors
def test_login_sets_secure_httponly_cookie_and_returns_token_structure():
    session = _new_session()
    cap = session.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    data = cap.json()
    login = session.post(
        f"{API}/auth/login",
        json={
            "username": "admin",
            "password": SEED_PASSWORD,
            "captcha_id": data.get("id", ""),
            "captcha_answer": _solve(data.get("question", "")),
            "remember": False,
        },
        timeout=30,
    )
    assert login.status_code == 200
    payload = login.json()
    assert isinstance(payload.get("token"), str) and payload["token"]
    assert payload.get("user", {}).get("username") == "admin"
    set_cookie = login.headers.get("set-cookie", "")
    assert "maiharta_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=None" in set_cookie


def test_cors_preflight_allows_credentials_and_non_wildcard_origin_for_explicit_origin():
    origin = os.environ.get("APP_URL", "https://crm.example.test")
    preflight = requests.options(
        f"{API}/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert preflight.status_code in [200, 204]
    assert preflight.headers.get("access-control-allow-credentials") == "true"
    allow_origin = preflight.headers.get("access-control-allow-origin")
    assert isinstance(allow_origin, str) and allow_origin.startswith("https://")
    assert allow_origin != "*"


def test_login_lockout_on_16th_failed_attempt_for_same_username_key():
    username = f"nosuch-{uuid.uuid4().hex[:8]}"
    session = _new_session()
    statuses = []
    for _ in range(16):
        cap = session.get(f"{API}/auth/captcha", timeout=20)
        assert cap.status_code == 200
        cap_data = cap.json()
        bad = session.post(
            f"{API}/auth/login",
            json={
                "username": username,
                "password": "wrong-password",
                "captcha_id": cap_data.get("id", ""),
                "captcha_answer": _solve(cap_data.get("question", "")),
            },
            timeout=25,
        )
        statuses.append(bad.status_code)
    assert statuses[-1] == 429


# Module: ClickUp retirement contract
def test_clickup_import_endpoints_are_retired_and_return_404(actors):
    admin_session, _ = actors["admin"]

    analyze = admin_session.post(f"{API}/imports/clickup/analyze", timeout=20)
    assert analyze.status_code == 404

    fake_sid = "retired-session-id"
    preview = admin_session.post(f"{API}/imports/clickup/{fake_sid}/preview", json={}, timeout=20)
    assert preview.status_code == 404

    commit = admin_session.post(f"{API}/imports/clickup/{fake_sid}/commit", json={}, timeout=20)
    assert commit.status_code == 404


# Module: account notification readiness + disabled-channel behavior
def test_account_notifications_get_exposes_readiness_without_secrets(actors):
    developer_session, _ = actors["developer"]
    response = developer_session.get(f"{API}/account/notifications", timeout=20)
    assert response.status_code == 200
    body = response.json()

    assert body.get("email_provider") == "Gmail via n8n"
    assert body.get("whatsapp_provider") == "n8n + WAHA"
    assert "email_configured" in body and isinstance(body["email_configured"], bool)
    assert "whatsapp_configured" in body and isinstance(body["whatsapp_configured"], bool)

    dumped = json.dumps(body)
    for secret_marker in ["RESEND_API_KEY", "N8N_WAHA_WEBHOOK_SECRET", "Bearer ", "sk_live", "re_"]:
        assert secret_marker not in dumped


def test_notification_preferences_phone_normalization_persists(actors):
    developer_session, _ = actors["developer"]
    save = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": True, "whatsapp_number": "0812 3456 7890"},
        timeout=25,
    )
    assert save.status_code == 200, save.text
    saved = save.json()
    assert saved["whatsapp_number"] == "+6281234567890"

    fetched = developer_session.get(f"{API}/account/notifications", timeout=20)
    assert fetched.status_code == 200
    assert fetched.json().get("whatsapp_number") == "+6281234567890"


def test_notification_test_disabled_channels_record_skipped_and_enforce_rate_limit(actors):
    developer_session, _ = actors["developer"]
    disable_channels = developer_session.patch(
        f"{API}/account/notifications",
        json={"in_app": True, "email": True, "whatsapp": True, "whatsapp_number": "+6281234567890"},
        timeout=25,
    )
    assert disable_channels.status_code == 200

    first = developer_session.post(f"{API}/account/notifications/test", timeout=30)
    assert first.status_code in [200, 429], first.text
    if first.status_code == 200:
        msg = first.json().get("message", "")
        assert "tidak dikirim" in msg.lower()

    deliveries = developer_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    assert deliveries.status_code == 200
    rows = deliveries.json()
    assert rows, "expected recent delivery rows"
    latest_two = rows[:2]
    assert all(r.get("status") == "skipped" for r in latest_two)
    assert all(r.get("reason") for r in latest_two)

    second = developer_session.post(f"{API}/account/notifications/test", timeout=25)
    assert second.status_code == 429


def test_notification_test_isolation_between_users(actors):
    developer_session, _ = actors["developer"]
    client_session, _ = actors["client"]

    dev_before = developer_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    client_before = client_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    assert dev_before.status_code == 200 and client_before.status_code == 200

    _ = client_session.post(f"{API}/account/notifications/test", timeout=30)

    dev_after = developer_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    client_after = client_session.get(f"{API}/account/notifications/deliveries", timeout=25)
    assert dev_after.status_code == 200 and client_after.status_code == 200

    assert len(dev_after.json()) == len(dev_before.json())
    assert len(client_after.json()) >= len(client_before.json())


# Module: offline provider contracts (no external sending)
@pytest.mark.anyio
async def test_n8n_email_contract_payload_and_secret_header(monkeypatch):
    import sys

    sys.path.insert(0, "/app/backend")
    import mailer  # noqa: WPS433

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["header"] = request.headers.get("X-CRM-Webhook-Secret")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(202, json={"ok": True, "status": "accepted", "notification_id": "notif-abc", "message_id": "gmail-1"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class _ClientFactory:
        def __call__(self, *args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("N8N_EMAIL_WEBHOOK_URL", "https://n8n.example.org/webhook/crm-email")
    monkeypatch.setenv("N8N_WAHA_WEBHOOK_SECRET", "y" * 32)
    monkeypatch.setenv("APP_URL", "https://crm.example.org")
    monkeypatch.setattr(mailer.httpx, "AsyncClient", _ClientFactory())

    provider_id = await mailer.send_email("user@domain.test", "Subjek", '<div><a href="https://crm.example.org/notifications">Open</a></div>', "notif-abc")
    assert provider_id == "gmail-1"
    assert captured["url"] == "https://n8n.example.org/webhook/crm-email"
    assert captured["header"] == "y" * 32
    assert captured["body"]["to"] == "user@domain.test"

    monkeypatch.setenv("N8N_EMAIL_WEBHOOK_URL", "https://n8n.example.org/webhook-test/crm-email")
    with pytest.raises(ValueError, match="webhook-test"):
        await mailer.send_email("user@domain.test", "Subjek", "<div>x</div>", "notif-y")


@pytest.mark.anyio
async def test_whatsapp_contract_webhook_validation_and_response_acceptance(monkeypatch):
    import sys

    sys.path.insert(0, "/app/backend")
    import whatsapp  # noqa: WPS433

    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["header"] = request.headers.get("X-CRM-Webhook-Secret")
        observed["body"] = json.loads(request.content.decode())
        return httpx.Response(
            202,
            json={
                "ok": True,
                "status": "accepted",
                "notification_id": "notif-1",
                "message_id": "wamid-1",
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class _ClientFactory:
        def __call__(self, *args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("N8N_WAHA_WEBHOOK_URL", "https://n8n.example.org/webhook/crm-whatsapp")
    monkeypatch.setenv("N8N_WAHA_WEBHOOK_SECRET", "x" * 32)
    monkeypatch.setenv("APP_URL", "https://crm.example.org")
    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _ClientFactory())

    provider_id = await whatsapp.send_whatsapp("0812 3456 7890", "notif-1", "user-1", "project-1")
    assert provider_id == "wamid-1"
    assert observed["url"].startswith("https://n8n.example.org/webhook/")
    assert observed["header"] == "x" * 32
    assert observed["body"]["phone_e164"] == "+6281234567890"

    def wrong_body(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "status": "accepted", "notification_id": "wrong", "message_id": "mid"})

    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _ClientFactory())
    transport2 = httpx.MockTransport(wrong_body)

    class _ClientFactory2:
        def __call__(self, *args, **kwargs):
            kwargs["transport"] = transport2
            return real_client(*args, **kwargs)

    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _ClientFactory2())
    with pytest.raises(ValueError, match="tidak sesuai"):
        await whatsapp.send_whatsapp("+6281234567890", "notif-2", "user-1", "")


# Module: guide + workflow public assets
def test_public_markdown_guide_and_workflow_json_are_downloadable_and_safe():
    guide = requests.get(f"{BASE_URL}/panduan-notifikasi.md", timeout=20)
    assert guide.status_code == 200
    text = guide.text
    assert "Resend" not in text and "n8n" in text and "WAHA" in text
    assert "N8N_WAHA_WEBHOOK_URL" in text
    assert "/webhook-test/" in text and "/webhook/" in text

    # Ensure no obvious live secret literals are exposed in public docs.
    assert "sk_live_" not in text
    assert "Bearer " not in text

    workflow = requests.get(f"{BASE_URL}/n8n-waha-workflow.json", timeout=20)
    assert workflow.status_code == 200
    body = workflow.json()
    assert body.get("active") is False
    nodes = body.get("nodes", [])
    assert any(node.get("name") == "Kirim via WAHA" for node in nodes)
    send_node = next(node for node in nodes if node.get("name") == "Kirim via WAHA")
    options = send_node.get("parameters", {}).get("options", {})
    response_opts = options.get("response", {}).get("response", {})
    assert response_opts.get("fullResponse") is True
    assert response_opts.get("neverError") is True
    assert send_node.get("onError") == "continueRegularOutput"
    assert send_node.get("retryOnFail") is False


# Module: regression smoke for Kanban->ticket sync remains alive
def test_ticket_to_task_sync_regression_smoke_still_works(actors):
    client_session, _ = actors["client"]
    admin_session, _ = actors["admin"]

    create = client_session.post(
        f"{API}/tickets",
        json={
            "project_id": "project-1",
            "title": f"TEST_ITER30_SYNC_{uuid.uuid4().hex[:6]}",
            "description": "sync smoke",
            "category": "Bug / Problem",
            "priority": "Sedang",
        },
        timeout=25,
    )
    assert create.status_code == 200, create.text
    ticket = create.json()
    task_id = ticket.get("task_id")
    assert isinstance(task_id, str) and task_id

    moved = admin_session.patch(f"{API}/projects/project-1/tasks/{task_id}", json={"status": "Dikerjakan"}, timeout=25)
    assert moved.status_code == 200, moved.text

    detail = admin_session.get(f"{API}/tickets/{ticket['id']}", timeout=20)
    assert detail.status_code == 200
    assert detail.json().get("status") == "Dikerjakan"


# Module: code review assertion for seed behavior expectations
def test_seed_logic_currently_does_not_update_existing_admin_password_on_nonempty_users_collection():
    seed_file = Path("/app/backend/seed.py").read_text(encoding="utf-8")
    assert "if await db.users.count_documents({}): return" in seed_file
