import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from docstore import MySQLClient
from fastapi import HTTPException

load_dotenv(Path(__file__).parent / '.env')
client = MySQLClient()
db = client.db
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
ROLES = ['Admin', 'Admin Project', 'Developer', 'Accounting', 'Client']
STATUSES = ['Project Masuk', 'Follow Up', 'Dokumen Disiapkan', 'Scope Dirinci', 'UI/UX', 'Disetujui', 'Development', 'Uploaded to Dev Server', 'Testing', 'Revisi', 'Uploaded to Production', 'Selesai']
TICKET_STATUSES = ['Baru', 'Ditinjau', 'Menunggu Klarifikasi', 'Diterima', 'Ditolak', 'Menunggu Estimasi Biaya', 'Menunggu Persetujuan', 'Dikerjakan', 'Selesai', 'Ditutup']
TASK_STATUSES = ['Belum Mulai', 'Dikerjakan', 'Testing', 'Revisi', 'Selesai']
SERVER_STAGES = ['Belum Naik', 'Dev Server', 'Production']
DEFAULT_CLIENT_PASSWORD = '12345678'
MAINTENANCE_STATUSES = ['Belum dikerjakan', 'Development', 'Testing', 'Selesai']
WORK_STATUSES = ['Terbuka', 'Dikerjakan', 'Selesai']
PLATFORMS = ['Web', 'Mobile Android', 'Mobile iOS', 'Desktop', 'UI/UX Design', 'Lainnya']
MANAGERS = ['Admin', 'Admin Project']
FINANCE = ['Admin', 'Accounting']
PERMISSIONS = {
    'task.read': ROLES, 'task.write': MANAGERS, 'task.progress': MANAGERS + ['Developer'],
    'costtype.read': FINANCE, 'costtype.write': FINANCE, 'expense.write': FINANCE,
    'project.read': ROLES, 'project.write': MANAGERS, 'project.status': MANAGERS + ['Developer'],
    'project.list': MANAGERS + ['Developer', 'Accounting'],
    'client.read': MANAGERS + ['Accounting'], 'client.write': MANAGERS,
    'user.manage': ['Admin'], 'team.read': MANAGERS,
    'feature.read': ROLES, 'feature.write': MANAGERS, 'feature.progress': MANAGERS + ['Developer'],
    'cost.read': FINANCE, 'cost.write': ['Admin'],
    'document.read': ROLES, 'document.write': MANAGERS,
    'revision.read': MANAGERS + ['Developer'], 'revision.write': MANAGERS,
    'maintenance.read': MANAGERS + ['Developer'], 'maintenance.write': MANAGERS,
    'deployment.read': MANAGERS + ['Developer'], 'deployment.write': MANAGERS + ['Developer'],
    'ticket.read': MANAGERS + ['Developer', 'Client'], 'ticket.create': ['Client'],
    'ticket.triage': MANAGERS, 'ticket.progress': MANAGERS + ['Developer', 'Client'],
    'dashboard.read': ROLES, 'history.read': ROLES,
    'audit.read': ['Admin'], 'trash.read': MANAGERS, 'trash.write': MANAGERS,
}
async def authorize(user, action, resource=None):
    allowed = user['role'] in PERMISSIONS.get(action, [])
    await db.audit_logs.insert_one({'id': uid(), 'user_id': user['id'], 'action': action, 'resource_id': (resource or {}).get('id'), 'allowed': allowed, 'created_at': now()})
    if not allowed: raise HTTPException(403, 'Anda tidak memiliki izin untuk tindakan ini.')

def project_scope(user):
    if user['role'] == 'Client': return {'client_id': user.get('client_id') or '__none__'}
    if user['role'] == 'Developer': return {'assigned_to': user['id']}
    return {}

async def project_for(user, project_id, action='project.read'):
    p = await db.projects.find_one({'$and': [project_scope(user), {'id': project_id}]}, {'_id': 0})
    if not p: raise HTTPException(404, 'Project tidak ditemukan.')
    await authorize(user, action, p)
    return p

def project_public(p, user):
    fields = ['id','code','name','description','client_id','client_name','category','platforms','type','status','progress','start_date','due_date','assigned_to','created_at','updated_at','production_at','tickets_closed']
    p = {**p, 'platforms': p.get('platforms') or [p.get('category', 'Web')]}
    if user['role'] in MANAGERS + ['Accounting']: fields += ['value']
    if user['role'] in FINANCE: fields += ['development_cost','server_cost','other_cost']
    if user['role'] in MANAGERS + ['Developer']: fields += ['internal_notes']
    return {k: p[k] for k in fields if k in p}

async def log_event(project_id, user, message, **extra):
    doc = {'id': uid(), 'project_id': project_id, 'user_name': user['name'], 'message': message, 'created_at': now(), **extra}
    await db.project_status_logs.insert_one(doc)

DEFAULT_TASK_STATUSES = [
    {'id': 'todo', 'name': 'Belum Mulai', 'color': '#87909e', 'kind': 'todo'},
    {'id': 'doing', 'name': 'Dikerjakan', 'color': '#3b82f6', 'kind': 'active'},
    {'id': 'testing', 'name': 'Testing', 'color': '#f59e0b', 'kind': 'active'},
    {'id': 'revisi', 'name': 'Revisi', 'color': '#ef4444', 'kind': 'active'},
    {'id': 'done', 'name': 'Selesai', 'color': '#10b981', 'kind': 'done'},
]
def project_statuses(p): return p.get('task_statuses') or [dict(s) for s in DEFAULT_TASK_STATUSES]

async def recalc_progress(pid):
    all_count = await db.project_features.count_documents({'project_id': pid})
    done = await db.project_features.count_documents({'project_id': pid, 'status': 'Selesai'})
    await db.projects.update_one({'id': pid}, {'$set': {'progress': round(done / all_count * 100) if all_count else 0}})

async def log_activity(user, action, entity_type, entity_id='', name='', project_id='', details=None):
    await db.activity_logs.insert_one({'id': uid(), 'user_id': user.get('id', ''), 'user_name': user.get('name', 'Sistem'), 'user_role': user.get('role', ''), 'action': action, 'entity_type': entity_type, 'entity_id': entity_id, 'name': name, 'project_id': project_id or '', 'details': details or {}, 'created_at': now()})

async def trash_item(user, collection, doc, entity_type, name, related=None):
    related = related or []
    await db.trash.insert_one({'id': uid(), 'collection': collection, 'entity_type': entity_type, 'entity_id': doc['id'], 'name': name, 'project_id': doc.get('project_id', doc['id'] if collection == 'projects' else ''), 'data': doc, 'related': related, 'deleted_by': user['id'], 'deleted_by_name': user['name'], 'deleted_at': now()})
    await db[collection].delete_one({'id': doc['id']})
    for r in related:
        if r['docs']: await db[r['collection']].delete_many({'id': {'$in': [d['id'] for d in r['docs']]}})
    await log_activity(user, 'hapus', entity_type, doc['id'], name, doc.get('project_id', ''), {'ke_arsip': True})

async def validate_assignee(user_id, project=None):
    if not user_id: return
    u = await db.users.find_one({'id': user_id, 'role': {'$in': MANAGERS + ['Developer']}, 'active': True}, {'_id': 0, 'id': 1, 'role': 1})
    if not u:
        raise HTTPException(400, 'PIC harus Admin, Admin Project, atau Developer aktif.')
    # Developer yang ditugaskan otomatis menjadi anggota project (1 task saja sudah memberi akses).
    if project and project.get('id') and u['role'] == 'Developer' and user_id not in project.get('assigned_to', []):
        await db.projects.update_one({'id': project['id']}, {'$addToSet': {'assigned_to': user_id}})
        project.setdefault('assigned_to', []).append(user_id)

async def task_developer_ids(pid):
    ids = set()
    async for t in db.tasks.find({'project_id': pid}, {'_id': 0, 'assigned_to': 1, 'assignee_ids': 1, 'subtasks.assigned_to': 1}):
        if t.get('assigned_to'): ids.add(t['assigned_to'])
        ids.update(i for i in (t.get('assignee_ids') or []) if i)
        ids.update(s.get('assigned_to') for s in (t.get('subtasks') or []) if s.get('assigned_to'))
    if not ids: return []
    return await db.users.distinct('id', {'id': {'$in': list(ids)}, 'role': 'Developer'})

async def sync_task_members(pid):
    """Pastikan setiap developer yang memiliki task di project ini menjadi anggota project."""
    ids = await task_developer_ids(pid)
    if ids: await db.projects.update_one({'id': pid}, {'$addToSet': {'assigned_to': {'$each': ids}}})
    return ids