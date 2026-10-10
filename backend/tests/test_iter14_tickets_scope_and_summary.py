"""Iteration 14: ticket scope, summary, and role-authorization regression tests."""

import os
import re
import uuid

import pytest
import requests
from dotenv import dotenv_values


ENV_FRONTEND = dotenv_values('/app/frontend/.env')
ENV_BACKEND = dotenv_values('/app/backend/.env')
BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or ENV_FRONTEND.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
API = f"{BASE_URL}/api"
SEED_PASSWORD = os.environ.get('SEED_PASSWORD') or ENV_BACKEND.get('SEED_PASSWORD', '')


def _solve(question: str) -> str:
    return str(sum(int(n) for n in re.findall(r'\d+', question)))


def _login(username: str) -> tuple[requests.Session, dict]:
    if not BASE_URL:
        pytest.skip('REACT_APP_BACKEND_URL missing')
    if not SEED_PASSWORD:
        pytest.skip('SEED_PASSWORD missing')
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    cap = session.get(f"{API}/auth/captcha", timeout=20)
    assert cap.status_code == 200
    cap_data = cap.json()
    auth = session.post(
        f"{API}/auth/login",
        json={
            'username': username,
            'password': SEED_PASSWORD,
            'captcha_id': cap_data['id'],
            'captcha_answer': _solve(cap_data['question']),
        },
        timeout=25,
    )
    assert auth.status_code == 200, f"login failed for {username}: {auth.status_code} {auth.text}"
    token = auth.json()['token']
    session.headers.update({'Authorization': f'Bearer {token}'})
    return session, auth.json()['user']


@pytest.fixture(scope='module')
def sessions():
    admin, admin_user = _login('admin')
    admin_project, ap_user = _login('adminproject')
    developer, developer_user = _login('developer')
    accounting, accounting_user = _login('accounting')
    client, client_user = _login('client')
    return {
        'admin': (admin, admin_user),
        'adminproject': (admin_project, ap_user),
        'developer': (developer, developer_user),
        'accounting': (accounting, accounting_user),
        'client': (client, client_user),
    }


# Auth + role gate for ticket endpoints
def test_anonymous_ticket_endpoints_401():
    anon = requests.Session()
    summary = anon.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert summary.status_code == 401
    listing = anon.get(f"{API}/projects/project-1/tickets", timeout=20)
    assert listing.status_code == 401


def test_accounting_blocked_from_ticket_endpoints(sessions):
    accounting_session, _ = sessions['accounting']
    summary = accounting_session.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert summary.status_code == 403
    listing = accounting_session.get(f"{API}/projects/project-1/tickets", timeout=20)
    assert listing.status_code == 403
    global_list = accounting_session.get(f"{API}/tickets", timeout=20)
    assert global_list.status_code == 403


# Project-scoped listing + summary shape/count checks
def test_project_ticket_summary_shape_and_counts(sessions):
    admin_session, _ = sessions['admin']
    rows = admin_session.get(f"{API}/projects/project-1/tickets", timeout=25)
    assert rows.status_code == 200
    tickets = rows.json()

    summary_resp = admin_session.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert set(summary.keys()) == {'total', 'new', 'active'}
    assert all(isinstance(summary[k], int) for k in ['total', 'new', 'active'])

    expected_total = len(tickets)
    expected_new = len([t for t in tickets if t.get('status') == 'Baru'])
    expected_active = len([t for t in tickets if t.get('status') not in ['Selesai', 'Ditutup', 'Ditolak']])

    assert summary['total'] == expected_total
    assert summary['new'] == expected_new
    assert summary['active'] == expected_active


def test_client_project_scope_enforced_404(sessions):
    client_session, _ = sessions['client']
    own = client_session.get(f"{API}/projects/project-1/tickets", timeout=20)
    assert own.status_code == 200
    foreign = client_session.get(f"{API}/projects/project-2/tickets", timeout=20)
    assert foreign.status_code == 404
    cross_create = client_session.post(
        f"{API}/tickets",
        json={
            'project_id': 'project-2',
            'title': f"TEST_cross_scope_{uuid.uuid4().hex[:6]}",
            'description': 'cross scope test ticket',
            'category': 'Bug / Problem',
            'priority': 'Sedang',
        },
        timeout=25,
    )
    assert cross_create.status_code == 404


def test_developer_only_assigned_tickets_and_no_estimate_field(sessions):
    developer_session, developer_user = sessions['developer']
    visible = developer_session.get(f"{API}/projects/project-1/tickets", timeout=20)
    assert visible.status_code == 200
    rows = visible.json()
    for row in rows:
        assert row.get('assigned_to') == developer_user['id']
        assert 'estimate' not in row

    blocked_project = developer_session.get(f"{API}/projects/project-7/tickets", timeout=20)
    assert blocked_project.status_code == 404


# Comment visibility and internal-comment restriction for client
def test_client_cannot_post_internal_and_cannot_see_internal_comments(sessions):
    client_session, _ = sessions['client']
    admin_session, _ = sessions['admin']

    created = client_session.post(
        f"{API}/tickets",
        json={
            'project_id': 'project-1',
            'title': f"TEST_internal_visibility_{uuid.uuid4().hex[:6]}",
            'description': 'ticket for internal visibility check',
            'category': 'Bug / Problem',
            'priority': 'Sedang',
        },
        timeout=25,
    )
    assert created.status_code == 200
    tid = created.json()['id']

    add_internal = admin_session.post(
        f"{API}/tickets/{tid}/comments",
        json={'message': 'TEST internal note', 'internal': True},
        timeout=20,
    )
    assert add_internal.status_code == 200

    client_try_internal = client_session.post(
        f"{API}/tickets/{tid}/comments",
        json={'message': 'try internal', 'internal': True},
        timeout=20,
    )
    assert client_try_internal.status_code == 403

    comments = client_session.get(f"{API}/tickets/{tid}/comments", timeout=20)
    assert comments.status_code == 200
    assert all(c.get('internal') is False for c in comments.json())


# Summary refresh behavior + closed-project create guard
def test_project_summary_updates_after_create_and_status_change(sessions):
    client_session, _ = sessions['client']
    admin_project_session, _ = sessions['adminproject']

    before = client_session.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert before.status_code == 200
    before_summary = before.json()

    created = client_session.post(
        f"{API}/tickets",
        json={
            'project_id': 'project-1',
            'title': f"TEST_summary_refresh_{uuid.uuid4().hex[:6]}",
            'description': 'validate project summary refresh counts',
            'category': 'Bug / Problem',
            'priority': 'Sedang',
        },
        timeout=25,
    )
    assert created.status_code == 200
    tid = created.json()['id']

    after_create = client_session.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert after_create.status_code == 200
    created_summary = after_create.json()
    assert created_summary['total'] == before_summary['total'] + 1
    assert created_summary['new'] == before_summary['new'] + 1

    # Admin Project performs allowed transition Baru -> Ditinjau
    moved = admin_project_session.patch(f"{API}/tickets/{tid}", json={'status': 'Ditinjau'}, timeout=25)
    assert moved.status_code == 200

    after_triage = client_session.get(f"{API}/projects/project-1/tickets/summary", timeout=20)
    assert after_triage.status_code == 200
    triaged_summary = after_triage.json()
    assert triaged_summary['new'] == created_summary['new'] - 1
    assert triaged_summary['total'] == created_summary['total']


def test_cannot_create_ticket_on_closed_project_if_any(sessions):
    client_session, _ = sessions['client']
    admin_session, _ = sessions['admin']
    projects = admin_session.get(f"{API}/projects", timeout=20)
    assert projects.status_code == 200
    rows = projects.json()
    closed = next((p for p in rows if p.get('tickets_closed')), None)
    if not closed:
        pytest.skip('No project with tickets_closed=true found in current seed')

    denied = client_session.post(
        f"{API}/tickets",
        json={
            'project_id': closed['id'],
            'title': f"TEST_closed_project_{uuid.uuid4().hex[:6]}",
            'description': 'ticket creation should be denied on closed project',
            'category': 'Bug / Problem',
            'priority': 'Sedang',
        },
        timeout=25,
    )
    assert denied.status_code == 400
