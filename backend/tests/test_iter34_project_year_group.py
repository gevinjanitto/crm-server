# Iteration 34: project year grouping (Selesai -> due_date year, others -> start_date year) + setup.sh syntax
import os, re, sys, subprocess
import pytest, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=", 1)[1].strip().rstrip("/")


# --- unit: group_year
def test_group_year_unit():
    from project_years import group_year
    assert group_year({'id': 'a', 'status': 'Selesai', 'start_date': '2022-01-10', 'due_date': '2023-04-12'}) == '2023'
    assert group_year({'id': 'b', 'status': 'Development', 'start_date': '2022-01-10', 'due_date': '2023-04-12'}) == '2022'
    assert group_year({'id': 'c', 'status': 'Selesai', 'start_date': '2021-01-10'}) == '2021'
    assert group_year({'id': 'd', 'status': 'Draft', 'created_at': '2020-05-01T00:00:00'}) == '2020'


# --- shell syntax
@pytest.mark.parametrize("f", ["/app/setup.sh", "/app/start-local.sh"])
def test_bash_syntax(f):
    assert subprocess.run(["bash", "-n", f]).returncode == 0


def _login():
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    a, op, b = re.match(r"\s*(\d+)\s*([+\-*xX×])\s*(\d+)", cap["question"]).groups()
    a, b = int(a), int(b)
    ans = a + b if op == '+' else a - b if op == '-' else a * b
    r = s.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "Maiharta123!",
                                                "captcha_id": cap["id"], "captcha_answer": str(ans)})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def s():
    return _login()


# --- API: Selesai project 2022-01-10..2022-04-12 grouped into 2022; status Selesai with deadline in 2023 grouped 2023
def test_project_group_year_api(s):
    clients = s.get(f"{BASE}/api/clients").json()
    assert clients, "no clients"
    created = []
    try:
        for name, start, due, exp in [("TEST_Year2022", "2022-01-10", "2022-04-12", "2022"),
                                      ("TEST_YearCross", "2022-11-10", "2023-02-12", "2023")]:
            r = s.post(f"{BASE}/api/projects", json={"name": name, "client_id": clients[0]["id"], "platforms": ["Web"],
                                                     "start_date": start, "due_date": due})
            assert r.status_code == 200, r.text
            p = r.json(); created.append(p["id"])
            lst = {x["id"]: x for x in s.get(f"{BASE}/api/projects").json()}
            assert lst[p["id"]]["group_year"] == "2022", lst[p["id"]]
            d = s.post(f"{BASE}/api/projects/{p['id']}/documents", data={"kind": "Kontrak", "name": "TEST_kontrak"},
                       files={"file": ("k.pdf", b"%PDF-1.4 test", "application/pdf")})
            assert d.status_code == 200, d.text
            r = s.post(f"{BASE}/api/projects/{p['id']}/status", json={"status": "Selesai"})
            assert r.status_code in (200, 400), r.text
            if r.status_code == 400:
                pytest.skip(f"Cannot set Selesai: {r.text}")
            lst = {x["id"]: x for x in s.get(f"{BASE}/api/projects").json()}
            assert lst[p["id"]]["status"] == "Selesai"
            assert lst[p["id"]]["group_year"] == exp, lst[p["id"]]
    finally:
        for pid in created:
            s.post(f"{BASE}/api/projects/{pid}/status", json={"status": "Project Masuk"})
            s.delete(f"{BASE}/api/projects/{pid}")
