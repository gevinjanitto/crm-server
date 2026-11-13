from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from core import db, now, authorize, log_activity
from auth import current_user
from whatsapp import whatsapp_configuration_error, sandbox_mode, detect_trial, trial_content_sid, _sender
from whatsapp_template import SETTING_ID, STATUS_LABELS, TEMPLATE_BODY, create_and_submit, approval_status

router = APIRouter(prefix='/admin/whatsapp-template')
PENDING_KEYS = ('content_sid', 'name', 'status', 'rejection_reason', 'body', 'synced_at')


def _label(status):
    return STATUS_LABELS.get(status, 'Belum disinkronkan' if status == 'none' else status)


def _public(row):
    row = row or {}
    status = row.get('status') or 'none'
    pending = row.get('pending_status') or ''
    return {'content_sid': row.get('content_sid', ''), 'name': row.get('name', ''), 'status': status, 'category': row.get('category', ''),
            'status_label': _label(status),
            'rejection_reason': row.get('rejection_reason', ''), 'synced_at': row.get('synced_at'),
            'checked_at': row.get('checked_at'), 'outdated': bool(row) and TEMPLATE_BODY not in (row.get('body'), row.get('pending_body')), 'body': TEMPLATE_BODY,
            'pending_content_sid': row.get('pending_content_sid', ''), 'pending_name': row.get('pending_name', ''), 'pending_status': pending,
            'pending_status_label': _label(pending) if pending else '', 'pending_rejection_reason': row.get('pending_rejection_reason', ''),
            'configuration_note': whatsapp_configuration_error(), 'sandbox': sandbox_mode(),
            'trial_content_sid': trial_content_sid() if sandbox_mode() else '', 'sender': _sender()[9:]}

SANDBOX_NOTE = 'Akun Twilio Trial: template sendiri tidak bisa dibuat. Pakai ContentSid template bawaan dari halaman Try out WhatsApp (TWILIO_CONTENT_SID).'


async def _save(values, unset=None):
    update = {'$set': values, '$setOnInsert': {'id': SETTING_ID}}
    if unset: update['$unset'] = {k: '' for k in unset}
    await db.app_settings.update_one({'id': SETTING_ID}, update, upsert=True)
    return await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0})


async def _check_pending(row):
    state = await approval_status(row['pending_content_sid'])
    if state['status'] == 'approved':
        # Template baru disetujui: gantikan template lama.
        values = {k: row.get(f'pending_{k}') for k in PENDING_KEYS}
        return await _save({**values, **state, 'checked_at': now()}, [f'pending_{k}' for k in PENDING_KEYS] + ['pending_checked_at'])
    return await _save({'pending_status': state['status'], 'pending_rejection_reason': state['rejection_reason'], 'pending_checked_at': now()})


async def promote_pending(row):
    """Dipanggil saat kirim WhatsApp: cek template baru paling sering tiap 10 menit, pasang otomatis bila sudah disetujui."""
    if not row.get('pending_content_sid') or row.get('pending_status') in ('rejected', 'disabled'): return row
    last = row.get('pending_checked_at') or row.get('pending_synced_at') or ''
    try:
        if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(minutes=10): return row
    except ValueError:
        pass
    try: return await _check_pending(row)
    except ValueError: return row


@router.get('')
async def template_state(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    await detect_trial()
    return _public(await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0}))


@router.post('/refresh')
async def refresh(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    row = await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0})
    if await detect_trial() or sandbox_mode(): raise HTTPException(400, SANDBOX_NOTE)
    if not row or not row.get('content_sid'): raise HTTPException(400, 'Template belum disinkronkan ke Twilio.')
    try:
        if row.get('pending_content_sid'): row = await _check_pending(row)
        row = await _save({**await approval_status(row['content_sid']), 'checked_at': now()})
    except ValueError as e: raise HTTPException(502, str(e))
    return _public(row)


@router.post('/sync')
async def sync(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    if await detect_trial() or sandbox_mode(): raise HTTPException(400, SANDBOX_NOTE)
    problem = whatsapp_configuration_error()
    if problem: raise HTTPException(400, problem)
    row = await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0}) or {}
    try:
        if row.get('content_sid'):
            # Template lama yang dikategorikan MARKETING oleh Meta tidak bisa diubah: buat template UTILITY baru (lama tetap dipakai sampai yang baru disetujui).
            current = await approval_status(row['content_sid'])
            row = await _save({**current, 'checked_at': now()})
            if current.get('category', '').upper() == 'MARKETING': row = {**row, 'body': ''}
        if row.get('content_sid') and row.get('body') == TEMPLATE_BODY and row.get('status') not in ('rejected', 'disabled'):
            return _public(row)
        if row.get('pending_content_sid') and row.get('pending_body') == TEMPLATE_BODY and row.get('pending_status') not in ('rejected', 'disabled') \
                and (await approval_status(row['pending_content_sid'])).get('category', '').upper() != 'MARKETING':
            return _public(await _check_pending(row))
        created = await create_and_submit()
    except ValueError as e: raise HTTPException(502, str(e))
    if row.get('status') == 'approved' and row.get('content_sid'):
        # Template lama tetap dipakai sampai template baru disetujui Meta.
        saved = await _save({**{f'pending_{k}': created[k] for k in ('content_sid', 'name', 'status', 'rejection_reason', 'body')},
                             'pending_synced_at': now(), 'pending_checked_at': now()})
    else:
        saved = await _save({**created, 'synced_at': now(), 'checked_at': now()})
    await log_activity(u, 'sinkronkan', 'template whatsapp', SETTING_ID, '', details={'content_sid': created['content_sid']})
    return _public(saved)
