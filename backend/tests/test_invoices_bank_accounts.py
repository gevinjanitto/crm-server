# Invoice + bank-account master + kwitansi signature/scale features
import io, sys, zipfile, pytest, requests
from datetime import date
from PIL import Image
sys.path.insert(0, '/app/backend/tests')
from conftest_receipts_helper import login, BASE_URL

PID = 'project-8'
INV = f'{BASE_URL}/api/projects/{PID}/invoices'
REC = f'{BASE_URL}/api/projects/{PID}/receipts'
BANK = f'{BASE_URL}/api/bank-accounts'
CREATED = {'inv': [], 'rec': [], 'bank': []}


@pytest.fixture(scope='module')
def s():
    sess = login()
    yield sess
    for i in CREATED['inv']: sess.delete(f'{INV}/{i}')
    for i in CREATED['rec']: sess.delete(f'{REC}/{i}')
    for i in CREATED['bank']: sess.delete(f'{BANK}/{i}')


def _png(color=(200, 30, 30), size=(120, 40)):
    b = io.BytesIO(); Image.new('RGB', size, color).save(b, 'PNG'); return b.getvalue()


def _inv(**kw):
    p = {'number': '', 'date': date.today().isoformat(), 'to_name': 'TEST_PT Klien Invoice', 'to_title': 'TEST_Jabatan',
         'to_address': 'Jl. Test 1', 'items': [{'description': 'TEST_Item', 'qty': 2, 'price': 1000000}],
         'ppn_enabled': True, 'ppn_rate': 11, 'pph_enabled': True, 'pph_rate': 2,
         'bank_name': 'TEST_Bank', 'bank_branch': 'Cab', 'account_number': '123', 'account_holder': 'CV X'}
    p.update(kw); return p


# Bank master CRUD
def test_bank_crud(s):
    r = s.post(BANK, json={'bank_name': 'TEST_Bank Mandiri', 'branch': 'Denpasar', 'account_number': '999001', 'account_holder': 'CV MAI HARTA'})
    assert r.status_code == 200, r.text
    b = r.json(); CREATED['bank'].append(b['id'])
    assert b['bank_name'] == 'TEST_Bank Mandiri' and '_id' not in b
    lst = s.get(BANK).json()
    assert any(x['id'] == b['id'] for x in lst)
    r = s.patch(f"{BANK}/{b['id']}", json={'bank_name': 'TEST_Bank Mandiri 2', 'branch': '', 'account_number': '999002', 'account_holder': 'CV MAI HARTA'})
    assert r.status_code == 200 and r.json()['account_number'] == '999002'
    got = [x for x in s.get(BANK).json() if x['id'] == b['id']][0]
    assert got['bank_name'] == 'TEST_Bank Mandiri 2'
    assert s.delete(f"{BANK}/{b['id']}").status_code == 200
    CREATED['bank'].remove(b['id'])
    assert not any(x['id'] == b['id'] for x in s.get(BANK).json())
    assert s.delete(f"{BANK}/{b['id']}").status_code == 404


def test_bank_validation(s):
    r = s.post(BANK, json={'bank_name': '', 'account_number': '1', 'account_holder': 'x'})
    assert r.status_code == 422
    assert s.patch(f'{BANK}/nonexistent', json={'bank_name': 'a', 'account_number': '1', 'account_holder': 'x'}).status_code == 404


# Invoice defaults
def test_invoice_defaults(s):
    r = s.get(f'{INV}/new'); assert r.status_code == 200
    d = r.json(); t = date.today()
    assert d['number'].endswith(f'/INV/MH/{t.month:02d}/{t.year}')
    assert d['to_name'] and d['show_signature'] is False
    assert d['logo_scale'] == 100 and d['sign_scale'] == 100 and d['client_logo_scale'] == 100
    banks = s.get(BANK).json()
    if banks: assert d['bank_account_id'] and d['bank_name']


# Invoice CRUD + calc + duplicate
def test_invoice_crud(s):
    r = s.post(INV, json=_inv()); assert r.status_code == 200, r.text
    inv = r.json(); CREATED['inv'].append(inv['id'])
    assert inv['subtotal'] == 2000000 and inv['ppn'] == 220000
    assert inv['pph'] == round(2000000 * 2 / 98) and inv['total'] == inv['subtotal'] + inv['ppn'] + inv['pph']
    assert inv['show_signature'] is False
    lst = s.get(INV).json(); assert any(x['id'] == inv['id'] for x in lst)
    # duplicate number
    assert s.post(INV, json=_inv(number=inv['number'])).status_code == 409
    # update
    r = s.patch(f"{INV}/{inv['id']}", json=_inv(number=inv['number'], to_name='TEST_Updated', show_signature=True, sign_scale=150, logo_scale=80))
    assert r.status_code == 200, r.text
    got = [x for x in s.get(INV).json() if x['id'] == inv['id']][0]
    assert got['to_name'] == 'TEST_Updated' and got['show_signature'] is True and got['sign_scale'] == 150 and got['logo_scale'] == 80


def test_invoice_validation(s):
    assert s.post(INV, json=_inv(to_name='   ')).status_code in (400, 422)
    assert s.post(INV, json=_inv(items=[])).status_code == 422
    assert s.post(INV, json=_inv(sign_scale=300)).status_code == 422
    assert s.post(INV, json=_inv(logo_scale=10)).status_code == 422


# Invoice images + downloads
def test_invoice_images_and_downloads(s):
    inv = s.post(INV, json=_inv(show_signature=True)).json(); CREATED['inv'].append(inv['id'])
    r = s.post(f"{INV}/{inv['id']}/logo", files={'file': ('l.png', _png(), 'image/png')}); assert r.status_code == 200, r.text
    assert r.json()['logo_path']
    assert s.get(f"{INV}/{inv['id']}/logo").status_code == 200
    r = s.post(f"{INV}/{inv['id']}/signature", files={'file': ('t.png', _png((0, 0, 200)), 'image/png')}); assert r.status_code == 200
    assert s.get(f"{INV}/{inv['id']}/signature").status_code == 200
    bad = s.post(f"{INV}/{inv['id']}/logo", files={'file': ('x.png', b'notimage', 'image/png')}); assert bad.status_code == 400
    d = s.get(f"{INV}/{inv['id']}/docx"); assert d.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(d.content)); xml = z.read('word/document.xml').decode()
    assert 'INVOICE' in xml and 'TEST_PT Klien Invoice' in xml and 'TEST_Bank' in xml
    media = [n for n in z.namelist() if n.startswith('word/media/')]
    assert len(media) >= 3, media  # brand + client + sign
    p = s.get(f"{INV}/{inv['id']}/pdf"); assert p.status_code == 200 and p.content[:4] == b'%PDF'
    assert 'Invoice-' in p.headers.get('content-disposition', '')
    assert s.get(f"{INV}/{inv['id']}/xls").status_code == 404
    # remove logo
    r = s.patch(f"{INV}/{inv['id']}", json=_inv(number=inv['number'], show_signature=True, remove_logo=True))
    assert r.status_code == 200 and r.json()['logo_path'] == ''
    assert s.get(f"{INV}/{inv['id']}/logo").status_code == 404


# Signature off -> no sign image in docx
def test_invoice_no_signature_docx(s):
    inv = s.post(INV, json=_inv()).json(); CREATED['inv'].append(inv['id'])
    z = zipfile.ZipFile(io.BytesIO(s.get(f"{INV}/{inv['id']}/docx").content))
    media = [n for n in z.namelist() if n.startswith('word/media/')]
    inv2 = s.post(INV, json=_inv(show_signature=True)).json(); CREATED['inv'].append(inv2['id'])
    z2 = zipfile.ZipFile(io.BytesIO(s.get(f"{INV}/{inv2['id']}/docx").content))
    media2 = [n for n in z2.namelist() if n.startswith('word/media/')]
    assert len(media2) == len(media) + 1, (media, media2)


# Preview endpoints
def test_previews(s):
    r = s.post(f'{INV}/preview', json={**_inv(), 'has_logo': True, 'client_ratio': 2, 'show_signature': True, 'sign_ratio': 1.5})
    assert r.status_code == 200
    els = r.json()['elements']
    keys = {e.get('key') for e in els if e.get('t') == 'img'}
    assert {'brand', 'client', 'sign'} <= keys
    fields = {e.get('f') for e in els if e.get('f')}
    assert {'to_name', 'bank_name', 'signer_name', 'items.0.description'} <= fields
    r = s.post(f'{INV}/preview', json={'items': [{'qty': 'abc'}], 'date': 'bad', 'ppn_rate': 'x'})
    assert r.status_code == 200
    r = s.post(f'{REC}/preview', json={'received_from': 'TEST', 'items': [{'description': 'a', 'qty': 1, 'price': 10}], 'show_signature': False})
    assert r.status_code == 200
    assert not any(e.get('key') == 'sign' for e in r.json()['elements'] if e.get('t') == 'img')
    assert any(e.get('f') == 'received_from' for e in r.json()['elements'])


# Kwitansi new fields
def test_receipt_signature_fields(s):
    d = s.get(f'{REC}/new').json(); assert d['show_signature'] is False and d['sign_scale'] == 100
    body = {'number': '', 'date': date.today().isoformat(), 'received_from': 'TEST_Kw', 'items': [{'description': 'TEST_x', 'qty': 1, 'price': 500000}],
            'show_signature': True, 'sign_scale': 120}
    r = s.post(REC, json=body); assert r.status_code == 200, r.text
    rec = r.json(); CREATED['rec'].append(rec['id'])
    assert rec['show_signature'] is True and rec['sign_scale'] == 120
    assert s.post(f"{REC}/{rec['id']}/signature", files={'file': ('t.png', _png(), 'image/png')}).status_code == 200
    assert s.get(f"{REC}/{rec['id']}/pdf").content[:4] == b'%PDF'
    assert s.get(f"{REC}/{rec['id']}/docx").status_code == 200


# Permissions
@pytest.mark.parametrize('role', ['developer', 'client'])
def test_permissions(role):
    try: u = login(role)
    except Exception: pytest.skip(f'{role} login failed')
    assert u.get(BANK).status_code in (403, 404)
    assert u.post(BANK, json={'bank_name': 'TEST_x', 'account_number': '1', 'account_holder': 'x'}).status_code in (403, 404)
    assert u.get(INV).status_code in (403, 404)
    assert u.get(f'{INV}/new').status_code in (403, 404)


def test_accounting_access():
    u = login('accounting')
    assert u.get(BANK).status_code == 200
    assert u.get(INV).status_code == 200
