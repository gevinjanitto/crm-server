import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from core import db, client, sync_task_members
from auth import router as auth_router
from projects import router as projects_router
from administration import router as admin_router
from tickets import router as tickets_router
from kanban import router as kanban_router
from finance import router as finance_router
from audit import router as audit_router
from notify import router as notify_router
from task_workspace import router as task_workspace_router
from workspace_structure import router as structure_router
from workspace_collab import router as collab_router
from workspace_planning import router as planning_router
from workspace_automation import router as automation_router
from workspace_scheduler import router as schedule_router
from seed import seed, seed_cost_types, backfill_tasks, migrate
from account_notifications import router as account_notifications_router
from reminders import router as reminders_router
from inbox import router as inbox_router
from task_media import router as task_media_router
from notification_controls import router as notification_controls_router

@asynccontextmanager
async def lifespan(app):
    for attempt in range(30):  # tunggu MySQL siap saat container/pod baru menyala
        try:
            await db.users.create_index('username', unique=True); break
        except Exception:
            if attempt == 29: raise
            logging.warning('MySQL belum siap, mencoba lagi...'); await asyncio.sleep(2)
    await db.users.create_index('id', unique=True)
    await db.projects.create_index('id', unique=True)
    await db.captchas.create_index('expires_at', expireAfterSeconds=0)
    await db.sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.login_attempts.create_index('created_at', expireAfterSeconds=600)
    await db.tasks.create_index('project_id')
    await db.tickets.create_index([('project_id', 1), ('assigned_to', 1), ('status', 1)])
    await db.task_views.create_index([('project_id', 1), ('user_id', 1)])
    await db.tasks.create_index('id', unique=True)
    for collection in ['workspace_nodes', 'workspace_fields', 'task_templates', 'workspace_docs', 'doc_versions', 'workspace_goals', 'workspace_rules', 'automation_logs', 'workspace_capacity', 'task_schedules']:
        await db[collection].create_index('project_id')
    await db.workspace_boards.create_index('project_id', unique=True)
    await db.workspace_sprints.create_index('project_id', unique=True, partialFilterExpression={'status': 'active'})
    for collection in ['task_schedules', 'workspace_capacity', 'cron_runs', 'scheduler_locks', 'scheduler_events']:
        await db[collection].create_index('id', unique=True)
    await db.activity_logs.create_index('created_at')
    await db.trash.create_index('deleted_at')
    await db.notifications.create_index([('user_id', 1), ('read', 1), ('created_at', -1)])
    await db.notification_deliveries.create_index([('user_id', 1), ('created_at', -1)])
    await db.notification_deliveries.create_index('provider_id', sparse=True)
    await db.workspace_nodes.create_index('id', unique=True)
    await db.project_reminders.create_index('id', unique=True)
    await db.project_reminders.create_index('project_id')
    await db.inbox_reads.create_index('id', unique=True)
    await seed()
    await seed_cost_types()
    await backfill_tasks()
    await migrate()
    for pid in await db.projects.distinct('id'):
        await sync_task_members(pid)
    yield
    client.close()

app = FastAPI(title='CRM Maiharta', lifespan=lifespan)
api = APIRouter(prefix='/api')
@api.get('/')
async def root(): return {'name': 'CRM Maiharta', 'status': 'ok'}
@api.get('/health')
async def health(): return {'status': 'ok'}
for r in [auth_router, admin_router, projects_router, tickets_router, kanban_router, task_workspace_router, structure_router, collab_router, planning_router, automation_router, schedule_router, finance_router, audit_router, notify_router, account_notifications_router, reminders_router, inbox_router, task_media_router, notification_controls_router]: api.include_router(r)
app.include_router(api)

origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]
if os.environ.get('APP_ORIGIN'): origins.append(os.environ['APP_ORIGIN'])
cors = {'allow_origin_regex': '.*'} if '*' in origins or not origins else {'allow_origins': origins}
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'], allow_headers=['Content-Type', 'Authorization'], **cors)
logging.basicConfig(level=logging.INFO)
