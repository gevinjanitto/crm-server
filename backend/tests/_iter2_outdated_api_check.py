# Iteration 2 helper: insert temporary old-body whatsapp_template row, check API outdated=true, then remove it
import os, sys, asyncio, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
from core import db

BASE = [l.split('=', 1)[1].strip() for l in open('/app/frontend/.env') if l.startswith('REACT_APP_BACKEND_URL=')][0]


def get():
    s = requests.Session()
    c = s.get(f'{BASE}/api/auth/captcha').json(); q = c['question'].split()
    t = s.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'Maiharta123!', 'captcha_id': c['id'], 'captcha_answer': str(int(q[0]) + int(q[2]))}).json()['token']
    return s.get(f'{BASE}/api/admin/whatsapp-template', headers={'Authorization': 'Bearer ' + t}).json()


async def main():
    assert await db.app_settings.find_one({'id': 'whatsapp_template'}) is None, 'row exists; abort'
    await db.app_settings.update_one({'id': 'whatsapp_template'}, {'$set': {'content_sid': 'HXTEST_OLD', 'name': 'TEST_old', 'status': 'pending',
                                     'category': 'MARKETING', 'body': '{{1}}\n\n{{2}}'}, '$setOnInsert': {'id': 'whatsapp_template'}}, upsert=True)
    try:
        d = await asyncio.to_thread(get)
        print('outdated', d['outdated'], 'category', d['category'], 'status', d['status'], 'body_new', d['body'].startswith('Halo {{1}}, ada'))
        if os.environ.get('HOLD'): await asyncio.sleep(int(os.environ['HOLD']))
    finally:
        await db.app_settings.delete_one({'id': 'whatsapp_template'})
        print('cleaned', await db.app_settings.find_one({'id': 'whatsapp_template'}) is None)

asyncio.run(main())
