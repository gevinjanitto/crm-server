"""Helper script to login as admin and print JSON {token, user}."""
import os, re, json, sys, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://crm-admin-notif.preview.emergentagent.com").rstrip("/")

def login(username="admin", password="Maiharta2026!"):
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    q = cap["question"]
    # parse like "6 + 1 = ?"
    m = re.match(r"\s*(\d+)\s*([+\-*])\s*(\d+)", q)
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = {"+": a+b, "-": a-b, "*": a*b}[op]
    r = s.post(f"{BASE}/api/auth/login", json={
        "username": username,
        "password": password,
        "captcha_id": cap["id"],
        "captcha_answer": str(ans),
    })
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print(json.dumps(login()))
