"""Iteration 6 backend tests: notifications, tickets rich body, attachments, project flows."""
import os, io, re, time, pytest, requests

BASE = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/') + '/api'
PW = 'MaiHarta!642a8bda'


def _login(username):
    c = requests.get(f'{BASE}/auth/captcha').json()
    a, b = [int(x) for x in c['question'].replace('= ?', '').split('+')]
    r = requests.post(f'{BASE}/auth/login', json={
        'username': username, 'password': PW,
        'captcha_id': c['id'], 'captcha_answer': str(a + b),
    })
    assert r.status_code == 200, f'login {username}: {r.status_code} {r.text}'
    return {'Authorization': 'Bearer ' + r.json()['token']}


@pytest.fixture(scope='module')
def tokens():
    return {r: _login(r) for r in ['admin', 'adminproject', 'developer', 'accounting', 'client']}


# --- captcha / login ---
def test_captcha_provider_math():
    c = requests.get(f'{BASE}/auth/captcha').json()
    assert c.get('provider') == 'math'
    assert 'id' in c and '+' in c['question'] and '= ?' in c['question']


def test_login_all_roles(tokens):
    for role in ['admin', 'adminproject', 'developer', 'accounting', 'client']:
        assert tokens[role]['Authorization'].startswith('Bearer ')


# --- client ticket creation with rich text sanitization ---
@pytest.fixture(scope='module')
def client_project_id(tokens):
    ps = requests.get(f'{BASE}/projects', headers=tokens['client']).json()
    assert ps, 'client should see at least one project'
    return ps[0]['id']


@pytest.fixture(scope='module')
def created_ticket(tokens, client_project_id):
    payload = {
        'project_id': client_project_id,
        'title': 'TEST_iter6 rich ticket',
        'description': 'placeholder',
        'description_html': '<p>Halo <b>tebal</b><script>alert(1)</script> '
                            '<a href="javascript:evil()">jsx</a> '
                            '<a href="https://example.com">ok</a></p><ul><li>satu</li></ul>',
        'cc_emails': ['cc1@example.com', 'cc2@example.com'],
        'priority': 'Tinggi',
    }
    r = requests.post(f'{BASE}/tickets', headers=tokens['client'], json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_ticket_sanitizes_html(created_ticket):
    h = created_ticket['description_html']
    assert '<script' not in h.lower()
    assert 'javascript:' not in h.lower()
    assert '<b>tebal</b>' in h
    # javascript href should be replaced with '#'
    assert re.search(r'href="#"', h)
    # https href preserved
    assert 'https://example.com' in h
    assert created_ticket['cc_emails'] == ['cc1@example.com', 'cc2@example.com']
    assert created_ticket['attachments'] == []


def test_invalid_cc_email_422(tokens, client_project_id):
    r = requests.post(f'{BASE}/tickets', headers=tokens['client'], json={
        'project_id': client_project_id, 'title': 'bad cc', 'description': 'xxxxx',
        'description_html': '<p>xxxxx</p>', 'cc_emails': ['not-an-email'], 'priority': 'Rendah',
    })
    assert r.status_code == 422, r.text


# --- attachments ---
def _png_bytes():
    return b'\x89PNG\r\n\x1a\n' + b'0' * 200


def test_upload_attachments_client(tokens, created_ticket):
    tid = created_ticket['id']
    files = [
        ('files', ('note.txt', b'hello world', 'text/plain')),
        ('files', ('image.png', _png_bytes(), 'image/png')),
    ]
    r = requests.post(f'{BASE}/tickets/{tid}/attachments', headers=tokens['client'], files=files)
    assert r.status_code == 200, r.text
    atts = r.json()['attachments']
    assert len(atts) == 2
    # storage_path must not be exposed
    assert all('storage_path' not in a for a in atts)


def test_upload_bad_extension(tokens, created_ticket):
    tid = created_ticket['id']
    r = requests.post(f'{BASE}/tickets/{tid}/attachments', headers=tokens['client'],
                      files=[('files', ('bad.exe', b'MZ', 'application/octet-stream'))])
    assert r.status_code == 400


def test_upload_over_limit(tokens, created_ticket):
    tid = created_ticket['id']
    # already 2 uploaded, add 4 more -> total 6 > 5
    files = [('files', (f'x{i}.txt', b'x', 'text/plain')) for i in range(4)]
    r = requests.post(f'{BASE}/tickets/{tid}/attachments', headers=tokens['client'], files=files)
    assert r.status_code == 400


def test_developer_cannot_upload(tokens, created_ticket):
    tid = created_ticket['id']
    r = requests.post(f'{BASE}/tickets/{tid}/attachments', headers=tokens['developer'],
                      files=[('files', ('a.txt', b'x', 'text/plain'))])
    # Developer may not even see the ticket -> 404 acceptable, or 403 by role check
    assert r.status_code in (403, 404)


def test_download_attachment_admin(tokens, created_ticket):
    tid = created_ticket['id']
    # refetch to get aid
    t = requests.get(f'{BASE}/tickets/{tid}', headers=tokens['admin']).json()
    aid = t['attachments'][0]['id']
    r = requests.get(f'{BASE}/tickets/{tid}/attachments/{aid}/download', headers=tokens['admin'])
    assert r.status_code == 200
    assert r.content == b'hello world'


# --- notifications ---
def test_notifications_after_client_create(tokens, created_ticket):
    time.sleep(0.3)
    for role in ['admin', 'adminproject']:
        n = requests.get(f'{BASE}/notifications', headers=tokens[role]).json()
        assert any(x.get('kind') == 'tiket' and 'Tiket baru' in x.get('title', '')
                   and created_ticket['code'] in x.get('title', '') for x in n['items']), \
            f'{role} missing ticket notif'
    # Client (actor) should NOT get notif for own creation of this ticket
    nc = requests.get(f'{BASE}/notifications', headers=tokens['client']).json()
    assert not any(created_ticket['code'] in x.get('title', '') and 'Tiket baru' in x.get('title', '')
                   for x in nc['items'])


def test_patch_ticket_notifies_client_and_developer(tokens, created_ticket):
    tid = created_ticket['id']
    r = requests.patch(f'{BASE}/tickets/{tid}', headers=tokens['admin'],
                       json={'status': 'Ditinjau', 'assigned_to': 'user-developer'})
    assert r.status_code == 200, r.text
    time.sleep(0.3)
    nc = requests.get(f'{BASE}/notifications', headers=tokens['client']).json()
    assert any(created_ticket['code'] in x['title'] and 'diperbarui' in x['title'].lower()
               for x in nc['items']), 'client missing update notif'
    nd = requests.get(f'{BASE}/notifications', headers=tokens['developer']).json()
    # developer gets assignment + update
    assert any('Penugasan tiket' in x['title'] for x in nd['items']), 'dev missing assignment notif'


def test_comment_notifies_client(tokens, created_ticket):
    tid = created_ticket['id']
    before = requests.get(f'{BASE}/notifications/unread-count', headers=tokens['client']).json()['unread']
    r = requests.post(f'{BASE}/tickets/{tid}/comments', headers=tokens['admin'],
                      json={'message': 'TEST_iter6 komentar cek', 'internal': False})
    assert r.status_code == 200
    time.sleep(0.3)
    after = requests.get(f'{BASE}/notifications/unread-count', headers=tokens['client']).json()['unread']
    assert after >= before + 1


def test_read_and_read_all_and_delete(tokens):
    n = requests.get(f'{BASE}/notifications', headers=tokens['client']).json()
    assert n['items']
    first = n['items'][0]['id']
    r = requests.post(f'{BASE}/notifications/{first}/read', headers=tokens['client'])
    assert r.status_code == 200
    r = requests.post(f'{BASE}/notifications/read-all', headers=tokens['client'])
    assert r.status_code == 200
    uc = requests.get(f'{BASE}/notifications/unread-count', headers=tokens['client']).json()
    assert uc['unread'] == 0
    # delete other's notif -> 404
    admin_n = requests.get(f'{BASE}/notifications', headers=tokens['admin']).json()['items']
    if admin_n:
        r = requests.delete(f'{BASE}/notifications/{admin_n[0]["id"]}', headers=tokens['client'])
        assert r.status_code == 404
    # delete own notif -> 200
    own = requests.get(f'{BASE}/notifications', headers=tokens['client']).json()['items']
    if own:
        r = requests.delete(f'{BASE}/notifications/{own[0]["id"]}', headers=tokens['client'])
        assert r.status_code == 200


# --- project flow notifications ---
def test_project_add_developer_notifies(tokens):
    # Use project-6 (Scope Dirinci, client-1)
    pid = 'project-6'
    p = requests.get(f'{BASE}/projects/{pid}', headers=tokens['admin']).json()
    fields = ['name', 'client_id', 'platforms', 'start_date', 'due_date', 'description', 'assigned_to']
    base_body = {k: p.get(k) for k in fields if p.get(k) is not None}
    assigned = list(p.get('assigned_to') or [])
    if 'user-developer' in assigned:
        new_assigned = [x for x in assigned if x != 'user-developer']
        requests.patch(f'{BASE}/projects/{pid}', headers=tokens['admin'],
                       json={**base_body, 'assigned_to': new_assigned})
        time.sleep(0.2)
    before = requests.get(f'{BASE}/notifications', headers=tokens['developer']).json()
    before_ids = {x['id'] for x in before['items']}
    r = requests.patch(f'{BASE}/projects/{pid}', headers=tokens['admin'],
                       json={**base_body, 'assigned_to': list({*assigned, 'user-developer'})})
    assert r.status_code == 200, r.text
    time.sleep(0.3)
    after = requests.get(f'{BASE}/notifications', headers=tokens['developer']).json()
    new_items = [x for x in after['items'] if x['id'] not in before_ids]
    assert any('ditambahkan' in x['title'].lower() or 'project' in x['title'].lower()
               for x in new_items), f'no project add notif: {[x["title"] for x in new_items[:5]]}'


def test_email_logs_admin_only(tokens):
    r = requests.get(f'{BASE}/notifications/email-logs', headers=tokens['admin'])
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = requests.get(f'{BASE}/notifications/email-logs', headers=tokens['adminproject'])
    assert r.status_code == 403
    r = requests.get(f'{BASE}/notifications/email-logs', headers=tokens['client'])
    assert r.status_code == 403


# --- regression ---
def test_regression_endpoints(tokens):
    for role in ['admin', 'adminproject', 'developer', 'client']:
        r = requests.get(f'{BASE}/projects', headers=tokens[role])
        assert r.status_code == 200
        r = requests.get(f'{BASE}/tickets', headers=tokens[role])
        assert r.status_code == 200
    r = requests.get(f'{BASE}/dashboard', headers=tokens['admin'])
    assert r.status_code == 200
    r = requests.get(f'{BASE}/reports/projects.xlsx', headers=tokens['admin'])
    assert r.status_code == 200
    assert 'spreadsheet' in r.headers.get('content-type', '') or r.headers.get('content-type', '').startswith('application')
