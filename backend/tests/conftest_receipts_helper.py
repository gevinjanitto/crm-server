# Shared login helper for receipt (Kwitansi) tests
import os, re, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    for line in open('/app/frontend/.env'):
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().rstrip('/')


def login(username='admin', password='Maiharta123!'):
    s = requests.Session()
    cap = s.get(f'{BASE_URL}/api/auth/captcha').json()
    a, b = map(int, re.findall(r'\d+', cap['question'])[:2])
    r = s.post(f'{BASE_URL}/api/auth/login', json={'username': username, 'password': password,
                                                   'captcha_id': cap['id'], 'captcha_answer': str(a + b)})
    r.raise_for_status()
    s.headers['Authorization'] = f"Bearer {r.json()['token']}"
    return s
