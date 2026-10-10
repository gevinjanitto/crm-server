"""Iteration 31: Reminders (project + report), in-app notify, cron, Inbox, welcome email template."""
import os, requests, pytest
from datetime import date, timedelta

def _read_env(path, key):
    try:
        for line in open(path):
            if line.startswith(key + '='):
                return line.split('=', 1)[1].strip().strip('"').rstrip('/')
    except FileNotFoundError: return ''
    return ''

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or _read_env('/app/frontend/.env', 'REACT_APP_BACKEND_URL')).rstrip('/')
API = BASE_URL + '/api'
CRON_SECRET = 'preview-cron-secret-9b8c7d6e5f4a3b2c1d0e'  # from backend/.env (preview)
PASSWORD = 'Maiharta2026!'
PID = 'project-1'


# ------- helpers -------

def _login(username):
    s = requests.Session(); s.headers.update({'Content-Type': 'application/json'})
    c = s.get(f'{API}/auth/captcha').json()
    parts = c['question'].split()
    a, b = int(parts[0]), int(parts[2])
    r = s.post(f'{API}/auth/login', json={'username': username, 'password': PASSWORD,
                                          'captcha_id': c['id'], 'captcha_answer': str(a + b)})
    assert r.status_code == 200, f'login {username}: {r.status_code} {r.text}'
    s.headers.update({'Authorization': f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope='module')
def admin(): return _login('admin')


@pytest.fixture(scope='module')
def dev(): return _login('developer')


def _cleanup(admin, created_ids):
    for rid in created_ids:
        admin.delete(f'{API}/projects/{PID}/reminders/{rid}')


# =========== Reminders CRUD ==========
class TestRemindersCRUD:
    created = []

    def test_01_create_valid(self, admin):
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=30)).isoformat()
        r = admin.post(f'{API}/projects/{PID}/reminders', json={
            'name': 'TEST_rem_normal', 'description': 'ket', 'start_date': start, 'end_date': end})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d['name'] == 'TEST_rem_normal'
        assert d['status'] == 'Berjalan'
        assert d['done'] is False
        assert d['notified_at'] is None, 'far-future reminder should NOT be notified'
        assert d['project_name']
        assert d['days_left'] == 30
        TestRemindersCRUD.created.append(d['id'])

    def test_02_create_within_14_days_notifies(self, admin):
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=5)).isoformat()
        r = admin.post(f'{API}/projects/{PID}/reminders', json={
            'name': 'TEST_rem_due', 'description': '', 'start_date': start, 'end_date': end})
        assert r.status_code == 200
        d = r.json()
        assert d['notified_at'] is not None, 'reminder within 14 days must set notified_at'
        TestRemindersCRUD.created.append(d['id'])

        # Admin should have an in-app notification "Reminder: TEST_rem_due"
        notes = admin.get(f'{API}/notifications').json()
        items = notes if isinstance(notes, list) else notes.get('items', [])
        assert any('TEST_rem_due' in (n.get('title') or '') for n in items), \
            f'in-app notification not found for admin: {items[:3]}'

    def test_03_validation_end_before_start(self, admin):
        r = admin.post(f'{API}/projects/{PID}/reminders', json={
            'name': 'bad', 'description': '', 'start_date': '2026-06-10', 'end_date': '2026-06-01'})
        assert r.status_code in (400, 422), r.text

    def test_04_non_admin_forbidden(self, dev):
        r = dev.get(f'{API}/projects/{PID}/reminders'); assert r.status_code == 403
        r = dev.get(f'{API}/reminders'); assert r.status_code == 403
        r = dev.post(f'{API}/projects/{PID}/reminders', json={
            'name': 'x', 'start_date': date.today().isoformat(), 'end_date': date.today().isoformat()})
        assert r.status_code == 403

    def test_05_project_list_only_not_done_sorted(self, admin):
        rows = admin.get(f'{API}/projects/{PID}/reminders').json()
        assert all(not x['done'] for x in rows)
        ends = [x['end_date'] for x in rows]
        assert ends == sorted(ends), 'project reminders not sorted by end_date asc'

    def test_06_all_reminders_includes_done_with_status(self, admin):
        rows = admin.get(f'{API}/reminders').json()
        assert any(x['status'] == 'Selesai' for x in rows), 'expected at least one Selesai (seed SSL)'
        assert any(x['status'] == 'Berjalan' for x in rows)
        for x in rows:
            assert 'days_left' in x and 'project_name' in x
        ends = [x['end_date'] for x in rows]
        assert ends == sorted(ends)

    def test_07_patch_end_date_resets_notified_at(self, admin):
        rid = TestRemindersCRUD.created[1]  # the due-soon one, has notified_at
        far = (date.today() + timedelta(days=90)).isoformat()
        r = admin.patch(f'{API}/projects/{PID}/reminders/{rid}', json={'end_date': far})
        assert r.status_code == 200, r.text
        assert r.json()['notified_at'] is None, 'changing end_date must reset notified_at'

    def test_08_done_never_auto_for_past_end(self, admin):
        # Create reminder with past end_date; done must stay False
        start = (date.today() - timedelta(days=30)).isoformat()
        end = (date.today() - timedelta(days=10)).isoformat()
        r = admin.post(f'{API}/projects/{PID}/reminders', json={
            'name': 'TEST_rem_past', 'start_date': start, 'end_date': end})
        assert r.status_code == 200
        d = r.json()
        assert d['done'] is False
        TestRemindersCRUD.created.append(d['id'])
        # trigger cron and re-read
        requests.post(f'{API}/cron/project-workspace',
                      headers={'Authorization': f'Bearer {CRON_SECRET}', 'x-webhook-id': 'rid-test-1'},
                      json={'event': 'schedule.triggered', 'schedule_id': 's', 'run_id': 'rid-test-1',
                            'dispatch_time': '2026-10-26T00:00:00Z'})
        import time; time.sleep(1.2)
        rows = admin.get(f'{API}/reminders').json()
        row = next(x for x in rows if x['id'] == d['id'])
        assert row['done'] is False, 'past end_date reminder was auto-marked done (BUG)'
        assert row['status'] == 'Berjalan'

    def test_09_patch_done_true(self, admin):
        rid = TestRemindersCRUD.created[0]
        r = admin.patch(f'{API}/projects/{PID}/reminders/{rid}', json={'done': True})
        assert r.status_code == 200
        assert r.json()['done'] is True
        assert r.json()['status'] == 'Selesai'
        # disappears from project list
        proj_rows = admin.get(f'{API}/projects/{PID}/reminders').json()
        assert not any(x['id'] == rid for x in proj_rows)
        # but still in report
        rep_rows = admin.get(f'{API}/reminders').json()
        assert any(x['id'] == rid and x['status'] == 'Selesai' for x in rep_rows)

    def test_99_cleanup(self, admin):
        _cleanup(admin, TestRemindersCRUD.created)


# ========== Cron endpoint ==========
class TestCron:
    def test_cron_requires_bearer(self):
        r = requests.post(f'{API}/cron/project-workspace', json={})
        assert r.status_code == 401

    def test_cron_wrong_secret(self):
        r = requests.post(f'{API}/cron/project-workspace',
                          headers={'Authorization': 'Bearer wrong'},
                          json={'event': 'schedule.triggered', 'schedule_id': 's', 'run_id': 'rid-wrong',
                                'dispatch_time': '2026-10-26T00:00:00Z'})
        assert r.status_code == 401

    def test_cron_ok(self):
        import uuid
        rid = f'rid-ok-{uuid.uuid4()}'
        r = requests.post(f'{API}/cron/project-workspace',
                          headers={'Authorization': f'Bearer {CRON_SECRET}', 'x-webhook-id': rid},
                          json={'event': 'schedule.triggered', 'schedule_id': 's', 'run_id': rid,
                                'dispatch_time': '2026-10-26T00:00:00Z'})
        assert r.status_code == 200, r.text
        assert r.json().get('accepted') is True


# ========== Inbox ==========
class TestInbox:
    def test_admin_sees_items(self, admin):
        r = admin.get(f'{API}/inbox')
        assert r.status_code == 200
        d = r.json()
        assert 'items' in d and 'unread' in d
        for it in d['items']:
            assert 'task_id' in it and 'comment_id' in it and 'project_name' in it
            # own comments excluded: admin's authored comments should not appear as latest.
            # we only check author_name differs from admin's full name heuristically.

    def test_developer_scoped(self, dev):
        r = dev.get(f'{API}/inbox')
        assert r.status_code == 200
        # developer must not get 403; may be empty list
        d = r.json(); assert isinstance(d.get('items'), list)

    def test_mark_read(self, admin):
        items = admin.get(f'{API}/inbox').json()['items']
        if not items: pytest.skip('no inbox items')
        tid = items[0]['task_id']
        r = admin.post(f'{API}/inbox/{tid}/read')
        assert r.status_code == 200


# ========== Welcome email template ==========
class TestWelcomeEmail:
    def test_sambutan_html_no_logo_no_credentials_plain_link(self):
        import sys; sys.path.insert(0, '/app/backend')
        from email_template import email_html, email_text
        note = {'kind': 'sambutan', 'title': 'Selamat bergabung, X',
                'message': 'Pesan selamat datang.', 'link': '/', 'created_at': '2026-10-26T00:00:00+00:00'}
        user = {'name': 'X'}
        html_out = email_html(note, user)
        text_out = email_text(note, user)
        # no <img> for sambutan
        assert '<img' not in html_out, 'welcome email must not include logo image'
        # no credentials words
        low = (html_out + ' ' + text_out).lower()
        for w in ['password', 'username', 'kata sandi']:
            assert w not in low, f"welcome email must not contain credential word: {w}"
        # plain link (no CTA button labelled Buka CRM Maiharta)
        assert 'Buka CRM Maiharta' not in html_out, 'welcome email should not have CTA button'
        assert 'Alamat CRM' in html_out
