"""Tests for Glosarium (RBAC+CRUD+docs) and Project Maintenance status feature."""
import os, io, pytest, requests

BASE = os.environ.get('REACT_APP_BACKEND_URL', 'https://crm-glosarium.preview.emergentagent.com').rstrip('/') + '/api'
PWD = 'Maiharta2026!'


def login(username):
    c = requests.get(f'{BASE}/auth/captcha', timeout=15).json()
    a, b = c['question'].split()[0], c['question'].split()[2]
    r = requests.post(f'{BASE}/auth/login', json={
        'username': username, 'password': PWD,
        'captcha_id': c['id'], 'captcha_answer': str(int(a) + int(b))
    }, timeout=15)
    assert r.status_code == 200, f'login {username} failed: {r.status_code} {r.text}'
    return r.json()['token']


def h(tok):
    return {'Authorization': f'Bearer {tok}'}


@pytest.fixture(scope='module')
def tokens():
    return {u: login(u) for u in ['admin', 'adminproject', 'developer', 'client']}


# ------------------------- GLOSSARY RBAC -------------------------
class TestGlossaryRBAC:
    def test_admin_list(self, tokens):
        r = requests.get(f'{BASE}/glossary', headers=h(tokens['admin']))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_adminproject_list(self, tokens):
        r = requests.get(f'{BASE}/glossary', headers=h(tokens['adminproject']))
        assert r.status_code == 200

    def test_developer_list(self, tokens):
        r = requests.get(f'{BASE}/glossary', headers=h(tokens['developer']))
        assert r.status_code == 200

    def test_client_cannot_list(self, tokens):
        r = requests.get(f'{BASE}/glossary', headers=h(tokens['client']))
        assert r.status_code == 403, f'client should be forbidden, got {r.status_code}'

    def test_adminproject_cannot_create(self, tokens):
        r = requests.post(f'{BASE}/glossary', json={'title': 'TEST_RBAC', 'description': ''}, headers=h(tokens['adminproject']))
        assert r.status_code == 403

    def test_developer_cannot_create(self, tokens):
        r = requests.post(f'{BASE}/glossary', json={'title': 'TEST_RBAC', 'description': ''}, headers=h(tokens['developer']))
        assert r.status_code == 403


# ------------------------- GLOSSARY CRUD + DOCS -------------------------
class TestGlossaryCrudDocs:
    gid = None
    did = None

    def test_01_create(self, tokens):
        payload = {'title': 'TEST_Glossary_Entry', 'description': '<p>desc <script>alert(1)</script> safe</p>'}
        r = requests.post(f'{BASE}/glossary', json=payload, headers=h(tokens['admin']))
        assert r.status_code == 200, r.text
        g = r.json()
        assert g['title'] == 'TEST_Glossary_Entry'
        # Sanitation: script tag should be removed
        assert '<script>' not in g['description'].lower(), f'Script not sanitized: {g["description"]}'
        TestGlossaryCrudDocs.gid = g['id']

    def test_02_get(self, tokens):
        r = requests.get(f'{BASE}/glossary/{self.gid}', headers=h(tokens['admin']))
        assert r.status_code == 200
        assert r.json()['title'] == 'TEST_Glossary_Entry'

    def test_03_patch(self, tokens):
        r = requests.patch(f'{BASE}/glossary/{self.gid}',
                           json={'title': 'TEST_Glossary_Updated', 'description': '<p>updated</p>'},
                           headers=h(tokens['admin']))
        assert r.status_code == 200
        # GET to verify persistence
        g = requests.get(f'{BASE}/glossary/{self.gid}', headers=h(tokens['admin'])).json()
        assert g['title'] == 'TEST_Glossary_Updated'

    def test_04_upload_doc(self, tokens):
        files = [('files', ('spec.pdf', b'%PDF-1.4 test content', 'application/pdf')),
                 ('files', ('note.txt', b'hello world', 'text/plain'))]
        r = requests.post(f'{BASE}/glossary/{self.gid}/documents', files=files,
                          headers=h(tokens['admin']))
        assert r.status_code == 200, r.text
        docs = r.json()['documents']
        assert len(docs) >= 2
        TestGlossaryCrudDocs.did = docs[0]['id']

    def test_05_bad_extension(self, tokens):
        files = [('files', ('bad.exe', b'MZ', 'application/octet-stream'))]
        r = requests.post(f'{BASE}/glossary/{self.gid}/documents', files=files,
                          headers=h(tokens['admin']))
        assert r.status_code == 400

    def test_06_rename_doc(self, tokens):
        r = requests.patch(f'{BASE}/glossary/{self.gid}/documents/{self.did}',
                           data={'name': 'Renamed Spec'},
                           headers=h(tokens['admin']))
        assert r.status_code == 200, r.text
        d = next(x for x in r.json()['documents'] if x['id'] == self.did)
        assert d['name'] == 'Renamed Spec'

    def test_07_replace_doc(self, tokens):
        files = {'file': ('replace.pdf', b'%PDF-1.4 replaced', 'application/pdf')}
        r = requests.patch(f'{BASE}/glossary/{self.gid}/documents/{self.did}',
                           files=files, data={'name': ''},
                           headers=h(tokens['admin']))
        assert r.status_code == 200
        d = next(x for x in r.json()['documents'] if x['id'] == self.did)
        assert d['filename'] == 'replace.pdf'

    def test_08_download(self, tokens):
        r = requests.get(f'{BASE}/glossary/{self.gid}/documents/{self.did}/download',
                         headers=h(tokens['admin']))
        assert r.status_code == 200
        assert b'replaced' in r.content

    def test_09_developer_can_download(self, tokens):
        r = requests.get(f'{BASE}/glossary/{self.gid}/documents/{self.did}/download',
                         headers=h(tokens['developer']))
        assert r.status_code == 200

    def test_10_developer_cannot_upload(self, tokens):
        files = [('files', ('x.txt', b'hi', 'text/plain'))]
        r = requests.post(f'{BASE}/glossary/{self.gid}/documents', files=files,
                          headers=h(tokens['developer']))
        assert r.status_code == 403

    def test_11_delete_doc(self, tokens):
        r = requests.delete(f'{BASE}/glossary/{self.gid}/documents/{self.did}',
                            headers=h(tokens['admin']))
        assert r.status_code == 200
        g = requests.get(f'{BASE}/glossary/{self.gid}', headers=h(tokens['admin'])).json()
        assert not any(d['id'] == self.did for d in g['documents'])

    def test_12_client_cannot_patch_or_delete(self, tokens):
        r = requests.patch(f'{BASE}/glossary/{self.gid}', json={'title': 'x'}, headers=h(tokens['client']))
        assert r.status_code == 403
        r = requests.delete(f'{BASE}/glossary/{self.gid}', headers=h(tokens['client']))
        assert r.status_code == 403

    def test_99_delete_entry(self, tokens):
        r = requests.delete(f'{BASE}/glossary/{self.gid}', headers=h(tokens['admin']))
        assert r.status_code == 200
        r = requests.get(f'{BASE}/glossary/{self.gid}', headers=h(tokens['admin']))
        assert r.status_code == 404


# ------------------------- MAINTENANCE STATUS -------------------------
class TestMaintenanceStatus:
    """Project-5 (Loka — Company Profile) is Selesai with an open maintenance."""
    PID = 'project-5'

    def test_01_list_has_in_maintenance_flag(self, tokens):
        r = requests.get(f'{BASE}/projects', headers=h(tokens['admin']))
        assert r.status_code == 200
        rows = r.json()
        p = next((x for x in rows if x['id'] == self.PID), None)
        assert p is not None, 'project-5 missing'
        assert 'in_maintenance' in p, 'in_maintenance flag missing from list'
        assert p['in_maintenance'] is True, f'expected in_maintenance=True, got {p}'
        assert p.get('status') == 'Selesai'

    def test_02_detail_has_in_maintenance(self, tokens):
        r = requests.get(f'{BASE}/projects/{self.PID}', headers=h(tokens['admin']))
        assert r.status_code == 200
        p = r.json()
        assert p.get('in_maintenance') is True

    def test_03_close_maintenance_removes_flag(self, tokens):
        # Fetch maintenances for the project
        r = requests.get(f'{BASE}/projects/{self.PID}/work/maintenances', headers=h(tokens['admin']))
        assert r.status_code == 200, r.text
        ms = r.json()
        open_m = next((m for m in ms if m.get('status') != 'Selesai'), None)
        assert open_m is not None, 'expected an open maintenance on project-5'
        wid = open_m['id']
        original_status = open_m['status']

        # Close it
        r = requests.patch(f'{BASE}/projects/{self.PID}/work/maintenances/{wid}',
                           json={'status': 'Selesai'}, headers=h(tokens['admin']))
        assert r.status_code == 200, r.text

        # Verify project no longer in_maintenance
        p = requests.get(f'{BASE}/projects/{self.PID}', headers=h(tokens['admin'])).json()
        assert p.get('in_maintenance') is False, f'should clear after close: {p}'

        # Restore original status for next tests
        requests.patch(f'{BASE}/projects/{self.PID}/work/maintenances/{wid}',
                       json={'status': original_status}, headers=h(tokens['admin']))
        p = requests.get(f'{BASE}/projects/{self.PID}', headers=h(tokens['admin'])).json()
        assert p.get('in_maintenance') is True, 'should flip back on reopen'
