"""Iteration 13: image resize/align sanitation.

Validates that PATCH /api/projects/{pid}/tasks/{tid} with description_html:
- Keeps data-width (10-100 digits only) and data-align (left|center|right) on <img>
- Strips invalid data-width / data-align values and other img attrs (style/onerror/src/class)
- Preserves attrs on round trip (reload)
"""
import os, re, pytest, requests

BASE = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE}/api"
PWD = os.environ.get('SEED_PASSWORD', 'Preview123!')
PNG = bytes.fromhex(
    '89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489'
    '0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082'
)


def login(username='admin'):
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
    return s


@pytest.fixture(scope='module')
def ctx():
    s = login('admin')
    tasks = s.get(f'{API}/projects/project-1/tasks').json()
    tid = tasks[0]['id']
    up = s.post(f'{API}/projects/project-1/tasks/{tid}/images',
                files=[('files', ('TEST_i13.png', PNG, 'image/png'))])
    img_id = up.json()['description_images'][-1]['id']
    return s, 'project-1', tid, img_id


class TestImageLayout:
    def test_valid_width_align_kept(self, ctx):
        s, pid, tid, img_id = ctx
        html = (f'<p><img data-image-id="{img_id}" data-width="50" data-align="center">'
                f'<img data-image-id="{img_id}" data-width="100" data-align="right"></p>')
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'description_html': html})
        assert r.status_code == 200, r.text
        out = r.json()['description_html']
        assert 'data-width="50"' in out
        assert 'data-align="center"' in out
        assert 'data-width="100"' in out
        assert 'data-align="right"' in out
        # round-trip via GET list
        tasks = s.get(f'{API}/projects/{pid}/tasks').json()
        g = next(t for t in tasks if t['id'] == tid)
        assert 'data-width="50"' in g['description_html']
        assert 'data-align="center"' in g['description_html']

    def test_invalid_width_align_stripped(self, ctx):
        s, pid, tid, img_id = ctx
        html = (f'<p><img data-image-id="{img_id}" data-width="500" data-align="justify" '
                f'style="opacity:0.1" onerror="x()" src="https://evil/x.png" class="foo"></p>')
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'description_html': html})
        assert r.status_code == 200, r.text
        out = r.json()['description_html'].lower()
        assert 'data-width="500"' not in out
        assert 'data-width="5"' not in out  # avoid regex false match
        assert 'data-align="justify"' not in out
        assert 'style=' not in out
        assert 'onerror' not in out
        assert 'evil' not in out
        assert 'class=' not in out
        # img itself (identified by data-image-id) should still be there
        assert f'data-image-id="{img_id}"' in out

    def test_width_non_digit_stripped(self, ctx):
        s, pid, tid, img_id = ctx
        html = f'<p><img data-image-id="{img_id}" data-width="50px" data-align="LEFT"></p>'
        r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'description_html': html})
        assert r.status_code == 200
        out = r.json()['description_html']
        assert 'data-width=' not in out  # "50px" not digits only
        # case-sensitive match: "LEFT" is not in allowed set (left/center/right)
        assert 'data-align=' not in out
        assert f'data-image-id="{img_id}"' in out

    def test_edge_boundaries(self, ctx):
        s, pid, tid, img_id = ctx
        # 10 valid, 9 invalid, 100 valid, 101 invalid
        for w, keep in [('10', True), ('9', False), ('100', True), ('101', False)]:
            html = f'<p><img data-image-id="{img_id}" data-width="{w}" data-align="left"></p>'
            r = s.patch(f'{API}/projects/{pid}/tasks/{tid}', json={'description_html': html})
            assert r.status_code == 200
            out = r.json()['description_html']
            if keep:
                assert f'data-width="{w}"' in out, f'width {w} should be kept'
            else:
                assert f'data-width="{w}"' not in out, f'width {w} should be stripped'
