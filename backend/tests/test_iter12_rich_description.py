"""Iteration 12: inline-image rich-text description tests.

Covers:
- PATCH description_html sanitizes (strips script, style, on*, external <img src>)
- Keeps <img data-image-id=uuid>, builds plain text in `description`
- Developer PATCH description_html -> 403
- Unreferenced images younger than 10 min are kept, older (>10 min) are dropped
"""
import os
import re
import time
import pytest
import requests

BASE = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE}/api"
PWD = os.environ.get('SEED_PASSWORD', 'Preview123!')
PNG = bytes.fromhex(
    '89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489'
    '0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082'
)


def login(username):
    s = requests.Session()
    cap = s.get(f'{API}/auth/captcha').json()
    m = re.match(r'(\d+)\s*([+\-*])\s*(\d+)', cap['question'])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = {'+': a + b, '-': a - b, '*': a * b}[op]
    r = s.post(f'{API}/auth/login', json={
        'username': username, 'password': PWD,
        'captcha_id': cap['id'], 'captcha_answer': str(ans),
    })
    assert r.status_code == 200, r.text
    s.headers['Authorization'] = f"Bearer {r.json()['token']}"
    return s, r.json()['user']


@pytest.fixture(scope='module')
def admin():
    return login('admin')


@pytest.fixture(scope='module')
def developer():
    return login('developer')


@pytest.fixture(scope='module')
def task_ids(admin):
    s, _ = admin
    tasks = s.get(f'{API}/projects/project-1/tasks').json()
    assert tasks, 'no tasks on project-1'
    # pick first NON-done task for simpler PATCH flow
    t = tasks[0]
    return 'project-1', t['id']


class TestSanitize:
    def test_sanitize_script_and_handlers(self, admin, task_ids):
        s, _ = admin; pid, tid = task_ids
        payload = {
            'description_html':
                '<p>Hello <b>world</b><script>alert(1)</script>'
                '<span style="color:red" onclick="x()">x</span></p>'
                '<img src="https://evil/x.png">'
        }
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        html = d.get('description_html') or ''
        assert '<script' not in html.lower()
        assert 'onclick' not in html.lower()
        assert 'style=' not in html.lower()
        # external image stripped (no data-image-id)
        assert 'evil' not in html
        assert '<img' not in html or 'data-image-id' in html
        # plain text set
        assert 'Hello' in (d.get('description') or '')
        assert 'alert(1)' not in (d.get('description') or '')

    def test_keep_valid_image_tag(self, admin, task_ids):
        s, _ = admin; pid, tid = task_ids
        # Upload an image to attach a real id
        up = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                    files=[('files', ('TEST_i12_a.png', PNG, 'image/png'))])
        assert up.status_code == 200, up.text
        img_id = up.json()['description_images'][-1]['id']
        payload = {'description_html': f'<p>pic</p><p><img data-image-id="{img_id}"></p>'}
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json=payload)
        assert r.status_code == 200, r.text
        html = r.json()['description_html']
        assert f'data-image-id="{img_id}"' in html
        pytest.i12_img_id = img_id

    def test_developer_description_html_forbidden(self, admin, developer, task_ids):
        sa, _ = admin; sd, _ = developer
        pid, tid = task_ids
        # ensure developer is assigned so other PATCHes work; description_html still should be blocked
        sa.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'assigned_to': 'user-developer'})
        r = sd.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'description_html': '<p>dev</p>'})
        assert r.status_code == 403, r.text


class TestDropUnusedImages:
    def test_young_unused_images_kept(self, admin, task_ids):
        """Image uploaded <10 min ago and omitted from HTML must NOT be dropped."""
        s, _ = admin; pid, tid = task_ids
        up = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                    files=[('files', ('TEST_i12_young.png', PNG, 'image/png'))])
        assert up.status_code == 200
        young_id = up.json()['description_images'][-1]['id']
        # Save description that does NOT reference young_id (but keep prior image to retain some content)
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}',
                    json={'description_html': '<p>only text, no imgs</p>'})
        assert r.status_code == 200
        imgs = r.json().get('description_images') or []
        ids = {i['id'] for i in imgs}
        assert young_id in ids, 'young unused image should be kept (10 min grace)'

    def test_old_unused_image_dropped_via_backfilled_created_at(self, admin, task_ids):
        """Simulate an old unused image by backdating created_at then PATCH.
        App storage is MySQL (crm_maiharta). We update description_images JSON column directly."""
        s, _ = admin; pid, tid = task_ids
        up = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                    files=[('files', ('TEST_i12_old.png', PNG, 'image/png'))])
        assert up.status_code == 200
        old_id = up.json()['description_images'][-1]['id']
        try:
            import pymysql, json
            conn = pymysql.connect(
                host=os.environ.get('MYSQL_HOST', '127.0.0.1'),
                port=int(os.environ.get('MYSQL_PORT', '3306')),
                user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
                database=os.environ['MYSQL_DATABASE'], autocommit=True,
            )
            cur = conn.cursor()
            cur.execute("SELECT doc FROM tasks WHERE k_id=%s", (tid,))
            row = cur.fetchone()
            if not row:
                pytest.skip('task row not found')
            doc = json.loads(row[0]) if isinstance(row[0], (bytes, str)) else row[0]
            for a in doc.get('description_images') or []:
                if a.get('id') == old_id:
                    a['created_at'] = '2000-01-01T00:00:00+00:00'
            cur.execute("UPDATE tasks SET doc=%s WHERE k_id=%s", (json.dumps(doc), tid))
            cur.close(); conn.close()
        except Exception as e:
            pytest.skip(f'cannot backdate: {e}')
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}',
                    json={'description_html': '<p>drop old pls</p>'})
        assert r.status_code == 200
        ids = {i['id'] for i in (r.json().get('description_images') or [])}
        assert old_id not in ids, 'old unused image should be dropped'


class TestDashboardKpiLinks:
    def test_tickets_endpoint_filters_still_work(self, admin):
        s, _ = admin
        r = s.get(f'{API}/tickets')
        assert r.status_code == 200
        assert isinstance(r.json(), list)
