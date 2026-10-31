import re
import base64
import binascii
import socket
import asyncio
import ipaddress
import mimetypes
from urllib.parse import urlsplit, unquote
import httpx
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from core import db, project_scope, project_for, authorize, status_progress, log_activity, MANAGERS
from schemas import TaskUpdate, SubtaskTreeInput, SubtaskUpdate, TaskCommentInput
from task_rules import assignee_ids
from kanban import edit_task, add_subtask_tree, edit_subtask, add_comment, kind_of, status_names
from api_tokens import any_principal, public_base
from project_maintenance import mark_maintenance
from schemas import TaskInput, WorkInput
from kanban import add_task, upload_task_document
from projects import create_work, upload_document
from file_shares import shareable_document, create_share

router = APIRouter()
LIMIT = 50
RANK = {'Mendesak': 0, 'Tinggi': 1, 'Sedang': 2, 'Rendah': 3}

def plain(html, n=300):
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html or '')).strip()
    return text[:n] + ('…' if len(text) > n else '')

HIDE_DONE = ContextVar('hide_done', default=False)
EXTERNAL = ('mcp', 'api')

def finished(p): return p.get('status') == 'Selesai' and not p.get('in_maintenance')

async def guard(p):
    """MCP/API token access cannot read finished projects (Selesai without active maintenance)."""
    if HIDE_DONE.get():
        await mark_maintenance([p])
        if finished(p): raise HTTPException(404, 'Project sudah selesai dan tidak dapat dibaca melalui MCP.')
    return p

def today(): return datetime.now(timezone.utc).date().isoformat()
def sort_key(t): return (RANK.get(t.get('priority'), 4), t.get('due_date') or '9999', t.get('title', ''))

async def projects_for(u, project=None, include_done=False):
    rows = await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'code': 1, 'name': 1, 'status': 1, 'task_statuses': 1, 'in_maintenance': 1}).to_list(2000)
    if HIDE_DONE.get() and not include_done:
        await mark_maintenance(rows)
        rows = [p for p in rows if not finished(p)]
    if project:
        key = str(project).strip().lower()
        exact = [p for p in rows if key in (p['id'].lower(), str(p.get('code', '')).lower(), p['name'].lower())]
        rows = exact or [p for p in rows if key in p['name'].lower() or key in str(p.get('code', '')).lower()]
    return {p['id']: p for p in rows}

async def load_tasks(u, project=None):
    info = await projects_for(u, project)
    tasks = await db.tasks.find({'project_id': {'$in': list(info)}}, {'_id': 0, 'time_entries': 0, 'description_html': 0}).to_list(10000)
    return info, tasks

async def names_for(tasks):
    ids = list({i for t in tasks for i in assignee_ids(t)})
    rows = await db.users.find({'id': {'$in': ids}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(1000) if ids else []
    return {r['id']: r['name'] for r in rows}

def task_row(t, info, names, base, **extra):
    subs = t.get('subtasks') or []
    p = info.get(t['project_id'], {})
    return {'id': t['id'], 'judul': t['title'], 'project': p.get('name', t.get('project_name', '')), 'project_id': t['project_id'], 'status': t.get('status'),
            'prioritas': t.get('priority'), 'due_date': t.get('due_date'), 'subtask': f"{sum(1 for s in subs if s.get('done'))}/{len(subs)}",
            'assignees': [names.get(i, i) for i in assignee_ids(t)], 'url': f"{base}/projects/{t['project_id']}/kanban?task={t['id']}", **extra}

def is_done(info, t): return kind_of(info.get(t['project_id'], {}), t.get('status')) == 'done'

async def task_context(ctx, task_id):
    t = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not t: raise HTTPException(404, 'Task tidak ditemukan.')
    p = await guard(await project_for(ctx['user'], t['project_id'], 'task.read'))
    return p, t

async def write_result(ctx, tool, p, t):
    await log_activity(ctx['user'], f'AI: {tool}', 'task', t['id'], t.get('title', ''), p['id'], {'via': ctx['via']})
    fresh = await db.tasks.find_one({'id': t['id']}, {'_id': 0})
    return task_row(fresh, {p['id']: p}, await names_for([fresh]), ctx['base'])

# ---------- read tools ----------
async def tugas_saya(ctx, status=None, project=None):
    u = ctx['user']; info, tasks = await load_tasks(u, project)
    rows = [t for t in tasks if u['id'] in assignee_ids(t) and (str(t.get('status', '')).lower() == str(status).lower() if status else not is_done(info, t))]
    rows.sort(key=sort_key); names = await names_for(rows)
    return [task_row(t, info, names, ctx['base']) for t in rows[:LIMIT]]

async def tugas_belum_ada_pemilik(ctx, project=None, prioritas=None):
    info, tasks = await load_tasks(ctx['user'], project)
    rows = [t for t in tasks if not assignee_ids(t) and not is_done(info, t) and (not prioritas or str(t.get('priority', '')).lower() == str(prioritas).lower())]
    rows.sort(key=sort_key)
    return [task_row(t, info, {}, ctx['base']) for t in rows[:LIMIT]]

async def rekomendasi_tugas(ctx):
    u = ctx['user']; info, tasks = await load_tasks(u)
    open_tasks = [t for t in tasks if not is_done(info, t)]
    mine = [t for t in open_tasks if u['id'] in assignee_ids(t)]
    free = [t for t in open_tasks if not assignee_ids(t)]
    overdue = [t for t in mine + free if t.get('due_date') and t['due_date'] < today()]
    seen, out = set(), []
    names = await names_for(mine)
    for reason, group in [('Terlambat (overdue)', overdue), ('Tugas Anda', mine), ('Belum ada pemilik', free)]:
        for t in sorted(group, key=sort_key):
            if t['id'] in seen: continue
            seen.add(t['id']); out.append(task_row(t, info, names, ctx['base'], alasan=reason))
    return out[:LIMIT]

async def detail_tugas(ctx, task_id):
    p, t = await task_context(ctx, task_id)
    comments = await db.task_comments.find({'task_id': task_id}, {'_id': 0}).sort('created_at', -1).to_list(5)
    row = task_row(t, {p['id']: p}, await names_for([t]), ctx['base'])
    row.update(deskripsi=plain(t.get('description_html') or t.get('description'), 2000), start_date=t.get('start_date'),
               subtasks=[{'id': s['id'], 'judul': s['title'], 'selesai': bool(s.get('done')), 'parent_id': s.get('parent_id', '')} for s in t.get('subtasks') or []],
               komentar_terakhir=[{'oleh': c.get('author_name'), 'teks': plain(c.get('message'), 500), 'waktu': c.get('created_at')} for c in comments],
               status_tersedia=status_names(p))
    return row

async def cari_tugas(ctx, kata_kunci, project=None):
    info, tasks = await load_tasks(ctx['user'], project)
    key = str(kata_kunci).lower()
    rows = [t for t in tasks if key in t.get('title', '').lower() or key in plain(t.get('description'), 100000).lower()]
    rows.sort(key=sort_key); names = await names_for(rows)
    return [task_row(t, info, names, ctx['base']) for t in rows[:LIMIT]]

async def daftar_project(ctx, status=None):
    info = await projects_for(ctx['user'])
    rows = [p for p in info.values() if not status or str(status).lower() in (str(p.get('status', '')).lower(), 'maintenance' if p.get('in_maintenance') else '')]
    return [{'id': p['id'], 'kode': p.get('code'), 'nama': p['name'], 'status': 'Maintenance' if p.get('in_maintenance') else p.get('status'),
             'progres': status_progress(p.get('status')), 'url': f"{ctx['base']}/projects/{p['id']}"} for p in sorted(rows, key=lambda x: x['name'])[:LIMIT * 2]]

async def lihat_notes_project(ctx, project, kata_kunci=None):
    info = await projects_for(ctx['user'], project)
    if not info: raise HTTPException(404, 'Project tidak ditemukan atau tidak dapat Anda akses.')
    docs = await db.workspace_docs.find({'project_id': {'$in': list(info)}}, {'_id': 0}).sort('updated_at', -1).to_list(500)
    key = str(kata_kunci or '').lower()
    out = []
    for d in docs:
        text = plain(d.get('content'), 100000)
        if key and key not in d['title'].lower() and key not in text.lower(): continue
        total = len(re.findall(r'data-type="taskItem"', d.get('content') or ''))
        done = len(re.findall(r'<li[^>]*data-checked="true"', d.get('content') or ''))
        out.append({'id': d['id'], 'judul': d['title'], 'project': info[d['project_id']]['name'], 'ringkasan': text[:400], 'checklist': f'{done}/{total}',
                    'diperbarui': d.get('updated_at'), 'url': f"{ctx['base']}/projects/{d['project_id']}/docs?doc={d['id']}"})
    return out[:LIMIT]

async def daftar_maintenance(ctx, project=None, status=None):
    await authorize(ctx['user'], 'maintenance.read')
    info = await projects_for(ctx['user'], project)
    rows = await db.maintenances.find({'project_id': {'$in': list(info)}}, {'_id': 0}).sort('created_at', -1).to_list(2000)
    if status: rows = [m for m in rows if str(m.get('status', '')).lower() == str(status).lower()]
    links = {}
    async for t in db.tasks.find({'source': 'maintenance', 'source_id': {'$in': [m['id'] for m in rows]}}, {'_id': 0, 'id': 1, 'source_id': 1}):
        links.setdefault(t['source_id'], []).append(t['id'])
    return [{'id': m['id'], 'judul': m.get('title'), 'project': info[m['project_id']]['name'], 'status': m.get('status'), 'jenis': m.get('kind'),
             'due_date': m.get('due_date'), 'task_id': links.get(m['id'], [])} for m in rows[:LIMIT]]

async def kapasitas_tim(ctx, project=None):
    if ctx['user']['role'] not in MANAGERS: raise HTTPException(403, 'Kapasitas tim hanya untuk Admin dan Admin Project.')
    info, tasks = await load_tasks(ctx['user'], project)
    active = [t for t in tasks if not is_done(info, t)]
    names = await names_for(active)
    counts = {}
    for t in active:
        for i in assignee_ids(t) or ['']:
            c = counts.setdefault(i, {'anggota': names.get(i, 'Belum ditugaskan') if i else 'Belum ditugaskan', 'tugas_aktif': 0, 'overdue': 0})
            c['tugas_aktif'] += 1; c['overdue'] += bool(t.get('due_date') and t['due_date'] < today())
    return sorted(counts.values(), key=lambda c: -c['tugas_aktif'])

# ---------- write tools ----------
async def find_user(ref):
    key = str(ref).strip()
    q = {'active': True, 'role': {'$in': MANAGERS + ['Developer']}}
    for field in ['id', 'username', 'email', 'name']:
        found = await db.users.find_one({**q, field: key}, {'_id': 0, 'id': 1, 'name': 1})
        if found: return found
    found = await db.users.find({**q, 'name': {'$regex': re.escape(key), '$options': 'i'}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(2)
    if len(found) == 1: return found[0]
    raise HTTPException(404, f'User "{key}" tidak ditemukan atau tidak unik.')

async def assign_tugas(ctx, task_id, user=None):
    p, t = await task_context(ctx, task_id)
    target = await find_user(user) if user else ctx['user']
    ids = list(dict.fromkeys(assignee_ids(t) + [target['id']]))
    await edit_task(p['id'], task_id, TaskUpdate(assignee_ids=ids), u=ctx['user'])
    return await write_result(ctx, 'assign_tugas', p, t)

async def ubah_status_tugas(ctx, task_id, status):
    p, t = await task_context(ctx, task_id)
    match = next((s for s in status_names(p) if s.lower() == str(status).strip().lower()), None)
    if not match: raise HTTPException(400, f"Status tidak valid. Pilihan: {', '.join(status_names(p))}.")
    await edit_task(p['id'], task_id, TaskUpdate(status=match), u=ctx['user'])
    return await write_result(ctx, 'ubah_status_tugas', p, t)

async def tambah_subtask(ctx, task_id, judul=None, items=None):
    p, t = await task_context(ctx, task_id)
    drafts = items or ([judul] if judul else [])
    drafts = [{'title': d} if isinstance(d, str) else d for d in drafts]
    if not drafts: raise HTTPException(400, 'Isi judul atau items subtask.')
    await add_subtask_tree(p['id'], task_id, SubtaskTreeInput(items=drafts), u=ctx['user'])
    return await write_result(ctx, 'tambah_subtask', p, t)

async def centang_subtask(ctx, task_id, subtask_id, selesai=True):
    p, t = await task_context(ctx, task_id)
    done = selesai if isinstance(selesai, bool) else str(selesai).strip().lower() not in ('false', '0', 'no', 'tidak')
    await edit_subtask(p['id'], task_id, subtask_id, SubtaskUpdate(done=done), u=ctx['user'])
    return await write_result(ctx, 'centang_subtask', p, t)

async def tambah_komentar(ctx, task_id, teks):
    p, t = await task_context(ctx, task_id)
    c = await add_comment(p['id'], task_id, TaskCommentInput(message=str(teks)), u=ctx['user'])
    await log_activity(ctx['user'], 'AI: tambah_komentar', 'task', task_id, t['title'], p['id'], {'via': ctx['via']})
    return {'id': c['id'], 'task_id': task_id, 'teks': c['message'], 'oleh': c['author_name'], 'waktu': c['created_at']}

async def one_project(ctx, project, include_done=False):
    info = await projects_for(ctx['user'], project, include_done)
    if not info: raise HTTPException(404, 'Project tidak ditemukan, sudah selesai, atau tidak dapat Anda akses.')
    if len(info) > 1: raise HTTPException(400, 'Project tidak unik: ' + ', '.join(p['name'] for p in info.values()) + '. Gunakan ID atau kode project.')
    return next(iter(info.values()))

async def resolve_assignee(ref): return (await find_user(ref))['id'] if ref else ''

SERVER_STAGES = ['Belum Naik', 'Dev Server', 'Production']
PRIORITY_NAMES = ['Rendah', 'Sedang', 'Tinggi', 'Mendesak']
MAINT_KINDS = ['Adaptive', 'Corrective', 'Preventive', 'Support', 'Change Request']

def as_list(v):
    if v in (None, ''): return []
    if isinstance(v, list): return v
    return [x.strip() for x in re.split(r'[,;]', str(v)) if x.strip()]

def subtask_items(items):
    out = []
    for x in as_list(items):
        if isinstance(x, dict):
            title = str(x.get('judul') or x.get('title') or '').strip()
            if title: out.append({'title': title, 'description': str(x.get('deskripsi') or x.get('description') or ''), 'children': [c if isinstance(c, dict) else {'title': c, 'description': '', 'children': []} for c in subtask_items(x.get('subtasks') or x.get('children') or [])]})
        elif str(x).strip(): out.append(str(x).strip())
    return out

def pick(value, options, label):
    for o in options:
        if str(value).strip().lower() == o.lower(): return o
    raise HTTPException(400, f"{label} tidak valid: {value}. Pilihan: {', '.join(options)}.")

async def resolve_people(refs):
    return [(await find_user(r))['id'] for r in as_list(refs)]

async def resolve_list(pid, ref):
    if not ref: return ''
    rows = await db.workspace_nodes.find({'project_id': pid, 'kind': 'list'}, {'_id': 0, 'id': 1, 'name': 1}).to_list(500)
    for n in rows:
        if str(ref).strip().lower() in (n['id'].lower(), n['name'].lower()): return n['id']
    raise HTTPException(400, f"List \"{ref}\" tidak ditemukan. Pilihan: {', '.join(n['name'] for n in rows) or 'belum ada list'}.")

async def resolve_group_ref(pid, ref):
    if not ref: return None
    rows = await db.maintenance_groups.find({'project_id': pid}, {'_id': 0, 'id': 1, 'name': 1}).to_list(500)
    for g in rows:
        if str(ref).strip().lower() in (g['id'].lower(), g['name'].lower()): return g['id']
    raise HTTPException(400, f"Grup maintenance \"{ref}\" tidak ditemukan. Pilihan: {', '.join(g['name'] for g in rows) or 'belum ada grup (kosongkan untuk otomatis)'}.")

async def attach(ctx, pid, tid, nama_file, konten, ref=None):
    if not (ref or (nama_file and konten)): return None
    d = await upload_task_document(pid, tid, file=await input_file(nama_file, konten, ref), u=ctx['user'])
    return d['name']

async def opsi_form(ctx, project):
    p = await one_project(ctx, project, include_done=True)
    full = await project_for(ctx['user'], p['id'], 'task.read')
    await mark_maintenance([full])
    team = await db.users.find({'active': True, '$or': [{'role': {'$in': MANAGERS}}, {'id': {'$in': full.get('assigned_to', [])}}]}, {'_id': 0, 'name': 1, 'username': 1, 'role': 1}).to_list(200)
    lists = await db.workspace_nodes.find({'project_id': p['id'], 'kind': 'list'}, {'_id': 0, 'name': 1}).to_list(500)
    groups = await db.maintenance_groups.find({'project_id': p['id']}, {'_id': 0, 'name': 1, 'year': 1}).to_list(500)
    return {'project': full['name'], 'status_project': 'Maintenance' if full.get('in_maintenance') else full['status'], 'bisa_tambah_task': not finished(full), 'bisa_tambah_maintenance': full['status'] == 'Selesai',
            'task': {'status': status_names(full), 'server': SERVER_STAGES, 'prioritas': PRIORITY_NAMES, 'list': [n['name'] for n in lists]},
            'maintenance': {'klasifikasi': MAINT_KINDS, 'prioritas': PRIORITY_NAMES, 'grup': [g['name'] for g in groups] + ['(kosong = otomatis sesuai tahun tanggal masuk)']},
            'penanggung_jawab': [{'nama': t['name'], 'username': t['username'], 'role': t['role']} for t in team]}

async def tambah_tugas(ctx, project, judul, status=None, server='Belum Naik', penanggung_jawab=None, prioritas='Sedang', list=None, tanggal_mulai=None, target_selesai=None,
                       estimasi_jam=0, tag=None, deskripsi='', subtasks=None, lampiran_nama_file=None, lampiran_base64=None, lampiran=None):
    p = await one_project(ctx, project)
    p = await project_for(ctx['user'], p['id'], 'task.read')
    data = TaskInput(title=str(judul), description=str(deskripsi), status=pick(status, status_names(p), 'Status') if status else status_names(p)[0],
                     server=pick(server, SERVER_STAGES, 'Server'), priority=pick(prioritas, PRIORITY_NAMES, 'Prioritas'), assignee_ids=await resolve_people(penanggung_jawab) or None,
                     list_id=await resolve_list(p['id'], list), start_date=tanggal_mulai, due_date=target_selesai, estimate_hours=float(estimasi_jam or 0),
                     tags=[str(x).strip() for x in as_list(tag)], subtasks=subtask_items(subtasks))
    t = await add_task(p['id'], data, u=ctx['user'])
    res = await write_result(ctx, 'tambah_tugas', p, t)
    if lampiran or lampiran_base64: res['lampiran'] = await attach(ctx, p['id'], t['id'], lampiran_nama_file or 'lampiran', lampiran_base64, lampiran)
    return res

async def tambah_maintenance(ctx, project, judul, klasifikasi, prioritas, tanggal_masuk, grup=None, tanggal_dikerjakan=None, target_selesai=None, penanggung_jawab=None,
                             estimasi_biaya=0, deskripsi='', subtasks=None, lampiran_nama_file=None, lampiran_base64=None, lampiran=None):
    p = await one_project(ctx, project, include_done=True)
    pic = await find_user(as_list(penanggung_jawab)[0]) if penanggung_jawab else None
    data = WorkInput(title=str(judul), description=str(deskripsi), kind=pick(klasifikasi, MAINT_KINDS, 'Klasifikasi'), priority=pick(prioritas, PRIORITY_NAMES, 'Prioritas'),
                     entry_date=tanggal_masuk, started_date=tanggal_dikerjakan, due_date=target_selesai, assigned_to=pic['id'] if pic else '',
                     estimate=float(estimasi_biaya or 0), subtasks=subtask_items(subtasks), group_id=await resolve_group_ref(p['id'], grup))
    doc = await create_work(p['id'], 'maintenances', data, u=ctx['user'])
    await log_activity(ctx['user'], 'AI: tambah_maintenance', 'maintenance', doc['id'], doc['title'], p['id'], {'via': ctx['via']})
    res = {'id': doc['id'], 'judul': doc['title'], 'project': p['name'], 'status': doc['status'], 'klasifikasi': doc['kind'], 'prioritas': doc.get('priority'),
           'tanggal_masuk': doc.get('entry_date'), 'tanggal_dikerjakan': doc.get('started_date'), 'target_selesai': doc.get('due_date'), 'penanggung_jawab': pic['name'] if pic else None,
           'estimasi_biaya': doc.get('estimate'), 'task_id': doc.get('task_id'), 'url': f"{ctx['base']}/maintenance"}
    if (lampiran or lampiran_base64) and doc.get('task_id'): res['lampiran'] = await attach(ctx, p['id'], doc['task_id'], lampiran_nama_file or 'lampiran', lampiran_base64, lampiran)
    return res

class Base64File:
    def __init__(self, filename, content):
        try: self._data = base64.b64decode(re.sub(r'^data:[^,]*,', '', str(content).strip()), validate=True)
        except (binascii.Error, ValueError): raise HTTPException(400, 'konten_base64 bukan base64 yang valid.')
        self.filename, self.content_type = str(filename), None
    async def read(self, n=-1): return self._data if n < 0 else self._data[:n]

MAX_FILE = 10 * 1024 * 1024

def public_host(host):
    try: infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror: raise HTTPException(400, 'Link file tidak dapat dihubungi.')
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)

async def download(url):
    for _ in range(4):
        parts = urlsplit(url)
        if parts.scheme != 'https' or not parts.hostname or not await asyncio.to_thread(public_host, parts.hostname):
            raise HTTPException(400, 'Link file harus HTTPS publik (download_url dari ChatGPT).')
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            async with client.stream('GET', url) as r:
                if r.is_redirect: url = str(r.url.join(r.headers.get('location', ''))); continue
                if r.status_code >= 400: raise HTTPException(400, f'Gagal mengunduh file dari link (HTTP {r.status_code}). Link mungkin kedaluwarsa, unggah ulang file.')
                data = b''
                async for chunk in r.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_FILE: raise HTTPException(400, 'File harus berukuran 1 byte hingga 10 MB.')
                return data, r.headers.get('content-type', '').split(';')[0].strip()
    raise HTTPException(400, 'Link file terlalu banyak redirect.')

class UrlFile:
    def __init__(self, ref, filename=''):
        if isinstance(ref, str): ref = {'download_url': ref}
        url = str((ref or {}).get('download_url') or '').strip()
        if not url.startswith('https://'):
            raise HTTPException(400, 'File belum terbaca. Lampirkan file/gambar langsung di chat ChatGPT (bukan path /mnt/data atau chat_upload://), lalu ulangi.')
        self.url, self.content_type = url, ref.get('mime_type') or None
        self.filename = str(ref.get('file_name') or filename or '').strip() or unquote(urlsplit(url).path.rsplit('/', 1)[-1])
        self._data = None
    async def read(self, n=-1):
        if self._data is None:
            self._data, kind = await download(self.url)
            self.content_type = self.content_type or kind or None
            if '.' not in self.filename and self.content_type:
                self.filename = (self.filename or 'lampiran') + ((mimetypes.guess_extension(self.content_type) or '').replace('.jpe', '.jpg'))
        return self._data if n < 0 else self._data[:n]

async def input_file(nama_file, konten_base64, ref):
    if ref:
        f = UrlFile(ref, '' if nama_file == 'lampiran' else nama_file)
        await f.read()
        return f
    if not konten_base64: raise HTTPException(400, 'Lampirkan file (parameter file) atau isi konten_base64.')
    return Base64File(nama_file, konten_base64)

def doc_row(d, base):
    return {'id': d['id'], 'nama': d['name'], 'kategori': d.get('kind'), 'ukuran_kb': round((d.get('size') or 0) / 1024, 1), 'akses': d.get('visibility'),
            'task_id': d.get('task_id', ''), 'diunggah': d.get('created_at'), 'oleh': d.get('uploaded_by'), 'url': f"{base}/projects/{d['project_id']}/documents"}

async def upload_lampiran_tugas(ctx, task_id, nama_file='', konten_base64=None, file=None):
    p, t = await task_context(ctx, task_id)
    d = await upload_task_document(p['id'], task_id, file=await input_file(nama_file, konten_base64, file), u=ctx['user'])
    await log_activity(ctx['user'], 'AI: upload_lampiran_tugas', 'task', task_id, t['title'], p['id'], {'via': ctx['via'], 'file': d['name']})
    return doc_row(d, ctx['base'])

async def upload_dokumen_project(ctx, project, kategori, nama_file='', konten_base64=None, nama='', akses='Internal', file=None):
    p = await one_project(ctx, project)
    d = await upload_document(p['id'], file=await input_file(nama_file, konten_base64, file), kind=kategori, visibility=akses, name=str(nama or ''), url='', u=ctx['user'])
    await log_activity(ctx['user'], 'AI: upload_dokumen_project', 'dokumen', d['id'], d['name'], p['id'], {'via': ctx['via']})
    return doc_row(d, ctx['base'])

async def daftar_dokumen(ctx, project=None, task_id=None):
    if task_id:
        p, _ = await task_context(ctx, task_id); q = {'task_id': task_id}
    else:
        p = await one_project(ctx, project or ''); await project_for(ctx['user'], p['id'], 'document.read'); q = {'project_id': p['id']}
    if ctx['user']['role'] == 'Accounting': q['kind'] = {'$in': ['Kontrak', 'Penawaran Harga', 'Invoice', 'BAST']}
    rows = await db.project_documents.find({**q, 'is_deleted': False}, {'_id': 0, 'storage_path': 0}).sort('created_at', -1).to_list(200)
    return [doc_row(d, ctx['base']) for d in rows[:LIMIT]]

async def bagikan_file(ctx, document_id, masa_berlaku_jam=24, izinkan_download=True):
    d = await shareable_document(ctx['user'], document_id)
    await guard(await db.projects.find_one({'id': d['project_id']}, {'_id': 0}))
    try: hours = float(masa_berlaku_jam)
    except (TypeError, ValueError): raise HTTPException(400, 'masa_berlaku_jam harus berupa angka.')
    allow = izinkan_download if isinstance(izinkan_download, bool) else str(izinkan_download).strip().lower() not in ('false', '0', 'no', 'tidak')
    s = await create_share(ctx['user'], d, datetime.now(timezone.utc) + timedelta(hours=hours), allow)
    return {'link': f"{ctx['base']}/s/{s['token']}", 'nama': d['name'], 'kedaluwarsa': s['expires_at'], 'izinkan_download': s['allow_download']}

S = lambda desc: {'type': 'string', 'description': desc}
PROJECT = S('ID, kode, atau nama project (opsional)')
FILE = {'type': 'object', 'description': 'File/gambar yang dilampirkan user di chat (ChatGPT mengisi download_url & file_id otomatis). Utamakan ini dibanding base64.',
        'properties': {'download_url': {'type': 'string'}, 'file_id': {'type': 'string'}, 'mime_type': {'type': 'string'}, 'file_name': {'type': 'string'}}, 'required': ['download_url', 'file_id']}
SUBTASKS = {'type': 'array', 'description': 'Subtask Kanban: teks judul, atau objek {judul, deskripsi, subtasks} untuk subtask bertingkat',
            'items': {'anyOf': [{'type': 'string'}, {'type': 'object', 'properties': {'judul': {'type': 'string'}, 'deskripsi': {'type': 'string'}, 'subtasks': {'type': 'array', 'items': {}}}, 'required': ['judul']}]}}
TOOLS = {
    'tugas_saya': (tugas_saya, False, 'Daftar kartu Kanban yang ditugaskan ke user saat ini (default: yang belum selesai).', {'status': S('Filter nama status, mis. "Dikerjakan"'), 'project': PROJECT}, []),
    'tugas_belum_ada_pemilik': (tugas_belum_ada_pemilik, False, 'Kartu tanpa assignee yang belum selesai, diurutkan prioritas lalu due date.', {'project': PROJECT, 'prioritas': S('Mendesak, Tinggi, Sedang, atau Rendah')}, []),
    'rekomendasi_tugas': (rekomendasi_tugas, False, 'Rekomendasi tugas berikutnya: overdue, tugas user, lalu tugas tanpa pemilik.', {}, []),
    'detail_tugas': (detail_tugas, False, 'Detail satu kartu: deskripsi, subtask, 5 komentar terakhir, status yang tersedia.', {'task_id': S('ID task')}, ['task_id']),
    'cari_tugas': (cari_tugas, False, 'Cari kartu berdasarkan kata kunci di judul atau deskripsi.', {'kata_kunci': S('Kata kunci'), 'project': PROJECT}, ['kata_kunci']),
    'daftar_project': (daftar_project, False, 'Project yang bisa diakses user beserta status dan progres.', {'status': S('Filter status project (opsional)')}, []),
    'lihat_notes_project': (lihat_notes_project, False, 'Notes project: judul, ringkasan teks, progres checklist.', {'project': S('ID, kode, atau nama project'), 'kata_kunci': S('Kata kunci (opsional)')}, ['project']),
    'daftar_maintenance': (daftar_maintenance, False, 'Daftar maintenance beserta task_id Kanban-nya.', {'project': PROJECT, 'status': S('Filter status (opsional)')}, []),
    'kapasitas_tim': (kapasitas_tim, False, 'Jumlah tugas aktif per anggota tim (khusus Admin/Admin Project).', {'project': PROJECT}, []),
    'assign_tugas': (assign_tugas, True, 'Assign kartu ke user (default: user saat ini).', {'task_id': S('ID task'), 'user': S('ID, username, email, atau nama user (opsional, default diri sendiri)')}, ['task_id']),
    'ubah_status_tugas': (ubah_status_tugas, True, 'Ubah status kartu Kanban.', {'task_id': S('ID task'), 'status': S('Nama status tujuan')}, ['task_id', 'status']),
    'tambah_subtask': (tambah_subtask, True, 'Tambah satu atau beberapa subtask ke kartu.', {'task_id': S('ID task'), 'judul': S('Judul satu subtask'), 'items': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Beberapa judul subtask'}}, ['task_id']),
    'centang_subtask': (centang_subtask, True, 'Tandai subtask selesai atau belum.', {'task_id': S('ID task'), 'subtask_id': S('ID subtask'), 'selesai': {'type': 'boolean', 'description': 'true = selesai'}}, ['task_id', 'subtask_id']),
    'tambah_komentar': (tambah_komentar, True, 'Tambah komentar pada kartu.', {'task_id': S('ID task'), 'teks': S('Isi komentar')}, ['task_id', 'teks']),
    'daftar_dokumen': (daftar_dokumen, False, 'Daftar dokumen project atau lampiran sebuah task (isi project atau task_id).', {'project': PROJECT, 'task_id': S('ID task (opsional)')}, []),
    'opsi_form': (opsi_form, False, 'Lihat pilihan isian form task & maintenance untuk sebuah project (status, server, prioritas, list, klasifikasi, grup, penanggung jawab). Panggil ini sebelum tambah_tugas/tambah_maintenance.', {'project': S('ID, kode, atau nama project')}, ['project']),
    'tambah_tugas': (tambah_tugas, True, 'Buat task Kanban dengan isian sama seperti form "Task baru" di app. Sebelum memanggil: panggil opsi_form, lalu tanyakan ke user isian yang belum disebut (status, server, penanggung jawab, prioritas, list, tanggal mulai, target selesai, estimasi jam, tag, deskripsi, subtask, lampiran). Project yang sudah selesai tidak bisa.', {
        'project': S('ID, kode, atau nama project'), 'judul': S('Judul task'), 'status': S('Status awal (lihat opsi_form; default status pertama)'), 'server': S('Belum Naik, Dev Server, atau Production'),
        'penanggung_jawab': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Nama/username penanggung jawab (boleh lebih dari satu)'}, 'prioritas': S('Rendah, Sedang, Tinggi, atau Mendesak'),
        'list': S('Nama List workspace (opsional)'), 'tanggal_mulai': S('Tanggal mulai YYYY-MM-DD'), 'target_selesai': S('Target selesai YYYY-MM-DD'), 'estimasi_jam': {'type': 'number', 'description': 'Estimasi (jam)'},
        'tag': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Tag, mis. Frontend, API'}, 'deskripsi': S('Deskripsi task'), 'subtasks': SUBTASKS,
        'lampiran': FILE, 'lampiran_nama_file': S('Nama file lampiran beserta ekstensi (opsional)'), 'lampiran_base64': S('Isi file lampiran dalam base64 (opsional, cadangan bila tidak ada lampiran file, maks. 10 MB)')}, ['project', 'judul']),
    'tambah_maintenance': (tambah_maintenance, True, 'Catat maintenance dengan isian sama seperti form "Maintenance baru" di app (project harus berstatus Selesai); otomatis membuat kartu Kanban. Sebelum memanggil: panggil opsi_form, lalu tanyakan ke user isian wajib (judul, klasifikasi, prioritas, tanggal masuk) dan isian lain yang belum disebut (grup, tanggal dikerjakan, target selesai, penanggung jawab, estimasi biaya, deskripsi, subtask, lampiran).', {
        'project': S('ID, kode, atau nama project'), 'judul': S('Judul maintenance (min. 3 karakter)'), 'klasifikasi': S('Adaptive, Corrective, Preventive, Support, atau Change Request'),
        'prioritas': S('Rendah, Sedang, Tinggi, atau Mendesak'), 'tanggal_masuk': S('Tanggal masuk YYYY-MM-DD'), 'grup': S('Nama grup maintenance (kosongkan = otomatis sesuai tahun tanggal masuk)'),
        'tanggal_dikerjakan': S('Tanggal dikerjakan YYYY-MM-DD (opsional)'), 'target_selesai': S('Target selesai YYYY-MM-DD (opsional)'), 'penanggung_jawab': S('Nama/username penanggung jawab (opsional)'),
        'estimasi_biaya': {'type': 'number', 'description': 'Estimasi biaya tambahan dalam Rupiah'}, 'deskripsi': S('Deskripsi maintenance'), 'subtasks': SUBTASKS,
        'lampiran': FILE, 'lampiran_nama_file': S('Nama file lampiran beserta ekstensi (opsional)'), 'lampiran_base64': S('Isi file lampiran dalam base64 (opsional, cadangan bila tidak ada lampiran file, maks. 10 MB)')}, ['project', 'judul', 'klasifikasi', 'prioritas', 'tanggal_masuk']),
    'upload_lampiran_tugas': (upload_lampiran_tugas, True, 'Unggah file lampiran ke task (PDF, DOCX, XLSX, TXT, CSV, PNG, JPG, WEBP; maks. 10 MB).', {'task_id': S('ID task'), 'file': FILE, 'nama_file': S('Nama file beserta ekstensi, mis. laporan.pdf (opsional bila memakai file)'), 'konten_base64': S('Isi file dalam base64 (cadangan bila tidak ada file)')}, ['task_id']),
    'upload_dokumen_project': (upload_dokumen_project, True, 'Unggah dokumen ke project (khusus Admin/Admin Project).', {'project': S('ID, kode, atau nama project'), 'kategori': S('Kontrak, Requirement, Rincian Fitur, Timeline, UI/UX Design, Penawaran Harga, Invoice, Akses Server, BAST, Dokumentasi Penggunaan, atau Lampiran Project'),
        'file': FILE, 'nama_file': S('Nama file beserta ekstensi (opsional bila memakai file)'), 'konten_base64': S('Isi file dalam base64 (cadangan bila tidak ada file)'), 'nama': S('Nama dokumen (opsional)'), 'akses': S('Internal atau Client')}, ['project', 'kategori']),
    'bagikan_file': (bagikan_file, True, 'Buat link berbagi publik untuk file dokumen/lampiran dengan masa berlaku.', {'document_id': S('ID dokumen'), 'masa_berlaku_jam': {'type': 'number', 'description': 'Masa berlaku dalam jam (default 24, maks. 8760)'},
        'izinkan_download': {'type': 'boolean', 'description': 'true = boleh diunduh, false = hanya lihat'}}, ['document_id']),
}

def tool_specs():
    return [{'name': n, 'description': d, 'write': w, 'files': [k for k, v in props.items() if v is FILE], 'inputSchema': {'type': 'object', 'properties': props, 'required': req, 'additionalProperties': False}}
            for n, (_, w, d, props, req) in TOOLS.items()]

async def run_tool(name, args, ctx):
    if name not in TOOLS: raise HTTPException(404, f'Tool "{name}" tidak dikenal.')
    fn, write, _, props, req = TOOLS[name]
    if write and 'write' not in ctx['scopes']: raise HTTPException(403, 'Token ini hanya baca (read-only). Buat token dengan scope write untuk aksi ini.')
    args = {k: v for k, v in (args or {}).items() if k in props and v not in (None, '')}
    missing = [k for k in req if k not in args]
    if missing: raise HTTPException(400, f"Parameter wajib: {', '.join(missing)}.")
    token = HIDE_DONE.set(ctx.get('via') in EXTERNAL)
    try: return await fn(ctx, **args)
    except ValidationError as e: raise HTTPException(400, '; '.join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))
    finally: HIDE_DONE.reset(token)

def make_ctx(request, principal, via):
    u, scopes = principal
    return {'user': u, 'scopes': scopes, 'base': public_base(request), 'via': via}

@router.get('/ai/tools')
async def list_tools(principal=Depends(any_principal)):
    return tool_specs()

@router.get('/ai/tools/{name}')
async def call_tool_get(name: str, request: Request, principal=Depends(any_principal)):
    if name in TOOLS and TOOLS[name][1]: raise HTTPException(405, 'Tool tulis harus dipanggil dengan POST.')
    return {'tool': name, 'result': await run_tool(name, dict(request.query_params), make_ctx(request, principal, 'api'))}

@router.post('/ai/tools/{name}')
async def call_tool_post(name: str, request: Request, principal=Depends(any_principal)):
    try: body = await request.json()
    except Exception: body = {}
    return {'tool': name, 'result': await run_tool(name, body if isinstance(body, dict) else {}, make_ctx(request, principal, 'api'))}
