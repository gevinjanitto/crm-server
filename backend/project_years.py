from datetime import datetime
from zoneinfo import ZoneInfo
from core import db

ACCEPTED_TICKETS = ['Diterima', 'Dikerjakan', 'Selesai', 'Ditutup']


def current_year():
    return str(datetime.now(ZoneInfo('Asia/Makassar')).year)


def _year(value):
    y = str(value or '')[:4]
    return y if y.isdigit() else None


async def maintenance_info(project_ids):
    """Approved maintenance per project: years (by start date), total cost and count."""
    info = {}
    if not project_ids: return info
    def add(pid, year, cost):
        if not year: return
        i = info.setdefault(pid, {'years': set(), 'cost': 0, 'count': 0})
        i['years'].add(year); i['cost'] += cost or 0; i['count'] += 1
    for m in await db.maintenances.find({'project_id': {'$in': project_ids}}, {'_id': 0}).to_list(50000):
        add(m['project_id'], _year(m.get('started_date')) or _year(m.get('entry_date')) or _year(m.get('created_at')), m.get('estimate', 0))
    for t in await db.tickets.find({'project_id': {'$in': project_ids}, 'status': {'$in': ACCEPTED_TICKETS}}, {'_id': 0}).to_list(50000):
        if t['status'] == 'Ditutup' and not (t.get('accepted_at') or t.get('approved') or t.get('task_id')): continue
        add(t['project_id'], _year(t.get('accepted_at')) or _year(t.get('created_at')), t.get('estimate', 0))
    return {k: {**v, 'years': sorted(v['years']), 'year': max(v['years'])} for k, v in info.items()}


async def maintenance_years(project_ids):
    return {k: v['years'] for k, v in (await maintenance_info(project_ids)).items()}


async def completion_years(rows):
    """Year a finished project reached Selesai (status log), fallback to stored completion/update date."""
    done = [p['id'] for p in rows if p.get('status') == 'Selesai']
    logs = {}
    if done:
        for r in await db.project_status_logs.find({'project_id': {'$in': done}, 'to_status': 'Selesai'}, {'_id': 0, 'project_id': 1, 'created_at': 1}).to_list(50000):
            logs[r['project_id']] = max(logs.get(r['project_id'], ''), r.get('created_at') or '')
    return {p['id']: _year(p.get('completed_at')) or _year(logs.get(p['id'])) or _year(p.get('updated_at')) or current_year() for p in rows if p['id'] in done}


def group_year(p, done_years=None, now_year=None):
    """Finished projects use their deadline year; others the start year (fallback created date)."""
    if p.get('status') == 'Selesai':
        return _year(p.get('due_date')) or _year(p.get('start_date')) or (done_years or {}).get(p['id']) or now_year or current_year()
    return _year(p.get('start_date')) or _year(p.get('created_at')) or now_year or current_year()


async def year_fields(rows):
    done = await completion_years(rows)
    maint = await maintenance_info([p['id'] for p in rows])
    out = {}
    for p in rows:
        m = maint.get(p['id']) if p.get('status') == 'Selesai' else None
        gy = group_year(p, done)
        out[p['id']] = {'group_year': gy, 'completion_year': gy if p.get('status') == 'Selesai' else None,
                        'maintenance_years': m['years'] if m else [], 'maintenance_year': m['year'] if m else None,
                        'maintenance_cost': m['cost'] if m else 0, 'maintenance_count': m['count'] if m else 0}
    return out
