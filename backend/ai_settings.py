import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core import db, now, log_activity
from auth import current_user

router = APIRouter()
AI_ROLES = ['Admin', 'Admin Project', 'Developer']

class AiSettingsInput(BaseModel):
    enabled: Optional[bool] = None
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)

async def ai_config():
    s = await db.app_settings.find_one({'id': 'ai'}, {'_id': 0}) or {}
    env_off = os.environ.get('AI_ENABLED', 'true').strip().lower() == 'false'
    return {'enabled': bool(s.get('enabled')) and not env_off, 'env_locked': env_off,
            'base_url': (s.get('base_url') or os.environ.get('AI_BASE_URL', '')).rstrip('/'),
            'model': s.get('model') or os.environ.get('AI_MODEL', ''),
            'api_key': s.get('api_key') or os.environ.get('AI_API_KEY', ''),
            'key_source': 'admin' if s.get('api_key') else ('env' if os.environ.get('AI_API_KEY') else '')}

def assistant_ready(c): return bool(c['enabled'] and c['api_key'] and c['base_url'] and c['model'])

async def require_ai():
    if not (await ai_config())['enabled']: raise HTTPException(403, 'Fitur AI sedang dinonaktifkan oleh admin.')

def admin_only(u):
    if u['role'] != 'Admin': raise HTTPException(403, 'Hanya Admin yang dapat mengatur fitur AI.')

def public_settings(c):
    key = c['api_key']
    return {'enabled': c['enabled'], 'env_locked': c['env_locked'], 'base_url': c['base_url'], 'model': c['model'],
            'has_api_key': bool(key), 'key_hint': f'…{key[-4:]}' if len(key) > 8 else ('…' if key else ''), 'key_source': c['key_source'],
            'assistant_ready': assistant_ready(c)}

@router.get('/ai/status')
async def ai_status(u=Depends(current_user)):
    c = await ai_config()
    return {'enabled': c['enabled'], 'assistant_ready': assistant_ready(c), 'allowed': u['role'] in AI_ROLES}

@router.get('/admin/ai-settings')
async def get_ai_settings(u=Depends(current_user)):
    admin_only(u)
    return public_settings(await ai_config())

@router.patch('/admin/ai-settings')
async def save_ai_settings(data: AiSettingsInput, u=Depends(current_user)):
    admin_only(u)
    update = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.model_dump(exclude_none=True).items()}
    await db.app_settings.update_one({'id': 'ai'}, {'$set': {**update, 'updated_at': now(), 'updated_by': u['id']}, '$setOnInsert': {'created_at': now()}}, upsert=True)
    details = {k: v for k, v in update.items() if k != 'api_key'}
    if 'api_key' in update: details['api_key'] = 'diubah' if update['api_key'] else 'dikosongkan'
    await log_activity(u, 'ubah', 'pengaturan AI', 'ai', 'Fitur AI & MCP', '', details)
    return public_settings(await ai_config())
