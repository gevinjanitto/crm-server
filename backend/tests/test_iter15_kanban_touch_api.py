"""Iteration 15 focused Kanban API regression tests for touch drag scenarios."""

import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


ENV_FRONTEND = dotenv_values(Path('/app/frontend/.env'))
ENV_BACKEND = dotenv_values(Path('/app/backend/.env'))
BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or ENV_FRONTEND.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get('SEED_PASSWORD') or ENV_BACKEND.get('SEED_PASSWORD', '')
PROJECT_ID = 'project-1'


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r'\d+', question)))


def _login(username: str) -> requests.Session:
    if not BASE_URL:
        pytest.skip('REACT_APP_BACKEND_URL missing')
    if not SEED_PASSWORD:
        pytest.skip('SEED_PASSWORD missing')
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    cap = session.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    auth = session.post(
        f"{API}/auth/login",
        json={
            'username': username,
            'password': SEED_PASSWORD,
            'captcha_id': cap.json()['id'],
            'captcha_answer': _solve(cap.json()['question']),
        },
        timeout=25,
    )
    assert auth.status_code == 200, f"login failed for {username}: {auth.status_code} {auth.text}"
    session.headers.update({'Authorization': f"Bearer {auth.json()['token']}"})
    return session


@pytest.fixture(scope='module')
def admin_project_session():
    return _login('adminproject')


@pytest.fixture(scope='module')
def cleanup_entities(admin_project_session):
    created_task_ids = []
    created_status_ids = []
    yield {'tasks': created_task_ids, 'statuses': created_status_ids}
    for task_id in created_task_ids:
        admin_project_session.delete(f"{API}/projects/{PROJECT_ID}/tasks/{task_id}", timeout=20)
    if created_status_ids:
        current = admin_project_session.get(f"{API}/projects/{PROJECT_ID}/statuses", timeout=20)
        if current.status_code == 200:
            for sid in created_status_ids:
                admin_project_session.delete(
                    f"{API}/projects/{PROJECT_ID}/statuses/{sid}?move_to=Belum%20Mulai",
                    timeout=20,
                )


# Module: kanban status columns
def test_create_reorder_status_and_verify_persist(admin_project_session, cleanup_entities):
    unique_name = f"TEST_REPRO_COL_{int(time.time())}"
    create = admin_project_session.post(
        f"{API}/projects/{PROJECT_ID}/statuses",
        json={'name': unique_name, 'color': '#a78bfa', 'kind': 'active'},
        timeout=25,
    )
    assert create.status_code == 200
    created_cols = create.json()
    new_col = next(c for c in created_cols if c['name'] == unique_name)
    cleanup_entities['statuses'].append(new_col['id'])
    assert new_col['kind'] == 'active'

    reordered_ids = [new_col['id']] + [c['id'] for c in created_cols if c['id'] != new_col['id']]
    reorder = admin_project_session.post(
        f"{API}/projects/{PROJECT_ID}/statuses/reorder",
        json={'ids': reordered_ids},
        timeout=25,
    )
    assert reorder.status_code == 200
    assert reorder.json()[0]['id'] == new_col['id']

    reload_cols = admin_project_session.get(f"{API}/projects/{PROJECT_ID}/statuses", timeout=20)
    assert reload_cols.status_code == 200
    assert reload_cols.json()[0]['id'] == new_col['id']


# Module: kanban task move persistence
def test_move_task_patch_and_verify_after_reload(admin_project_session, cleanup_entities):
    title = f"TEST_REPRO_TASK_MOVE_{int(time.time())}"
    created = admin_project_session.post(
        f"{API}/projects/{PROJECT_ID}/tasks",
        json={'title': title, 'status': 'Belum Mulai'},
        timeout=25,
    )
    assert created.status_code == 200
    task = created.json()
    cleanup_entities['tasks'].append(task['id'])
    assert task['status'] == 'Belum Mulai'

    moved = admin_project_session.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{task['id']}",
        json={'status': 'Dikerjakan', 'order': 1234.5},
        timeout=25,
    )
    assert moved.status_code == 200
    moved_body = moved.json()
    assert moved_body['status'] == 'Dikerjakan'
    assert float(moved_body['order']) == 1234.5

    fetched = admin_project_session.get(f"{API}/projects/{PROJECT_ID}/tasks", timeout=25)
    assert fetched.status_code == 200
    after_reload = next(t for t in fetched.json() if t['id'] == task['id'])
    assert after_reload['status'] == 'Dikerjakan'
    assert float(after_reload['order']) == 1234.5


# Module: kanban dependency completion guard
def test_move_to_done_with_unmet_dependency_returns_400(admin_project_session, cleanup_entities):
    blocker_title = f"TEST_REPRO_BLOCKER_{int(time.time())}"
    dependent_title = f"TEST_REPRO_DEP_{int(time.time())}"

    blocker = admin_project_session.post(
        f"{API}/projects/{PROJECT_ID}/tasks",
        json={'title': blocker_title, 'status': 'Belum Mulai'},
        timeout=25,
    )
    assert blocker.status_code == 200
    blocker_task = blocker.json()
    cleanup_entities['tasks'].append(blocker_task['id'])

    dependent = admin_project_session.post(
        f"{API}/projects/{PROJECT_ID}/tasks",
        json={'title': dependent_title, 'status': 'Dikerjakan', 'dependencies': [blocker_task['id']]},
        timeout=25,
    )
    assert dependent.status_code == 200
    dep_task = dependent.json()
    cleanup_entities['tasks'].append(dep_task['id'])
    assert blocker_task['id'] in dep_task.get('dependencies', [])

    denied = admin_project_session.patch(
        f"{API}/projects/{PROJECT_ID}/tasks/{dep_task['id']}",
        json={'status': 'Selesai'},
        timeout=25,
    )
    assert denied.status_code == 400
    assert 'prasyarat' in denied.text.lower()

    verify = admin_project_session.get(f"{API}/projects/{PROJECT_ID}/tasks", timeout=25)
    assert verify.status_code == 200
    persisted = next(t for t in verify.json() if t['id'] == dep_task['id'])
    assert persisted['status'] == 'Dikerjakan'