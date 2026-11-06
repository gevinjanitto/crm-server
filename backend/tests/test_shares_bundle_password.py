# Bundle/password/no-expiry file shares + notification provider config + setup.sh
import os, re, io, uuid
from datetime import datetime, timedelta, timezone
import pytest, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE}/api"
SAMPLE_TOKEN = "KZ9O52vlcGtvVfvp8ZCockJP"


def login(username, password):
    s = requests.Session()
    cap = s.get(f"{API}/auth/captcha").json()
    a, op, b = re.match(r"\s*(\d+)\s*([+\-*])\s*(\d+)", cap["question"]).groups()
    ans = {"+": int(a) + int(b), "-": int(a) - int(b), "*": int(a) * int(b)}[op]
    r = s.post(f"{API}/auth/login", json={"username": username, "password": password, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if tok: s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin", "Maiharta123!")


@pytest.fixture(scope="module")
def project(admin):
    ps = admin.get(f"{API}/projects").json()
    assert ps, "no projects"
    return ps[0]


@pytest.fixture(scope="module")
def docs(admin, project):
    pid = project["id"]
    out = []
    for i, (fn, ct, body) in enumerate([("TEST_a.txt", "text/plain", b"hello bundle A"), ("TEST_b.txt", "text/plain", b"hello bundle B")]):
        r = admin.post(f"{API}/projects/{pid}/documents", files={"file": (fn, io.BytesIO(body), ct)}, data={"kind": "Lainnya", "visibility": "Internal", "name": f"TEST_doc_{i}"})
        if r.status_code != 200:
            # kind may be restricted; try another
            r = admin.post(f"{API}/projects/{pid}/documents", files={"file": (fn, io.BytesIO(body), ct)}, data={"kind": "Kontrak", "visibility": "Internal", "name": f"TEST_doc_{i}"})
        assert r.status_code == 200, r.text
        out.append(r.json())
    yield out
    for d in out:
        admin.delete(f"{API}/projects/{pid}/documents/{d['id']}")


def fut(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


class TestShares:
    def test_bundle_forever_password(self, admin, docs):
        ids = [d["id"] for d in docs]
        r = admin.post(f"{API}/shares", json={"document_ids": ids, "expires_at": None, "password": "rahasia9", "allow_download": True})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["document_ids"] == ids and s["expires_at"] is None and s["has_password"] is True
        assert "password_hash" not in s
        tok = s["token"]
        # no key -> 401
        assert requests.get(f"{API}/public/shares/{tok}").status_code == 401
        # wrong pw
        assert requests.post(f"{API}/public/shares/{tok}/unlock", json={"password": "nope"}).status_code == 400
        k = requests.post(f"{API}/public/shares/{tok}/unlock", json={"password": "rahasia9"}).json()["key"]
        assert k
        info = requests.get(f"{API}/public/shares/{tok}", params={"k": k}).json()
        assert len(info["files"]) == 2 and info["expires_at"] is None and info["has_password"]
        f = requests.get(f"{API}/public/shares/{tok}/file", params={"doc": ids[1], "k": k, "download": "true"})
        assert f.status_code == 200 and f.content == b"hello bundle B"
        assert "attachment" in f.headers["content-disposition"]
        # file without key -> 401
        assert requests.get(f"{API}/public/shares/{tok}/file", params={"doc": ids[1]}).status_code == 401
        # doc not in share -> 404
        assert requests.get(f"{API}/public/shares/{tok}/file", params={"doc": "xxx", "k": k}).status_code == 404
        # listed for doc
        rows = admin.get(f"{API}/shares", params={"document_id": ids[1]}).json()
        assert any(x["id"] == s["id"] for x in rows)
        # revoke -> 404
        assert admin.delete(f"{API}/shares/{s['id']}").status_code == 200
        assert requests.get(f"{API}/public/shares/{tok}", params={"k": k}).status_code == 404

    def test_bundle_document_type(self, admin, docs):
        r = admin.post(f"{API}/shares", json={"document_ids": [d["id"] for d in docs], "expires_at": fut()})
        s = r.json()
        admin.delete(f"{API}/shares/{s['id']}")
        assert s["document_type"] == "bundle", f"bundle share stored document_type={s['document_type']}"

    def test_view_only_blocks_download(self, admin, docs):
        s = admin.post(f"{API}/shares", json={"document_id": docs[0]["id"], "expires_at": fut(), "allow_download": False}).json()
        tok = s["token"]
        assert requests.get(f"{API}/public/shares/{tok}/file", params={"download": "true"}).status_code == 403
        v = requests.get(f"{API}/public/shares/{tok}/file")
        assert v.status_code == 200 and "inline" in v.headers["content-disposition"]
        info = requests.get(f"{API}/public/shares/{tok}").json()
        assert info["allow_download"] is False and info["name"] == docs[0]["name"]
        admin.delete(f"{API}/shares/{s['id']}")

    def test_single_legacy_without_password(self, admin, docs):
        s = admin.post(f"{API}/shares", json={"document_id": docs[0]["id"], "expires_at": fut(1)}).json()
        assert s["has_password"] is False and s["expires_at"]
        info = requests.get(f"{API}/public/shares/{s['token']}").json()
        assert info["document_type"] == "file" and len(info["files"]) == 1
        assert requests.post(f"{API}/public/shares/{s['token']}/unlock", json={"password": "x"}).json()["key"] == ""
        admin.delete(f"{API}/shares/{s['id']}")

    def test_validation(self, admin, docs):
        assert admin.post(f"{API}/shares", json={"document_ids": []}).status_code == 400
        assert admin.post(f"{API}/shares", json={"document_id": docs[0]["id"], "expires_at": fut(-1)}).status_code == 400
        assert admin.post(f"{API}/shares", json={"document_id": docs[0]["id"], "expires_at": fut(24 * 400)}).status_code == 400
        assert admin.post(f"{API}/shares", json={"document_id": docs[0]["id"], "password": "ab"}).status_code == 400
        assert admin.post(f"{API}/shares", json={"document_ids": ["nonexist"]}).status_code == 404

    def test_sample_token(self):
        assert requests.get(f"{API}/public/shares/{SAMPLE_TOKEN}").status_code == 401
        r = requests.post(f"{API}/public/shares/{SAMPLE_TOKEN}/unlock", json={"password": "rahasia1"})
        assert r.status_code == 200 and r.json()["key"]
        info = requests.get(f"{API}/public/shares/{SAMPLE_TOKEN}", params={"k": r.json()["key"]}).json()
        assert len(info["files"]) >= 2

    def test_unauthenticated_create(self):
        assert requests.post(f"{API}/shares", json={"document_id": "x"}).status_code == 401

    def test_client_forbidden(self, admin, docs):
        clients = admin.get(f"{API}/clients").json()
        if not clients: pytest.skip("no client available")
        uname = f"test_cl_{uuid.uuid4().hex[:6]}"
        cu = admin.post(f"{API}/users", json={"name": "TEST client", "username": uname, "email": f"{uname}@example.com", "role": "Client", "client_id": clients[0]["id"]}).json()
        try:
            c = login(cu["username"], "12345678")
        except AssertionError:
            pytest.skip("cannot login as client (unknown password)")
        r = c.post(f"{API}/shares", json={"document_id": docs[0]["id"], "expires_at": fut()})
        assert r.status_code == 403, r.text


class TestNotifConfig:
    def test_providers(self, admin):
        r = admin.get(f"{API}/account/notifications")
        assert r.status_code == 200
        d = r.json()
        txt = str(d)
        assert "Gmail API (Google Cloud)" in txt and "WhatsApp API" in txt
        assert "n8n" not in txt.lower() and "waha" not in txt.lower(), txt

    def test_setup_sh(self):
        r = requests.get(f"{BASE}/setup.sh")
        assert r.status_code == 200 and r.text.startswith("#!/usr/bin/env bash") and "__PAYLOAD_BELOW__" in r.text

    def test_guide_md(self):
        r = requests.get(f"{BASE}/panduan-notifikasi.md")
        assert r.status_code == 200
        assert "Gmail" in r.text
