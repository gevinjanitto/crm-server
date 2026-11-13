import asyncio, sys
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
from core import db, uid, now
from maintenance_details import create_details
async def main():
    u = await db.users.find_one({'username': 'admin'}, {'_id': 0})
    m = {'id': uid(), 'project_id': 'project-5', 'title': 'LEGACY3 Belum digabung', 'kind': 'Adaptive', 'priority': 'Mendesak', 'status': 'Belum dikerjakan', 'entry_date': '2026-06-01', 'created_at': now(), 'details_v2': True, 'description': ''}
    ids = await create_details('project-5', u, m, [{'title': 'Kondisi Saat ini', 'children': [{'title': 'cek'}]}, {'title': 'Penyesuaian'}])
    m['task_id'] = ids[0]
    await db.maintenances.insert_one(m)
    print(m['id'], ids)
asyncio.run(main())
