# Iter44: image_boxes (drag/resize) for kwitansi & invoice + WhatsApp report endpoint access
import os, subprocess, pytest, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0]
BASE_URL = BASE_URL.rstrip('/')
PID = 'project-8'


def token(user):
    return subprocess.check_output(['bash', '/app/tests/login_token.sh', user]).decode().strip()


@pytest.fixture(scope='module')
def admin():
    s = requests.Session(); t = token('admin')
    if len(t) < 20: pytest.skip(f'login failed: {t}')
    s.headers['Authorization'] = f'Bearer {t}'
    return s


@pytest.fixture(scope='module')
def created():
    return []


@pytest.fixture(scope='module', autouse=True)
def cleanup(admin, created):
    yield
    for kind, i in created:
        admin.delete(f'{BASE_URL}/api/projects/{PID}/{kind}/{i}')


def imgs(els):
    return {e['key']: e for e in els if e['t'] == 'img'}


# WhatsApp report
class TestWAReport:
    def test_admin_report(self, admin):
        r = admin.get(f'{BASE_URL}/api/admin/whatsapp-report?status=')
        assert r.status_code == 200, r.text
        d = r.json()
        assert 'messages' in d and isinstance(d['messages'], list)

    def test_developer_forbidden(self):
        t = token('developer')
        r = requests.get(f'{BASE_URL}/api/admin/whatsapp-report?status=', headers={'Authorization': f'Bearer {t}'})
        assert r.status_code in (401, 403)


@pytest.mark.parametrize('kind', ['receipts', 'invoices'])
class TestImageBoxes:
    def test_preview_applies_box(self, admin, kind):
        base = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/new').json()
        p0 = admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}/preview', json=base)
        assert p0.status_code == 200
        b0 = imgs(p0.json()['elements'])['brand']
        body = {**base, 'image_boxes': {'brand': {'dx': 1, 'dy': 0.5, 'dw': 0.8, 'dh': -0.2}}}
        p1 = admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}/preview', json=body)
        b1 = imgs(p1.json()['elements'])['brand']
        assert abs(b1['x'] - (b0['x'] + 1)) < 0.01
        assert abs(b1['y'] - (b0['y'] + 0.5)) < 0.01
        assert abs(b1['w'] - (b0['w'] + 0.8)) < 0.01
        assert abs(b1['h'] - (b0['h'] - 0.2)) < 0.01
        assert b1.get('stretch') is True

    def test_preview_clamps_out_of_page(self, admin, kind):
        base = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/new').json()
        body = {**base, 'image_boxes': {'brand': {'dx': -30, 'dy': -30, 'dw': 0, 'dh': 0}}}
        b = imgs(admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}/preview', json=body).json()['elements'])['brand']
        assert b['x'] >= 0 and b['y'] >= 0
        assert not b.get('stretch')

    def test_preview_garbage_box(self, admin, kind):
        base = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/new').json()
        body = {**base, 'image_boxes': {'brand': {'dx': 'abc'}, 'x': 5}}
        r = admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}/preview', json=body)
        assert r.status_code == 200

    def test_save_persists_and_pdf(self, admin, created, kind):
        base = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/new').json()
        if kind == 'receipts': base['received_from'] = 'TEST_iter44 client'
        else: base['to_name'] = 'TEST_iter44 client'
        base['number'] = ''
        base['image_boxes'] = {'brand': {'dx': 0.5, 'dy': 0.25, 'dw': 1, 'dh': 0.5}}
        r = admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}', json=base)
        assert r.status_code == 200, r.text
        d = r.json(); created.append((kind, d['id']))
        assert d['image_boxes']['brand']['dw'] == 1
        lst = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}').json()
        row = next(x for x in lst if x['id'] == d['id'])
        assert row['image_boxes']['brand'] == {'dx': 0.5, 'dy': 0.25, 'dw': 1, 'dh': 0.5}
        # update
        upd = {**{k: v for k, v in row.items() if k in base}, 'image_boxes': {'brand': {'dx': -1, 'dy': 0, 'dw': 0, 'dh': 0}}}
        u = admin.patch(f'{BASE_URL}/api/projects/{PID}/{kind}/{d["id"]}', json=upd)
        assert u.status_code == 200, u.text
        row = next(x for x in admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}').json() if x['id'] == d['id'])
        assert row['image_boxes']['brand']['dx'] == -1
        for fmt in ('pdf', 'docx'):
            f = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/{d["id"]}/{fmt}')
            assert f.status_code == 200 and len(f.content) > 1000

    def test_save_rejects_out_of_range(self, admin, kind):
        base = admin.get(f'{BASE_URL}/api/projects/{PID}/{kind}/new').json()
        if kind == 'receipts': base['received_from'] = 'TEST_iter44 bad'
        else: base['to_name'] = 'TEST_iter44 bad'
        base['image_boxes'] = {'brand': {'dx': 99}}
        r = admin.post(f'{BASE_URL}/api/projects/{PID}/{kind}', json=base)
        assert r.status_code == 422
