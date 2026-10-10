import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, model_validator
from core import db, uid, now, log_activity
from auth import current_user
from notify import notify, ids_by_role
from task_media import store_files, remove_files, file_response, DOC_TYPES, IMAGE_TYPES

log = logging.getLogger('reminders')
router = APIRouter()
NOTIFY_DAYS = 14
MAX_ATTACHMENTS = 20
ATTACH_TYPES = {**DOC_TYPES, **IMAGE_TYPES}


def check_extra(extra_notify, extra_days):
    if not extra_notify: return
    if not extra_days: raise ValueError('Isi jumlah hari notifikasi tambahan.')
    if extra_days == NOTIFY_DAYS: raise ValueError('14 hari sudah menjadi notifikasi utama. Pilih jumlah hari lain.')


class ReminderInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=3000)
    start_date: date
    end_date: date
    extra_notify: bool = False
    extra_notify_days: Optional[int] = Field(default=None, ge=1, le=365)

    @model_validator(mode='after')
    def check_range(self):
        if self.end_date < self.start_date: raise ValueError('Tanggal akhir tidak boleh sebelum tanggal mulai.')
        check_extra(self.extra_notify, self.extra_notify_days)
        return self


class ReminderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=3000)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    done: Optional[bool] = None
    extra_notify: Optional[bool] = None
    extra_notify_days: Optional[int] = Field(default=None, ge=1, le=365)


def admin_only(u):
    if u['role'] != 'Admin': raise HTTPException(403, 'Menu reminder hanya untuk Admin.')


def today(): return datetime.now(ZoneInfo('Asia/Makassar')).date()


def public_file(a): return {k: a[k] for k in ('id', 'name', 'size', 'content_type', 'is_image', 'uploaded_by', 'created_at') if k in a}


def with_meta(r, projects=None):
    left = (date.fromisoformat(r['end_date']) - today()).days
    return {**r, 'extra_notify': bool(r.get('extra_notify')), 'extra_notify_days': r.get('extra_notify_days'), 'extra_notified_at': r.get('extra_notified_at'),
            'attachments': [public_file(a) for a in r.get('attachments') or []],
            'status': 'Selesai' if r.get('done') else 'Berjalan', 'days_left': left, 'project_name': (projects or {}).get(r['project_id'], r.get('project_name', ''))}


async def project_or_404(pid):
    p = await db.projects.find_one({'id': pid}, {'_id': 0, 'id': 1, 'name': 1})
    if not p: raise HTTPException(404, 'Project tidak ditemukan.')
    return p


async def reminder_or_404(pid, rid):
    r = await db.project_reminders.find_one({'id': rid, 'project_id': pid}, {'_id': 0})
    if not r: raise HTTPException(404, 'Reminder tidak ditemukan.')
    return r


async def claim(reminder, field):
    res = await db.project_reminders.update_one({'id': reminder['id'], field: None, 'done': False}, {'$set': {field: now()}})
    return bool(res.modified_count)


async def notify_due(reminder):
    """Notif utama sekali saat sisa <= 14 hari, plus notif tambahan (opsional) saat sisa <= N hari."""
    if reminder.get('done'): return 0
    left = (date.fromisoformat(reminder['end_date']) - today()).days
    claimed = []
    if not reminder.get('notified_at') and left <= NOTIFY_DAYS and await claim(reminder, 'notified_at'): claimed.append('notified_at')
    extra_days = reminder.get('extra_notify_days')
    if reminder.get('extra_notify') and extra_days and not reminder.get('extra_notified_at') and left <= extra_days and await claim(reminder, 'extra_notified_at'):
        claimed.append('extra_notified_at')
    if not claimed: return 0
    p = await db.projects.find_one({'id': reminder['project_id']}, {'_id': 0, 'name': 1}) or {}
    end = date.fromisoformat(reminder['end_date']).strftime('%d/%m/%Y')
    when = f'{left} hari lagi' if left > 0 else ('hari ini' if left == 0 else f'sudah lewat {-left} hari')
    title = f"Reminder tambahan (H-{extra_days}): {reminder['name']}" if claimed == ['extra_notified_at'] else f"Reminder: {reminder['name']}"
    msg = f"Reminder \"{reminder['name']}\" pada project {p.get('name', '-')} berakhir {end} ({when})."
    if reminder.get('description'): msg += f" Keterangan: {reminder['description'][:400]}"
    if reminder.get('attachments'): msg += f" Lampiran: {len(reminder['attachments'])} dokumen."
    try:
        await notify(await ids_by_role('Admin'), title, msg, 'pengingat', '/reminders', reminder['project_id'], 'reminder', reminder['id'])
    except Exception:
        await db.project_reminders.update_one({'id': reminder['id']}, {'$set': {f: None for f in claimed}}); raise
    return 1


async def check_due_reminders():
    sent = 0
    for r in await db.project_reminders.find({'done': False}, {'_id': 0}).to_list(5000):
        try: sent += await notify_due(r)
        except Exception: log.exception('Reminder notification failed')
    return sent


@router.get('/reminders')
async def all_reminders(u=Depends(current_user)):
    admin_only(u)
    rows = await db.project_reminders.find({}, {'_id': 0}).sort('end_date', 1).to_list(5000)
    names = {p['id']: p['name'] for p in await db.projects.find({'id': {'$in': list({r['project_id'] for r in rows})}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(5000)} if rows else {}
    return [with_meta(r, names) for r in rows]


@router.get('/projects/{pid}/reminders')
async def project_reminders(pid: str, u=Depends(current_user)):
    admin_only(u); await project_or_404(pid)
    rows = await db.project_reminders.find({'project_id': pid, 'done': False}, {'_id': 0}).sort('end_date', 1).to_list(1000)
    return [with_meta(r) for r in rows]


@router.post('/projects/{pid}/reminders')
async def add_reminder(pid: str, data: ReminderInput, u=Depends(current_user)):
    admin_only(u); p = await project_or_404(pid)
    r = {'id': uid(), 'project_id': pid, 'project_name': p['name'], 'name': data.name.strip(), 'description': data.description.strip(),
         'start_date': data.start_date.isoformat(), 'end_date': data.end_date.isoformat(), 'done': False, 'done_at': None, 'done_by': '',
         'extra_notify': data.extra_notify, 'extra_notify_days': data.extra_notify_days if data.extra_notify else None, 'extra_notified_at': None,
         'attachments': [], 'notified_at': None, 'created_by': u['id'], 'created_at': now(), 'updated_at': now()}
    await db.project_reminders.insert_one(r.copy())
    await log_activity(u, 'buat', 'reminder', r['id'], r['name'], pid)
    await notify_due(r)
    return with_meta(await db.project_reminders.find_one({'id': r['id']}, {'_id': 0}))


@router.patch('/projects/{pid}/reminders/{rid}')
async def edit_reminder(pid: str, rid: str, data: ReminderUpdate, u=Depends(current_user)):
    admin_only(u)
    r = await reminder_or_404(pid, rid)
    changes = {k: (v.isoformat() if isinstance(v, date) else v.strip() if isinstance(v, str) else v) for k, v in data.model_dump(exclude_none=True).items()}
    if (changes.get('end_date') or r['end_date']) < (changes.get('start_date') or r['start_date']): raise HTTPException(400, 'Tanggal akhir tidak boleh sebelum tanggal mulai.')
    extra_on = changes.get('extra_notify', bool(r.get('extra_notify')))
    extra_days = changes.get('extra_notify_days', r.get('extra_notify_days'))
    try: check_extra(extra_on, extra_days)
    except ValueError as e: raise HTTPException(400, str(e))
    if not extra_on: changes['extra_notify_days'] = None
    end_changed = 'end_date' in changes and changes['end_date'] != r['end_date']
    if end_changed: changes['notified_at'] = None
    if end_changed or extra_on != bool(r.get('extra_notify')) or (extra_on and extra_days != r.get('extra_notify_days')): changes['extra_notified_at'] = None
    if 'done' in changes: changes.update(done_at=now() if changes['done'] else None, done_by=u['name'] if changes['done'] else '')
    changes['updated_at'] = now()
    await db.project_reminders.update_one({'id': rid}, {'$set': changes})
    r = await db.project_reminders.find_one({'id': rid}, {'_id': 0})
    await log_activity(u, 'selesai' if changes.get('done') else 'ubah', 'reminder', rid, r['name'], pid)
    await notify_due(r)
    return with_meta(await db.project_reminders.find_one({'id': rid}, {'_id': 0}))


@router.delete('/projects/{pid}/reminders/{rid}')
async def delete_reminder(pid: str, rid: str, u=Depends(current_user)):
    admin_only(u)
    r = await reminder_or_404(pid, rid)
    await db.project_reminders.delete_one({'id': rid})
    remove_files(r.get('attachments'))
    await log_activity(u, 'hapus', 'reminder', rid, r['name'], pid)
    return {'message': 'Reminder dihapus.'}


@router.post('/projects/{pid}/reminders/{rid}/attachments')
async def upload_attachments(pid: str, rid: str, files: list[UploadFile] = File(...), u=Depends(current_user)):
    admin_only(u)
    r = await reminder_or_404(pid, rid)
    existing = r.get('attachments') or []
    if len(existing) + len(files) > MAX_ATTACHMENTS: raise HTTPException(400, f'Maksimal {MAX_ATTACHMENTS} dokumen per reminder.')
    added = await store_files(files, f'reminders/{rid}', ATTACH_TYPES, u)
    await db.project_reminders.update_one({'id': rid}, {'$set': {'attachments': existing + added, 'updated_at': now()}})
    await log_activity(u, 'unggah', 'dokumen reminder', rid, r['name'], pid, {'dokumen': [a['name'] for a in added]})
    return with_meta(await db.project_reminders.find_one({'id': rid}, {'_id': 0}))


@router.get('/projects/{pid}/reminders/{rid}/attachments/{aid}')
async def get_attachment(pid: str, rid: str, aid: str, u=Depends(current_user)):
    admin_only(u)
    r = await reminder_or_404(pid, rid)
    a = next((a for a in r.get('attachments') or [] if a['id'] == aid), None)
    if not a: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    return await file_response(a)


@router.delete('/projects/{pid}/reminders/{rid}/attachments/{aid}')
async def delete_attachment(pid: str, rid: str, aid: str, u=Depends(current_user)):
    admin_only(u)
    r = await reminder_or_404(pid, rid)
    files = r.get('attachments') or []
    a = next((a for a in files if a['id'] == aid), None)
    if not a: raise HTTPException(404, 'Dokumen tidak ditemukan.')
    await db.project_reminders.update_one({'id': rid}, {'$set': {'attachments': [x for x in files if x['id'] != aid], 'updated_at': now()}})
    remove_files([a])
    await log_activity(u, 'hapus', 'dokumen reminder', rid, r['name'], pid, {'dokumen': a['name']})
    return with_meta(await db.project_reminders.find_one({'id': rid}, {'_id': 0}))
