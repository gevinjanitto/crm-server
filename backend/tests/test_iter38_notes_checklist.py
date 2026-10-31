# Notes checklist (tiptap taskList) sanitizer persistence + /api/notes + setup.sh payload freshness
import os, re, subprocess, tempfile
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "Maiharta123!"
PID = "project-5"
CHECK_HTML = ('<ul data-type="taskList"><li data-type="taskItem" data-checked="true"><label><input type="checkbox" checked="checked"><span></span></label>'
              '<div><p>TEST_A</p></div></li><li data-type="taskItem" data-checked="false"><label><input type="checkbox"><span></span></label><div><p>TEST_B</p></div></li></ul>')


def login(username):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = a + b if op == "+" else a - b if op == "-" else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": username, "password": PWD, "captcha_id": cap["id"], "captcha_answer": str(ans)})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin")


@pytest.fixture(scope="module")
def doc(admin):
    r = admin.post(f"{BASE}/api/projects/{PID}/workspace/docs", json={"title": "TEST_checklist", "content": CHECK_HTML + '<script>alert(1)</script><p onclick="x()">ok</p>', "visibility": "Internal"})
    assert r.status_code == 200, r.text
    d = r.json()
    yield d
    admin.delete(f"{BASE}/api/projects/{PID}/workspace/docs/{d['id']}")


# create keeps taskList attrs, strips script/onclick
def test_create_keeps_checklist(doc):
    c = doc["content"]
    assert 'data-type="taskList"' in c and 'data-type="taskItem"' in c
    assert 'data-checked="true"' in c and 'data-checked="false"' in c
    assert 'type="checkbox"' in c and 'checked' in c
    assert "<script" not in c and "onclick" not in c


# update toggles checked state and persists
def test_update_toggle_persists(admin, doc):
    new = CHECK_HTML.replace('data-checked="false"', 'data-checked="true"')
    r = admin.patch(f"{BASE}/api/projects/{PID}/workspace/docs/{doc['id']}", json={"title": "TEST_checklist", "content": new, "visibility": "Internal", "version": doc["version"]})
    assert r.status_code == 200, r.text
    rows = admin.get(f"{BASE}/api/projects/{PID}/workspace/docs").json()
    got = next(d for d in rows if d["id"] == doc["id"])
    assert got["content"].count('data-checked="true"') == 2
    assert got["version"] == doc["version"] + 1


# /api/notes returns content with checklist
def test_notes_menu_content(admin, doc):
    rows = admin.get(f"{BASE}/api/notes").json()
    n = next(x for x in rows if x["id"] == doc["id"])
    assert 'data-type="taskItem"' in n["content"]
    assert any(x["title"] == "Checklist rilis" for x in rows)


# disallowed attrs on input (e.g. onfocus) stripped
def test_input_attr_xss_stripped(admin):
    r = admin.post(f"{BASE}/api/projects/{PID}/workspace/docs", json={"title": "TEST_xss", "content": '<input type="checkbox" onfocus="alert(1)" autofocus><div style="x" onmouseover="y">t</div>', "visibility": "Internal"})
    assert r.status_code == 200
    c = r.json()["content"]
    admin.delete(f"{BASE}/api/projects/{PID}/workspace/docs/{r.json()['id']}")
    assert "onfocus" not in c and "autofocus" not in c and "onmouseover" not in c and "style" not in c


# setup.sh downloadable
def test_setup_download():
    r = requests.get(f"{BASE}/setup.sh")
    assert r.status_code == 200 and r.text.startswith("#!/usr/bin/env bash") and "__PAYLOAD_BELOW__" in r.text


# setup.sh payload contains checklist changes
def test_setup_payload_fresh():
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(f"curl -s {BASE}/setup.sh | sed -n '/^__PAYLOAD_BELOW__$/,$p' | tail -n +2 | base64 -d | tar -xzf - -C {t}", shell=True, check=True)
        assert "toggleTaskList" in open(f"{t}/frontend/src/components/workspace/DocsPage.jsx").read()
        assert "@tiptap/extension-list\"" in open(f"{t}/frontend/package.json").read()
        assert "data-checked" in open(f"{t}/backend/workspace_collab.py").read()
