import re
from html.parser import HTMLParser
from fastapi import APIRouter, Depends, HTTPException
from core import db, project_scope, project_statuses, MANAGERS, now
from auth import current_user
from task_rules import assignee_ids
from workspace_common import can_open_doc

router = APIRouter()

@router.get('/tasks/mine')
async def my_tasks(u=Depends(current_user)):
    if u['role'] not in MANAGERS + ['Developer']: return []
    projects = await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'name': 1, 'task_statuses': 1}).to_list(2000)
    info = {p['id']: p for p in projects}
    done = {pid: {s['name'] for s in project_statuses(p) if s.get('kind') == 'done'} for pid, p in info.items()}
    tasks = await db.tasks.find({'project_id': {'$in': list(info)}}, {'_id': 0}).to_list(10000)
    out = []
    for t in tasks:
        if t.get('status') in done[t['project_id']]: continue
        subs = [s for s in t.get('subtasks', []) if s.get('assigned_to') == u['id'] and not s.get('done')]
        if u['id'] not in assignee_ids(t) and not subs: continue
        out.append({'id': t['id'], 'project_id': t['project_id'], 'project_name': info[t['project_id']]['name'], 'title': t['title'],
                    'status': t.get('status', ''), 'priority': t.get('priority', ''), 'due_date': t.get('due_date'),
                    'subtasks': [s['title'] for s in subs] if u['id'] not in assignee_ids(t) else []})
    rank = {'Mendesak': 0, 'Tinggi': 1, 'Sedang': 2, 'Rendah': 3}
    return sorted(out, key=lambda x: (rank.get(x['priority'], 4), x['due_date'] or '9999', x['title']))

class _Blocks(HTMLParser):
    BLOCK = {'p', 'h1', 'h2', 'h3', 'blockquote', 'pre'}
    def __init__(self):
        super().__init__(); self.stack, self.out = [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'li': self.stack.append({'tag': 'li', 'task': a.get('data-type') == 'taskItem', 'checked': a.get('data-checked') == 'true', 'text': []})
        elif tag in self.BLOCK and not any(s['tag'] == 'li' for s in self.stack): self.stack.append({'tag': tag, 'task': False, 'checked': False, 'text': []})
        elif tag == 'br' and self.stack: self.stack[-1]['text'].append(' ')
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1]['tag'] == tag:
            b = self.stack.pop(); self.out.append({**b, 'text': ' '.join(''.join(b['text']).split())})
    def handle_data(self, data):
        if self.stack: self.stack[-1]['text'].append(data)

def mention_lines(content, username):
    parser = _Blocks(); parser.feed(content or ''); parser.close()
    pattern = re.compile(rf'(?<![\w@])@{re.escape(username)}(?![\w.-])', re.I)
    return [b for b in parser.out if pattern.search(b['text']) and not b['checked']]

@router.get('/notes/mentions/mine')
async def my_note_mentions(u=Depends(current_user)):
    if not u.get('username'): return []
    scope = project_scope(u) if u['role'] == 'Client' else {}
    projects = {p['id']: p for p in await db.projects.find(scope, {'_id': 0, 'id': 1, 'name': 1, 'assigned_to': 1, 'client_id': 1}).to_list(5000)}
    docs = await db.workspace_docs.find({'project_id': {'$in': list(projects)}}, {'_id': 0, 'id': 1, 'project_id': 1, 'title': 1, 'content': 1, 'visibility': 1, 'updated_at': 1, 'updated_by': 1}).sort('updated_at', -1).to_list(5000)
    out = []
    for d in docs:
        p = projects[d['project_id']]
        for i, b in enumerate(mention_lines(d.get('content'), u['username'])):
            out.append({'id': f"{d['id']}-{i}", 'doc_id': d['id'], 'doc_title': d.get('title', ''), 'project_id': d['project_id'], 'project_name': p['name'],
                        'text': b['text'][:240], 'checklist': b['task'], 'can_open': can_open_doc(u, p, d), 'updated_at': d.get('updated_at'), 'updated_by': d.get('updated_by', '')})
    return out

def _mentions_text(text, username):
    return bool(re.search(rf'(?<![\w@])@{re.escape(username)}(?![\w.-])', text or '', re.I))

@router.get('/mentions/mine')
async def my_mentions(u=Depends(current_user)):
    notes = [{**m, 'source': 'notes', 'source_label': 'Notes', 'link': f"/projects/{m['project_id']}/docs?doc={m['doc_id']}", 'location': m['doc_title'], 'date': m.get('updated_at')} for m in await my_note_mentions(u)]
    projects = {p['id']: p['name'] for p in await db.projects.find(project_scope(u), {'_id': 0, 'id': 1, 'name': 1}).to_list(5000)}
    out = []
    uname = u.get('username') or ''
    comments = await db.task_comments.find({'project_id': {'$in': list(projects)}}, {'_id': 0}).sort('created_at', -1).to_list(5000) if projects else []
    comments = [c for c in comments if c.get('author_id') != u['id'] and (any(m.get('id') == u['id'] for m in c.get('mentions') or []) or (uname and _mentions_text(c.get('message'), uname)))]
    tids = list({c['task_id'] for c in comments})
    titles = {t['id']: t['title'] for t in await db.tasks.find({'id': {'$in': tids}}, {'_id': 0, 'id': 1, 'title': 1}).to_list(5000)} if tids else {}
    for c in comments:
        out.append({'id': f"tc-{c['id']}", 'source': 'task_comment', 'source_label': 'Komentar task', 'text': (c.get('message') or 'Lampiran')[:240],
                    'project_id': c['project_id'], 'project_name': projects.get(c['project_id'], ''), 'location': titles.get(c['task_id'], 'Task'),
                    'link': f"/projects/{c['project_id']}/kanban?task={c['task_id']}&comment={c['id']}", 'can_open': True, 'checklist': False, 'date': c.get('created_at'), 'updated_by': c.get('author_name', '')})
    if uname and u['role'] in MANAGERS + ['Developer', 'Client']:
        tickets = {t['id']: t for t in await db.tickets.find({'project_id': {'$in': list(projects)}}, {'_id': 0, 'id': 1, 'title': 1, 'code': 1, 'project_id': 1}).to_list(5000)} if projects else {}
        rows = await db.ticket_comments.find({'ticket_id': {'$in': list(tickets)}}, {'_id': 0}).sort('created_at', -1).to_list(5000) if tickets else []
        for c in rows:
            if c.get('system') or (u['role'] == 'Client' and c.get('internal')) or c.get('author_name') == u['name'] or not _mentions_text(c.get('message'), uname): continue
            t = tickets[c['ticket_id']]
            out.append({'id': f"tk-{c['id']}", 'source': 'ticket_comment', 'source_label': 'Komentar tiket', 'text': c['message'][:240],
                        'project_id': t['project_id'], 'project_name': projects.get(t['project_id'], ''), 'location': f"{t.get('code', '')} {t.get('title', '')}".strip(),
                        'link': f"/tickets?ticket={t['id']}", 'can_open': True, 'checklist': False, 'date': c.get('created_at'), 'updated_by': c.get('author_name', '')})
    hidden = {d['mention_id'] for d in await db.mention_dismissals.find({'user_id': u['id']}, {'_id': 0, 'mention_id': 1}).to_list(10000)}
    out = [m for m in out if m['id'] not in hidden]
    return notes + sorted(out, key=lambda m: m.get('date') or '', reverse=True)

@router.delete('/mentions/mine/{mid}')
async def dismiss_mention(mid: str, u=Depends(current_user)):
    if not mid.startswith(('tc-', 'tk-')): raise HTTPException(400, 'Mention notes hilang otomatis setelah dicentang di notes.')
    key = f"{u['id']}:{mid}"
    if not await db.mention_dismissals.find_one({'id': key}, {'_id': 0, 'id': 1}):
        await db.mention_dismissals.insert_one({'id': key, 'user_id': u['id'], 'mention_id': mid, 'created_at': now()})
    return {'message': 'Mention dihapus dari dashboard.'}
