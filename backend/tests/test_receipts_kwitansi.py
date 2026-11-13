# Kwitansi (receipt) feature: defaults, CRUD, calc, logo, DOCX/PDF, duplicate number, role access
import io, sys, subprocess, zipfile, pytest, requests
from datetime import date
from PIL import Image
sys.path.insert(0, '/app/backend/tests')
from conftest_receipts_helper import login, BASE_URL

PID = 'project-8'
API = f'{BASE_URL}/api/projects/{PID}/receipts'
CREATED = []


@pytest.fixture(scope='module')
def s():
    sess = login()
    yield sess
    for rid in CREATED:
        sess.delete(f'{API}/{rid}')


def _payload(**kw):
    p = {'number': '', 'date': date.today().isoformat(), 'received_from': 'TEST_PT Klien',
         'items': [{'description': 'TEST_Biaya Pengembangan', 'qty': 1, 'price': 22415100}],
         'ppn_enabled': True, 'ppn_rate': 11, 'pph_enabled': True, 'pph_rate': 2}
    p.update(kw); return p


def _png():
    b = io.BytesIO(); Image.new('RGB', (80, 40), (200, 30, 30)).save(b, 'PNG'); return b.getvalue()


# Defaults endpoint
def test_new_defaults(s):
    r = s.get(f'{API}/new'); assert r.status_code == 200
    d = r.json()
    today = date.today()
    assert d['number'].endswith(f'/INV/MH/{today.month:02d}/{today.year}')
    assert d['date'] == today.isoformat()
    assert d['received_from']
    assert len(d['items']) == 1 and d['items'][0]['qty'] == 1 and d['items'][0]['price'] == 16000000
    assert 'Svara' in d['items'][0]['description']


# Create + calc + persist
def test_create_calc_and_get(s):
    nxt = s.get(f'{API}/new').json()['number']
    r = s.post(API, json=_payload()); assert r.status_code == 200, r.text
    d = r.json(); CREATED.append(d['id'])
    assert d['number'] == nxt
    assert (d['subtotal'], d['ppn'], d['pph'], d['total']) == (22415100, 2465661, 457451, 25338212)
    assert d['terbilang'] == 'Dua Puluh Lima Juta Tiga Ratus Tiga Puluh Delapan Ribu Dua Ratus Dua Belas Rupiah'
    lst = s.get(API).json()
    assert any(x['id'] == d['id'] and x['total'] == 25338212 for x in lst)
    # sequence increments
    assert s.get(f'{API}/new').json()['number'] != nxt


# Duplicate number -> 409
def test_duplicate_number_409(s):
    r = s.post(API, json=_payload(number='001/INV/MH/11/2026')); assert r.status_code == 409


# Validation
@pytest.mark.parametrize('bad', [{'items': []}, {'items': [{'description': 'x', 'qty': 1, 'price': 1}] * 7},
                                 {'received_from': ''}, {'items': [{'description': 'x', 'qty': 0, 'price': 1}]}])
def test_validation_422(s, bad):
    assert s.post(API, json=_payload(**bad)).status_code == 422


# Update / taxes toggle
def test_patch_persists(s):
    d = s.post(API, json=_payload()).json(); CREATED.append(d['id'])
    body = _payload(number=d['number'], received_from='TEST_Updated', ppn_enabled=False, pph_enabled=False,
                    items=[{'description': 'A', 'qty': 2, 'price': 1000}, {'description': 'B', 'qty': 1.5, 'price': 333}])
    r = s.patch(f"{API}/{d['id']}", json=body); assert r.status_code == 200, r.text
    got = next(x for x in s.get(API).json() if x['id'] == d['id'])
    assert got['received_from'] == 'TEST_Updated' and got['total'] == 2000 + 500 and got['ppn'] == 0 and got['pph'] == 0
    assert got['number'] == d['number']


# Logo upload, get, docx/pdf, remove
def test_logo_docx_pdf_remove(s):
    d = s.post(API, json=_payload()).json(); CREATED.append(d['id'])
    h = {k: v for k, v in s.headers.items() if k != 'Content-Type'}
    r = requests.post(f"{API}/{d['id']}/logo", files={'file': ('l.png', _png(), 'image/png')}, headers=h)
    assert r.status_code == 200, r.text; assert r.json()['logo_path']
    assert s.get(f"{API}/{d['id']}/logo").headers['content-type'] == 'image/png'
    bad = requests.post(f"{API}/{d['id']}/logo", files={'file': ('x.png', b'notimage', 'image/png')}, headers=h)
    assert bad.status_code == 400
    dx = s.get(f"{API}/{d['id']}/docx"); assert dx.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(dx.content))
    xml = z.read('word/document.xml').decode()
    assert 'word/media/img_client.png' in z.namelist() and 'TEST_PT Klien' in xml and 'Rp 25.338.212,00' in xml
    assert 'attachment' in dx.headers['content-disposition']
    pdf = s.get(f"{API}/{d['id']}/pdf"); assert pdf.status_code == 200 and pdf.content[:4] == b'%PDF'
    r = s.patch(f"{API}/{d['id']}", json=_payload(number=d['number'], remove_logo=True)); assert r.status_code == 200
    assert r.json()['logo_path'] == ''
    assert s.get(f"{API}/{d['id']}/logo").status_code == 404
    assert 'word/media/img_client.png' not in zipfile.ZipFile(io.BytesIO(s.get(f"{API}/{d['id']}/docx").content)).namelist()
    assert s.get(f"{API}/{d['id']}/xls").status_code == 404


# Six items + long text renders
def test_six_items_render(s):
    items = [{'description': 'TEST_Item panjang sekali ' * 6, 'qty': i + 1, 'price': 1234567} for i in range(6)]
    d = s.post(API, json=_payload(items=items, received_from='TEST_' + 'Nama Instansi Sangat Panjang ' * 5)).json(); CREATED.append(d['id'])
    assert s.get(f"{API}/{d['id']}/pdf").status_code == 200
    assert s.get(f"{API}/{d['id']}/docx").status_code == 200


# Delete
def test_delete(s):
    d = s.post(API, json=_payload()).json()
    assert s.delete(f"{API}/{d['id']}").status_code == 200
    assert all(x['id'] != d['id'] for x in s.get(API).json())
    assert s.get(f"{API}/{d['id']}/pdf").status_code == 404


# Role access
@pytest.mark.parametrize('user,read,write', [('developer', {403, 404}, {403, 404}), ('client', {403, 404}, {403, 404}),
                                             ('accounting', {200}, {200})])
def test_roles(s, user, read, write):
    sid, tok = subprocess.check_output([sys.executable, '/app/backend/tests/_mint_role_token.py', user]).decode().split()
    try:
        h = {'Authorization': f'Bearer {tok}'}
        assert requests.get(API, headers=h).status_code in read
        assert requests.get(f'{API}/new', headers=h).status_code in read
        r = requests.post(API, json=_payload(), headers=h)
        assert r.status_code in write
        if r.status_code == 200: CREATED.append(r.json()['id'])
    finally:
        subprocess.call([sys.executable, '/app/backend/tests/_mint_role_token.py', 'del', sid])
