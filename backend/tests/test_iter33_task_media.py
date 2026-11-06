"""Backend tests for subtask description + task image + comment attachments (iteration 33)."""
import io
import os
import re
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
PWD = 'Maiharta2026!'

# tiny valid PNG (1x1 transparent)
PNG_1x1 = bytes.fromhex(
    '89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489'
    '0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082'
)


def login(username):
    s = requests.Session()
    cap = s.get(f'{API}/auth/captcha').json()
    assert cap['provider'] == 'math', cap
    m = re.match(r'(\d+)\s*\+\s*(\d+)', cap['question'])
    ans = str(int(m.group(1)) + int(m.group(2)))
    r = s.post(f'{API}/auth/login', json={'username': username, 'password': PWD,
                                           'captcha_id': cap['id'], 'captcha_answer': ans})
    assert r.status_code == 200, (username, r.status_code, r.text)
    s.headers['Authorization'] = f"Bearer {r.json()['token']}"
    return s, r.json()['user']


@pytest.fixture(scope='module')
def admin():
    s, u = login('admin'); return s, u

@pytest.fixture(scope='module')
def developer():
    s, u = login('developer'); return s, u

@pytest.fixture(scope='module')
def client_user():
    s, u = login('client'); return s, u


@pytest.fixture(scope='module')
def task(admin):
    s, _ = admin
    # find a project-1 task
    tasks = s.get(f'{API}/projects/project-1/tasks').json()
    assert isinstance(tasks, list) and tasks, tasks
    return 'project-1', tasks[0]['id'], tasks[0]


# ---------- Subtask description ----------
class TestSubtaskDescription:
    def test_create_subtask_with_description(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/subtasks',
                   json={'title': 'TEST_subtask desc', 'description': 'deskripsi awal'})
        assert r.status_code == 200, r.text
        subs = r.json().get('subtasks', [])
        new = next((x for x in subs if x['title'] == 'TEST_subtask desc'), None)
        assert new and new['description'] == 'deskripsi awal'
        pytest.subtask_id = new['id']

    def test_patch_subtask_description(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        sid = pytest.subtask_id
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}/subtasks/{sid}',
                    json={'description': 'deskripsi diperbarui'})
        assert r.status_code == 200, r.text
        subs = r.json()['subtasks']
        found = next(x for x in subs if x['id'] == sid)
        assert found['description'] == 'deskripsi diperbarui'

    def test_description_persists_on_reload(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        tasks = s.get(f'{API}/projects/{pid}/tasks').json()
        t = next(x for x in tasks if x['id'] == tid)
        sub = next(x for x in t['subtasks'] if x['id'] == pytest.subtask_id)
        assert sub['description'] == 'deskripsi diperbarui'

    def test_description_max_length(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/subtasks',
                   json={'title': 'TEST_long', 'description': 'x' * 3001})
        assert r.status_code == 422

    def test_developer_can_edit_subtask(self, developer, admin, task):
        sd, _ = developer; sa, _ = admin
        pid, tid, _ = task
        # admin needs to assign developer to task first
        sa.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'assigned_to': 'user-developer'})
        r = sd.patch(f'{API}/projects/{pid}/tasks/{tid}/subtasks/{pytest.subtask_id}',
                     json={'description': 'dev edit'})
        assert r.status_code == 200, r.text

    def test_cleanup_subtask(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.delete(f'{API}/projects/{pid}/tasks/{tid}/subtasks/{pytest.subtask_id}')
        assert r.status_code == 200


# ---------- Task images ----------
class TestTaskImages:
    def test_upload_image_as_admin(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                   files=[('files', ('TEST_a.png', PNG_1x1, 'image/png'))])
        assert r.status_code == 200, r.text
        imgs = r.json().get('description_images', [])
        assert len(imgs) >= 1
        img = imgs[-1]
        # storage_path must be stripped
        assert 'storage_path' not in img
        assert img['name'] == 'TEST_a.png'
        pytest.image_id = img['id']

    def test_get_image(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.get(f'{API}/projects/{pid}/tasks/{tid}/images/{pytest.image_id}')
        assert r.status_code == 200
        assert r.headers.get('content-type', '').startswith('image/')
        assert r.content[:8] == PNG_1x1[:8]

    def test_developer_cannot_upload(self, developer, task):
        s, _ = developer; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                   files=[('files', ('TEST_b.png', PNG_1x1, 'image/png'))])
        assert r.status_code == 403, r.text

    def test_non_image_rejected(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/images',
                   files=[('files', ('TEST_x.pdf', b'%PDF-1.4 test', 'application/pdf'))])
        assert r.status_code == 400

    def test_delete_image(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.delete(f'{API}/projects/{pid}/tasks/{tid}/images/{pytest.image_id}')
        assert r.status_code == 200, r.text
        imgs = r.json().get('description_images', [])
        assert not any(x['id'] == pytest.image_id for x in imgs)


# ---------- Comment attachments ----------
class TestCommentAttachments:
    def test_text_only_comment(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments',
                   json={'message': 'TEST_text only'})
        assert r.status_code == 200, r.text
        pytest.text_cid = r.json()['id']

    def test_upload_comment_with_image(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments/upload',
                   data={'message': 'TEST_with image', 'assigned_to': ''},
                   files=[('files', ('TEST_c.png', PNG_1x1, 'image/png'))])
        assert r.status_code == 200, r.text
        c = r.json()
        atts = c.get('attachments', [])
        assert len(atts) == 1
        assert 'storage_path' not in atts[0]
        assert atts[0]['is_image']
        pytest.img_cid = c['id']
        pytest.img_aid = atts[0]['id']

    def test_upload_comment_with_doc(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments/upload',
                   data={'message': '', 'assigned_to': ''},
                   files=[('files', ('TEST_d.pdf', b'%PDF-1.4 fakepdf', 'application/pdf'))])
        assert r.status_code == 200, r.text
        atts = r.json()['attachments']
        assert atts and not atts[0]['is_image']
        pytest.doc_cid = r.json()['id']
        pytest.doc_aid = atts[0]['id']

    def test_invalid_extension_rejected(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments/upload',
                   data={'message': '', 'assigned_to': ''},
                   files=[('files', ('TEST_bad.exe', b'MZ...', 'application/octet-stream'))])
        assert r.status_code == 400

    def test_too_many_files_rejected(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        files = [('files', (f'TEST_m{i}.png', PNG_1x1, 'image/png')) for i in range(6)]
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments/upload',
                   data={'message': '', 'assigned_to': ''}, files=files)
        assert r.status_code == 400

    def test_get_comments_hides_storage_path(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        rows = s.get(f'{API}/projects/{pid}/tasks/{tid}/comments').json()
        for c in rows:
            for a in c.get('attachments') or []:
                assert 'storage_path' not in a

    def test_download_comment_attachment(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        r = s.get(f'{API}/projects/{pid}/tasks/{tid}/comments/{pytest.img_cid}/attachments/{pytest.img_aid}')
        assert r.status_code == 200
        assert r.headers.get('content-type', '').startswith('image/')

    def test_client_can_send_attachment_on_own_project(self, client_user, task):
        s, _ = client_user
        pid = 'project-1'  # Nusantara Living (client-1) seeded project
        tasks = s.get(f'{API}/projects/{pid}/tasks').json()
        if not tasks:
            pytest.skip('no tasks on client project')
        tid = tasks[0]['id']
        r = s.post(f'{API}/projects/{pid}/tasks/{tid}/comments/upload',
                   data={'message': 'TEST_client attach', 'assigned_to': ''},
                   files=[('files', ('TEST_cl.png', PNG_1x1, 'image/png'))])
        assert r.status_code == 200, r.text

    def test_delete_comment_cleans_up(self, admin, task):
        s, _ = admin; pid, tid, _ = task
        for cid in [pytest.text_cid, pytest.img_cid, pytest.doc_cid]:
            r = s.delete(f'{API}/projects/{pid}/tasks/{tid}/comments/{cid}')
            assert r.status_code == 200
