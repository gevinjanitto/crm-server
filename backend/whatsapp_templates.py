from fastapi import APIRouter, Depends, HTTPException
from core import db, now, authorize, log_activity
from auth import current_user
from whatsapp import whatsapp_configuration_error
from whatsapp_template import SETTING_ID, STATUS_LABELS, TEMPLATE_BODY, create_and_submit, approval_status

router = APIRouter(prefix='/admin/whatsapp-template')


def _public(row):
    row = row or {}
    status = row.get('status') or 'none'
    return {'content_sid': row.get('content_sid', ''), 'name': row.get('name', ''), 'status': status,
            'status_label': STATUS_LABELS.get(status, 'Belum disinkronkan' if status == 'none' else status),
            'rejection_reason': row.get('rejection_reason', ''), 'synced_at': row.get('synced_at'),
            'checked_at': row.get('checked_at'), 'outdated': bool(row) and row.get('body') != TEMPLATE_BODY, 'body': TEMPLATE_BODY,
            'configuration_note': whatsapp_configuration_error()}


async def _save(values):
    await db.app_settings.update_one({'id': SETTING_ID}, {'$set': values, '$setOnInsert': {'id': SETTING_ID}}, upsert=True)
    return await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0})


@router.get('')
async def template_state(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    return _public(await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0}))


@router.post('/refresh')
async def refresh(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    row = await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0})
    if not row or not row.get('content_sid'): raise HTTPException(400, 'Template belum disinkronkan ke Twilio.')
    try: state = await approval_status(row['content_sid'])
    except ValueError as e: raise HTTPException(502, str(e))
    return _public(await _save({**state, 'checked_at': now()}))


@router.post('/sync')
async def sync(u=Depends(current_user)):
    await authorize(u, 'user.manage')
    problem = whatsapp_configuration_error()
    if problem: raise HTTPException(400, problem)
    row = await db.app_settings.find_one({'id': SETTING_ID}, {'_id': 0}) or {}
    if row.get('content_sid') and row.get('body') == TEMPLATE_BODY and row.get('status') not in ('rejected', 'disabled'):
        try: return _public(await _save({**await approval_status(row['content_sid']), 'checked_at': now()}))
        except ValueError as e: raise HTTPException(502, str(e))
    try: created = await create_and_submit()
    except ValueError as e: raise HTTPException(502, str(e))
    saved = await _save({**created, 'synced_at': now(), 'checked_at': now()})
    await log_activity(u, 'sinkronkan', 'template whatsapp', SETTING_ID, '', details={'content_sid': created['content_sid']})
    return _public(saved)
