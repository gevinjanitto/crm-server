"""Iter6: /api/account/notifications/daily-stats admin-only + payload shape."""
import os, requests, pytest
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE}/api"

def login(username):
    s = requests.Session()
    c = s.get(f"{API}/auth/captcha").json()
    parts = c['question'].split()
    a, b = int(parts[0]), int(parts[2])
    ans = a+b if parts[1]=='+' else a-b if parts[1]=='-' else a*b
    tok = s.post(f"{API}/auth/login", json={
        "username": username, "password": os.environ.get("SEED_PASSWORD", ""),
        "captcha_id": c['id'], "captcha_answer": str(ans)
    }).json()['token']
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s

@pytest.fixture(scope="module")
def admin():
    return login("admin")

@pytest.mark.parametrize("user", ["adminproject", "developer", "accounting", "client"])
def test_non_admin_forbidden(user):
    s = login(user)
    r = s.get(f"{API}/account/notifications/daily-stats")
    assert r.status_code == 403, f"{user}: {r.status_code} {r.text}"

def test_admin_payload(admin):
    r = admin.get(f"{API}/account/notifications/daily-stats")
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("email", "whatsapp", "email_daily_limit", "since"):
        assert k in data, f"missing {k}: {data}"
    assert isinstance(data['email'], int) and data['email'] >= 0
    assert isinstance(data['whatsapp'], int) and data['whatsapp'] >= 0
    assert data['email_daily_limit'] == 500
    # since should match today 00:00 Asia/Makassar
    expected = datetime.now(ZoneInfo('Asia/Makassar')).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    assert data['since'] == expected, f"{data['since']} != {expected}"
