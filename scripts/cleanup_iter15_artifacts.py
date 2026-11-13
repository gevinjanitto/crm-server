"""Cleanup temporary TEST_REPRO artifacts created during iteration 15 testing."""

import json
import re

import requests
from dotenv import dotenv_values


FRONTEND_ENV = dotenv_values('/app/frontend/.env')
BACKEND_ENV = dotenv_values('/app/backend/.env')
BASE_URL = (FRONTEND_ENV.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
API = f"{BASE_URL}/api"
PASSWORD = BACKEND_ENV.get('SEED_PASSWORD', '')


def solve(question: str) -> str:
    return str(sum(int(x) for x in re.findall(r'\d+', question)))


def login(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    cap = s.get(f"{API}/auth/captcha", timeout=20)
    cap.raise_for_status()
    c = cap.json()
    auth = s.post(
        f"{API}/auth/login",
        json={
            'username': username,
            'password': PASSWORD,
            'captcha_id': c.get('id', ''),
            'captcha_answer': solve(c.get('question', '0+0')),
        },
        timeout=25,
    )
    auth.raise_for_status()
    token = auth.json()['token']
    s.headers.update({'Authorization': f'Bearer {token}'})
    return s


def main() -> None:
    if not BASE_URL or not PASSWORD:
        print('Missing BASE_URL or PASSWORD; skip cleanup')
        return
    session = login('adminproject')

    tasks = session.get(f"{API}/projects/project-1/tasks", timeout=25)
    if tasks.status_code == 200:
        for t in tasks.json():
            if str(t.get('title', '')).startswith('TEST_REPRO_'):
                session.delete(f"{API}/projects/project-1/tasks/{t['id']}", timeout=20)

    statuses = session.get(f"{API}/projects/project-1/statuses", timeout=25)
    if statuses.status_code == 200:
        for s in statuses.json():
            if str(s.get('name', '')).startswith('TEST_REPRO_COL_'):
                session.delete(f"{API}/projects/project-1/statuses/{s['id']}?move_to=Belum%20Mulai", timeout=20)

    print(json.dumps({'cleanup': 'done', 'prefixes': ['TEST_REPRO_', 'TEST_REPRO_COL_']}))


if __name__ == '__main__':
    main()