import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from core import db, project_scope, project_for, authorize, status_progress, log_activity, MANAGERS
from schemas import TaskUpdate, SubtaskTreeInput, SubtaskUpdate, TaskCommentInput
from task_rules import assignee_ids
from kanban import edit_task, add_subtask_tree, edit_subtask, add_comment, kind_of, status_names
from api_tokens import any_principal, public_base

router = APIRouter()
LIMIT = 50
RANK = {'Mendesak': 0, 'Tinggi': 1, 'Sedang': 2, 'Rendah': 3}

def plain(html, n=300):
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html or '')).strip()
    return text[:n] + ('…' if len(text) > n else '')

def today(): return datetime.now(timezone.utc).date().isoformat()
def sort_key(t): return (RANK.get(t.get('priority'), 4), t.get('due_date') or '9999', t.get('title', ''))

async def projects_for(u, project=None):
    rows = await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'code': 1, 'name': 1, 'status': 1, 'task_statuses': 1, 'in_maintenance': 1}).to_list(2000)
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
    p = await project_for(ctx['user'], t['project_id'], 'task.read')
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

S = lambda desc: {'type': 'string', 'description': desc}
PROJECT = S('ID, kode, atau nama project (opsional)')
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
}

def tool_specs():
    return [{'name': n, 'description': d, 'write': w, 'inputSchema': {'type': 'object', 'properties': props, 'required': req, 'additionalProperties': False}}
            for n, (_, w, d, props, req) in TOOLS.items()]

async def run_tool(name, args, ctx):
    if name not in TOOLS: raise HTTPException(404, f'Tool "{name}" tidak dikenal.')
    fn, write, _, props, req = TOOLS[name]
    if write and 'write' not in ctx['scopes']: raise HTTPException(403, 'Token ini hanya baca (read-only). Buat token dengan scope write untuk aksi ini.')
    args = {k: v for k, v in (args or {}).items() if k in props and v not in (None, '')}
    missing = [k for k in req if k not in args]
    if missing: raise HTTPException(400, f"Parameter wajib: {', '.join(missing)}.")
    return await fn(ctx, **args)

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
