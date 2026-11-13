"""Iteration 10 targeted auth token bootstrap + prefixed artifact cleanup."""

import json
import re
from pathlib import Path

import requests
from dotenv import dotenv_values


BASE = dotenv_values(Path(__file__).parents[2] / "frontend" / ".env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
PASSWORD = dotenv_values(Path(__file__).parents[1] / '.env')['SEED_PASSWORD']
PID = "project-1"
OUT = Path("/app/test_reports/iter10_tokens.json")


def _solve(question: str) -> str:
    return str(sum(int(x) for x in re.findall(r"\d+", question)))


def _login(username: str):
    s = requests.Session()
    cap = s.get(f"{BASE}/auth/captcha", timeout=20)
    assert cap.status_code == 200, cap.text
    cj = cap.json()
    r = s.post(
        f"{BASE}/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
            "captcha_id": cj["id"],
            "captcha_answer": _solve(cj["question"]),
            "remember": False,
        },
        timeout=20,
    )
    assert r.status_code == 200, f"{username}: {r.status_code} {r.text}"
    data = r.json()
    return s, data["token"], data["user"]


def test_generate_tokens_and_cleanup_prefixed_artifacts():
    users = ["admin", "adminproject", "developer", "client", "accounting"]
    sessions = {}
    tokens = {}
    user_data = {}

    for username in users:
        s, token, user = _login(username)
        sessions[username] = s
        tokens[username] = token
        user_data[username] = {"id": user["id"], "role": user["role"], "name": user["name"]}

    # Clean this iteration's prefixed saved views from adminproject account
    h_ap = {"Authorization": f"Bearer {tokens['adminproject']}"}
    views = requests.get(f"{BASE}/projects/{PID}/task-views", headers=h_ap, timeout=20)
    assert views.status_code == 200, views.text
    for v in views.json():
        if str(v.get("name", "")).startswith("UIT10_"):
            requests.delete(f"{BASE}/projects/{PID}/task-views/{v['id']}", headers=h_ap, timeout=20)

    # Disable old prefixed active automation rules that contaminate regression checks
    autom = requests.get(f"{BASE}/projects/{PID}/workspace/automations", headers=h_ap, timeout=20)
    assert autom.status_code == 200, autom.text
    aj = autom.json()
    for rule in aj.get("rules", []):
        name = str(rule.get("name", ""))
        if rule.get("enabled") and (name.startswith("UIT9") or name.startswith("UIT10") or name.startswith("Test_I9")):
            payload = {k: rule.get(k) for k in ["name", "trigger", "condition_field", "condition_value", "action", "action_value"]}
            payload["enabled"] = False
            requests.patch(f"{BASE}/projects/{PID}/workspace/automations/{rule['id']}", headers=h_ap, json=payload, timeout=20)

    # Verify last_run is scoped to project/global only
    latest = requests.get(f"{BASE}/projects/{PID}/workspace/automations", headers=h_ap, timeout=20)
    assert latest.status_code == 200
    last_run = latest.json().get("last_run")
    if last_run:
        assert last_run.get("project_id") in [PID, None]

    OUT.write_text(json.dumps({"base": BASE.removesuffix("/api"), "tokens": tokens, "users": user_data}, ensure_ascii=False), encoding="utf-8")
    assert OUT.exists()
