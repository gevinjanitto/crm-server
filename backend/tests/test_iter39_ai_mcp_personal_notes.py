# Iter39: Personal notes (multi-doc), AI toggle, PAT tokens, AI tools, MCP, OAuth 2.1, assistant, setup.sh
import os, re, base64, hashlib, io, tarfile
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "Maiharta2026!"
_cache = {}


def login(username):
    if username in _cache: return _cache[username]
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*x×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = {"+": a + b, "-": a - b, "*": a * b, "x": a * b, "×": a * b}[op]
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200: pytest.skip(f"login {username} gagal {r.status_code} {r.text}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    s.user = r.json()["user"]
    _cache[username] = s
    return s


def bearer(t): return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin():
    s = login("admin")
    assert s.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": True}).status_code == 200
    yield s
    # cleanup TEST tokens
    for t in s.get(f"{BASE}/api/admin/tokens").json():
        if t["name"].startswith("TEST") and not t.get("revoked_at"): s.delete(f"{BASE}/api/admin/tokens/{t['id']}")
    s.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": True})


@pytest.fixture(scope="module")
def dev(admin): return login("developer")


def pat(s, scopes, name="TEST_pat"):
    r = s.post(f"{BASE}/api/me/tokens", json={"name": name, "scopes": scopes})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Personal notes ----------
class TestPersonalNotes:
    def test_crud_versions_privacy(self, admin, dev):
        r = admin.post(f"{BASE}/api/personal-notes", json={"title": "TEST_note", "content": "<p>halo</p>"})
        assert r.status_code == 200, r.text
        d = r.json(); assert d["title"] == "TEST_note" and d["version"] == 1
        lst = admin.get(f"{BASE}/api/personal-notes").json()
        assert any(x["id"] == d["id"] for x in lst)
        r = admin.patch(f"{BASE}/api/personal-notes/{d['id']}", json={"title": "TEST_note2", "content": "<p>baru</p>", "version": 1})
        assert r.status_code == 200 and r.json()["version"] == 2
        # stale version -> 409
        assert admin.patch(f"{BASE}/api/personal-notes/{d['id']}", json={"title": "x", "content": "", "version": 1}).status_code == 409
        vers = admin.get(f"{BASE}/api/personal-notes/{d['id']}/versions").json()
        assert [v["version"] for v in vers][:2] == [2, 1]
        # privacy
        assert all(x["id"] != d["id"] for x in dev.get(f"{BASE}/api/personal-notes").json())
        assert dev.get(f"{BASE}/api/personal-notes/{d['id']}/versions").status_code == 404
        assert dev.patch(f"{BASE}/api/personal-notes/{d['id']}", json={"title": "hack", "content": "", "version": 2}).status_code == 404
        assert dev.delete(f"{BASE}/api/personal-notes/{d['id']}").status_code == 404
        # delete
        assert admin.delete(f"{BASE}/api/personal-notes/{d['id']}").status_code == 200
        assert admin.get(f"{BASE}/api/personal-notes/{d['id']}/versions").status_code == 404

    def test_checklist_content_preserved(self, dev):
        html = '<ul data-type="taskList"><li data-type="taskItem" data-checked="true"><p>a</p></li></ul>'
        d = dev.post(f"{BASE}/api/personal-notes", json={"title": "TEST_check", "content": html}).json()
        assert 'data-type="taskList"' in d["content"] and 'data-checked="true"' in d["content"]
        dev.delete(f"{BASE}/api/personal-notes/{d['id']}")

    @pytest.mark.parametrize("user", ["client", "accounting"])
    def test_forbidden_roles(self, admin, user):
        s = login(user)
        assert s.get(f"{BASE}/api/personal-notes").status_code == 403
        assert s.post(f"{BASE}/api/personal-notes", json={"title": "x"}).status_code == 403


# ---------- AI settings & toggle ----------
class TestAiSettings:
    def test_admin_settings_no_key_leak(self, admin, dev):
        r = admin.get(f"{BASE}/api/admin/ai-settings"); d = r.json()
        assert r.status_code == 200 and d["enabled"] is True and "api_key" not in d
        assert dev.get(f"{BASE}/api/admin/ai-settings").status_code == 403
        assert dev.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": False}).status_code == 403
        st = dev.get(f"{BASE}/api/ai/status").json(); assert st["enabled"] is True and st["allowed"] is True
        assert login("client").get(f"{BASE}/api/ai/status").json()["allowed"] is False

    def test_toggle_off_blocks_everything(self, admin):
        t = pat(admin, ["read"])["token"]
        admin.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": False})
        try:
            assert admin.get(f"{BASE}/api/me/tokens").status_code == 403
            assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(t)).status_code == 403
            assert requests.post(f"{BASE}/api/mcp", headers=bearer(t), json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 403
            assert admin.get(f"{BASE}/api/ai/status").json()["enabled"] is False
        finally:
            admin.patch(f"{BASE}/api/admin/ai-settings", json={"enabled": True})
        assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(t)).status_code == 200


# ---------- Tokens ----------
class TestTokens:
    def test_client_forbidden(self, admin):
        assert login("client").get(f"{BASE}/api/me/tokens").status_code == 403
        assert login("accounting").post(f"{BASE}/api/me/tokens", json={"name": "TEST"}).status_code == 403

    def test_list_no_hash_and_max_10(self, dev, admin):
        made = []
        try:
            active = [t for t in dev.get(f"{BASE}/api/me/tokens").json() if t["kind"] == "pat" and not t.get("revoked_at")]
            for i in range(10 - len(active)): made.append(pat(dev, ["read"], f"TEST_max{i}")["id"])
            r = dev.post(f"{BASE}/api/me/tokens", json={"name": "TEST_over"})
            assert r.status_code == 400 and "Maksimal" in r.json()["detail"]
            lst = dev.get(f"{BASE}/api/me/tokens").json()
            assert all("token_hash" not in t and "token" not in t for t in lst)
            assert dev.get(f"{BASE}/api/admin/tokens").status_code == 403
            all_t = admin.get(f"{BASE}/api/admin/tokens").json()
            mine = [t for t in all_t if t["id"] in made]
            assert mine and mine[0]["user_name"]
            assert admin.delete(f"{BASE}/api/admin/tokens/{made[0]}").status_code == 200
            assert any(t["id"] == made[0] and t["revoked_at"] for t in dev.get(f"{BASE}/api/me/tokens").json())
        finally:
            for tid in made: dev.delete(f"{BASE}/api/me/tokens/{tid}")

    def test_cannot_revoke_others_token(self, admin, dev):
        t = pat(admin, ["read"])
        assert dev.delete(f"{BASE}/api/me/tokens/{t['id']}").status_code == 404
        admin.delete(f"{BASE}/api/me/tokens/{t['id']}")

    def test_invalid_token_401(self):
        r = requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer("mh_pat_invalid"))
        assert r.status_code == 401


# ---------- AI tools ----------
class TestAiTools:
    def test_dev_scope_and_kapasitas(self, admin, dev):
        dt = pat(dev, ["read"])["token"]
        dev_p = requests.get(f"{BASE}/api/ai/tools/daftar_project", headers=bearer(dt)).json()["result"]
        adm_p = admin.get(f"{BASE}/api/ai/tools/daftar_project").json()["result"]
        dev_ids, adm_ids = {p["id"] for p in dev_p}, {p["id"] for p in adm_p}
        assert dev_ids <= adm_ids and dev_ids != adm_ids
        assert requests.get(f"{BASE}/api/ai/tools/kapasitas_tim", headers=bearer(dt)).status_code == 403
        assert admin.get(f"{BASE}/api/ai/tools/kapasitas_tim").status_code == 200
        # dev cannot read task in non-member project
        other = next(iter(adm_ids - dev_ids))
        tasks = admin.get(f"{BASE}/api/projects/{other}/tasks").json()
        if tasks:
            r = requests.get(f"{BASE}/api/ai/tools/detail_tugas", headers=bearer(dt), params={"task_id": tasks[0]["id"]})
            assert r.status_code in (403, 404)
        assert len(requests.get(f"{BASE}/api/ai/tools", headers=bearer(dt)).json()) == 14

    def test_write_pat_assign_logged(self, admin, dev):
        dt = pat(dev, ["read", "write"])["token"]
        pid = requests.get(f"{BASE}/api/ai/tools/daftar_project", headers=bearer(dt)).json()["result"][0]["id"]
        task = admin.post(f"{BASE}/api/projects/{pid}/tasks", json={"title": "TEST_ai_assign"}).json()
        assert "id" in task, task
        try:
            ro = pat(dev, ["read"])["token"]
            assert requests.post(f"{BASE}/api/ai/tools/assign_tugas", headers=bearer(ro), json={"task_id": task["id"]}).status_code == 403
            r = requests.post(f"{BASE}/api/ai/tools/assign_tugas", headers=bearer(dt), json={"task_id": task["id"]})
            assert r.status_code == 200, r.text
            assert dev.user["name"] in r.json()["result"]["assignees"]
            logs = admin.get(f"{BASE}/api/audit", params={"q": "AI: assign_tugas", "limit": 20}).json()
            assert any(l["entity_id"] == task["id"] for l in logs)
            r = requests.post(f"{BASE}/api/ai/tools/tambah_komentar", headers=bearer(dt), json={"task_id": task["id"], "teks": "TEST komentar"})
            assert r.status_code == 200 and r.json()["result"]["teks"]
            assert requests.post(f"{BASE}/api/ai/tools/assign_tugas", headers=bearer(dt), json={}).status_code == 400
            assert requests.get(f"{BASE}/api/ai/tools/tidak_ada", headers=bearer(dt)).status_code == 404
        finally:
            admin.delete(f"{BASE}/api/projects/{pid}/tasks/{task['id']}")


# ---------- MCP ----------
class TestMcp:
    def test_mcp_flow(self, dev):
        t = pat(dev, ["read"])["token"]
        rpc = lambda m, p=None, i=1: requests.post(f"{BASE}/api/mcp", headers=bearer(t), json={"jsonrpc": "2.0", "id": i, "method": m, "params": p or {}})
        init = rpc("initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
        assert init["protocolVersion"] == "2025-06-18" and init["capabilities"]["tools"]
        tools = rpc("tools/list").json()["result"]["tools"]
        assert len(tools) == 14 and all("inputSchema" in x for x in tools)
        r = rpc("tools/call", {"name": "tugas_saya", "arguments": {}}).json()["result"]
        assert r["isError"] is False and r["content"][0]["type"] == "text"
        r = rpc("tools/call", {"name": "kapasitas_tim", "arguments": {}}).json()["result"]
        assert r["isError"] is True and "403" in r["content"][0]["text"]
        r = rpc("tools/call", {"name": "assign_tugas", "arguments": {"task_id": "x"}}).json()["result"]
        assert r["isError"] is True and "403" in r["content"][0]["text"]
        assert rpc("foo/bar").json()["error"]["code"] == -32601
        n = requests.post(f"{BASE}/api/mcp", headers=bearer(t), json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert n.status_code == 202

    def test_mcp_no_token(self):
        r = requests.post(f"{BASE}/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r.status_code == 401
        assert "resource_metadata=" in r.headers.get("WWW-Authenticate", "")


# ---------- OAuth ----------
class TestOAuth:
    REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"

    def test_metadata(self):
        pr = requests.get(f"{BASE}/api/.well-known/oauth-protected-resource").json()
        assert pr["resource"].endswith("/api/mcp") and pr["authorization_servers"]
        asm = requests.get(f"{BASE}/api/.well-known/oauth-authorization-server").json()
        assert asm["code_challenge_methods_supported"] == ["S256"] and asm["token_endpoint"].endswith("/api/oauth/token")
        assert pr["resource"].startswith("https://")

    def test_full_flow(self, admin):
        reg = requests.post(f"{BASE}/api/oauth/register", json={"client_name": "TEST_oauth", "redirect_uris": [self.REDIRECT]})
        assert reg.status_code == 201
        cid = reg.json()["client_id"]
        assert requests.post(f"{BASE}/api/oauth/register", json={"redirect_uris": ["http://evil.com/cb"]}).status_code == 400
        verifier = "TESTverifier" * 5
        ch = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        a = requests.get(f"{BASE}/api/oauth/authorize", params={"client_id": cid, "redirect_uri": self.REDIRECT, "response_type": "code", "code_challenge": ch, "code_challenge_method": "S256", "state": "st"}, allow_redirects=False)
        assert a.status_code == 302 and "/oauth/authorize?" in a.headers["location"] and "/api/" not in a.headers["location"]
        bad = requests.get(f"{BASE}/api/oauth/authorize", params={"client_id": cid, "redirect_uri": "https://evil.com", "code_challenge": ch}, allow_redirects=False)
        assert bad.status_code == 400
        assert admin.get(f"{BASE}/api/oauth/client", params={"client_id": cid, "redirect_uri": self.REDIRECT}).json()["client_name"] == "TEST_oauth"
        red = admin.post(f"{BASE}/api/oauth/approve", json={"client_id": cid, "redirect_uri": self.REDIRECT, "code_challenge": ch, "state": "st", "scope": "read write"}).json()["redirect"]
        code = re.search(r"code=([^&]+)", red).group(1); assert "state=st" in red
        # wrong verifier
        w = requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": self.REDIRECT, "client_id": cid, "code_verifier": "wrong" * 10})
        assert w.status_code == 400 and w.json()["error"] == "invalid_grant"
        # code consumed even after wrong verifier -> get a fresh one
        red = admin.post(f"{BASE}/api/oauth/approve", json={"client_id": cid, "redirect_uri": self.REDIRECT, "code_challenge": ch, "state": "st", "scope": "read write"}).json()["redirect"]
        code = re.search(r"code=([^&]+)", red).group(1)
        tok = requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": self.REDIRECT, "client_id": cid, "code_verifier": verifier}).json()
        assert tok["access_token"].startswith("mh_oat_") and tok["refresh_token"] and "write" in tok["scope"]
        reuse = requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "authorization_code", "code": code, "client_id": cid, "code_verifier": verifier})
        assert reuse.status_code == 400
        m = requests.post(f"{BASE}/api/mcp", headers=bearer(tok["access_token"]), json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert m.status_code == 200 and m.json()["result"]["tools"]
        ref = requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
        assert ref["access_token"].startswith("mh_oat_") and ref["access_token"] != tok["access_token"]
        assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(tok["access_token"])).status_code == 401
        assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(ref["access_token"])).status_code == 200
        # old refresh token invalid
        assert requests.post(f"{BASE}/api/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).status_code == 400
        # revoke
        requests.post(f"{BASE}/api/oauth/revoke", data={"token": ref["access_token"]})
        assert requests.get(f"{BASE}/api/ai/tools/tugas_saya", headers=bearer(ref["access_token"])).status_code == 401
        deny = admin.post(f"{BASE}/api/oauth/approve", json={"client_id": cid, "redirect_uri": self.REDIRECT, "code_challenge": ch, "approve": False}).json()["redirect"]
        assert "error=access_denied" in deny

    def test_client_cannot_approve(self, admin):
        cid = requests.post(f"{BASE}/api/oauth/register", json={"client_name": "TEST", "redirect_uris": [self.REDIRECT]}).json()["client_id"]
        r = login("client").post(f"{BASE}/api/oauth/approve", json={"client_id": cid, "redirect_uri": self.REDIRECT, "code_challenge": "c" * 43})
        assert r.status_code == 403


# ---------- Assistant ----------
class TestAssistant:
    def test_chat_503_without_key(self, admin):
        s = admin.get(f"{BASE}/api/admin/ai-settings").json()
        if s["assistant_ready"]: pytest.skip("assistant configured")
        r = admin.post(f"{BASE}/api/assistant/chat", json={"message": "halo"})
        assert r.status_code == 503 and "belum dikonfigurasi" in r.json()["detail"]
        assert login("client").post(f"{BASE}/api/assistant/chat", json={"message": "halo"}).status_code == 403


# ---------- setup.sh ----------
class TestSetupSh:
    def test_download_and_archive(self):
        r = requests.get(f"{BASE}/setup.sh")
        assert r.status_code == 200 and r.text.startswith("#!")
        assert "__ARCHIVE_BELOW__" in r.text
        payload = r.text.split("__ARCHIVE_BELOW__", 2)[-1].strip()
        raw = base64.b64decode(payload)
        names = tarfile.open(fileobj=io.BytesIO(raw), mode="r:*").getnames()
        norm = [n.lstrip("./") for n in names]
        assert not any(n.endswith("backend/.env") or n.endswith("frontend/.env") for n in norm), [n for n in norm if n.endswith(".env")]
        assert any(n.endswith("backend/server.py") for n in norm) and any(n.endswith("personal_notes.py") for n in norm)
        assert any(n.endswith("mcp_server.py") for n in norm) and any("PersonalNotes.jsx" in n for n in norm)
        assert not any("node_modules/" in n for n in norm)
