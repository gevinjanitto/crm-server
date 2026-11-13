# Token PAT, AI tools, MCP, dan Asisten AI (fase 1-4) + OAuth (fase 5)
import os, re, base64, hashlib
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
PWD = os.environ.get("SEED_PASSWORD", "Maiharta2026!")


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    a, b = map(int, re.findall(r"\d+", cap["question"])[:2])
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(a + b)})
    if r.status_code != 200: pytest.skip(f"login gagal {r.status_code}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    s = login("admin")
    assert s.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": True}).status_code == 200
    return s


def pat(session, scopes):
    r = session.post(f"{BASE}/api/me/tokens", json={"name": "TEST_pat", "scopes": scopes})
    assert r.status_code == 200, r.text
    return r.json()


def bearer(t): return {"Authorization": f"Bearer {t}"}


def test_pat_read_and_revoke(admin):
    t = pat(admin, ["read"])
    assert t["token"].startswith("mh_pat_") and "token_hash" not in t
    assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(t["token"])).status_code == 200
    r = requests.post(f"{BASE}/api/ai/tools/assign_tugas", headers=bearer(t["token"]), json={"task_id": "x"})
    assert r.status_code == 403
    assert admin.delete(f"{BASE}/api/me/tokens/{t['id']}").status_code == 200
    assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(t["token"])).status_code == 401


def test_mcp_tools_list_and_call(admin):
    t = pat(admin, ["read", "write"])["token"]
    rpc = lambda m, p=None: requests.post(f"{BASE}/api/mcp", headers=bearer(t), json={"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}}).json()
    assert rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]["serverInfo"]["name"] == "crm-maiharta"
    names = {x["name"] for x in rpc("tools/list")["result"]["tools"]}
    assert {"tugas_saya", "assign_tugas", "kapasitas_tim"} <= names
    assert rpc("tools/call", {"name": "daftar_project", "arguments": {}})["result"]["isError"] is False


def test_mcp_requires_token():
    r = requests.post(f"{BASE}/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401 and "resource_metadata" in r.headers.get("WWW-Authenticate", "")


def test_toggle_off_blocks_tokens(admin):
    t = pat(admin, ["read"])["token"]
    admin.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": False})
    try:
        assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(t)).status_code == 403
    finally:
        admin.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": True})


def test_oauth_pkce_flow(admin):
    redirect = "https://chatgpt.com/connector_platform_oauth_redirect"
    cid = requests.post(f"{BASE}/api/oauth/register", json={"client_name": "TEST", "redirect_uris": [redirect]}).json()["client_id"]
    verifier = "v" * 50
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    red = admin.post(f"{BASE}/api/oauth/approve", json={"client_id": cid, "redirect_uri": redirect, "code_challenge": challenge, "state": "s", "scope": "read"}).json()["redirect"]
    code = re.search(r"code=([^&]+)", red).group(1)
    tok = requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "client_id": cid, "code_verifier": verifier}).json()
    assert tok["access_token"].startswith("mh_oat_")
    assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(tok["access_token"])).status_code == 200


def test_assistant_needs_config_or_works(admin):
    r = admin.post(f"{BASE}/api/assistant/chat", json={"message": "ada tugas apa untuk saya?"})
    assert r.status_code in (200, 503)
