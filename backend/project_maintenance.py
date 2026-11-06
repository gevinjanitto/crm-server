from core import db


async def maintenance_project_ids(project_ids):
    """Projects with an open manual maintenance or an unfinished client ticket."""
    if not project_ids: return set()
    ids = set(await db.maintenances.distinct('project_id', {'project_id': {'$in': project_ids}, 'status': {'$ne': 'Selesai'}}))
    ids |= set(await db.tickets.distinct('project_id', {'project_id': {'$in': project_ids}, 'status': {'$nin': ['Selesai', 'Ditutup', 'Ditolak']}}))
    return ids


async def mark_maintenance(rows):
    """Selesai projects with active maintenance get in_maintenance=True (stored status stays Selesai)."""
    done = [p['id'] for p in rows if p.get('status') == 'Selesai']
    active = await maintenance_project_ids(done)
    for p in rows: p['in_maintenance'] = p['id'] in active
    return rows
