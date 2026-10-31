"""Notifikasi web (Web Push/VAPID) ke Windows, macOS, Android dan iOS (PWA terpasang)."""
import os
import json
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pywebpush import webpush, WebPushException
from core import db, uid, now
from auth import current_user

log = logging.getLogger('push')
router = APIRouter(prefix='/push')


class Keys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1000)
    keys: Keys
    device: str = Field(default='', max_length=120)


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1000)


def configured():
    return all(os.environ.get(k, '').strip() for k in ('VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_SUBJECT'))


@router.get('/public-key')
async def public_key():
    if not configured(): raise HTTPException(503, 'Notifikasi web belum diaktifkan di server (VAPID_* belum diisi).')
    return {'public_key': os.environ['VAPID_PUBLIC_KEY'].strip()}


@router.get('/status')
async def status(u=Depends(current_user)):
    return {'configured': configured(), 'devices': await db.push_subscriptions.count_documents({'user_id': u['id']})}


@router.post('/subscribe')
async def subscribe(data: SubscriptionIn, u=Depends(current_user)):
    if not data.endpoint.startswith('https://'): raise HTTPException(400, 'Endpoint push tidak valid.')
    await db.push_subscriptions.delete_many({'endpoint': data.endpoint})
    await db.push_subscriptions.insert_one({'id': uid(), 'user_id': u['id'], 'endpoint': data.endpoint, 'keys': data.keys.model_dump(), 'device': data.device, 'created_at': now()})
    return {'message': 'Notifikasi web aktif di perangkat ini.'}


@router.post('/unsubscribe')
async def unsubscribe(data: EndpointIn, u=Depends(current_user)):
    await db.push_subscriptions.delete_many({'user_id': u['id'], 'endpoint': data.endpoint})
    return {'message': 'Notifikasi web dimatikan di perangkat ini.'}


@router.post('/test')
async def test(u=Depends(current_user)):
    if not await db.push_subscriptions.count_documents({'user_id': u['id']}): raise HTTPException(400, 'Belum ada perangkat aktif. Nyalakan notifikasi web dulu di perangkat ini.')
    sent = await push_user(u['id'], {'id': uid(), 'title': 'Uji notifikasi web', 'message': 'Notifikasi web CRM Maiharta sudah aktif di perangkat ini.', 'link': '/notifications'})
    if not sent: raise HTTPException(502, 'Notifikasi web gagal dikirim ke layanan push. Matikan lalu nyalakan lagi notifikasi web di perangkat ini.')
    return {'message': f'Notifikasi uji dikirim ke {sent} perangkat.'}


def _send(sub, payload):
    webpush(subscription_info={'endpoint': sub['endpoint'], 'keys': sub['keys']}, data=payload,
            vapid_private_key=os.environ['VAPID_PRIVATE_KEY'].strip(), vapid_claims={'sub': os.environ['VAPID_SUBJECT'].strip()}, ttl=86400, timeout=15)


async def _send_one(sub, payload):
    try:
        await asyncio.to_thread(_send, sub, payload)
        return 1
    except WebPushException as error:
        code = getattr(error.response, 'status_code', None)
        if code in (404, 410): await db.push_subscriptions.delete_many({'id': sub['id']})
        else: log.warning('Web push gagal (HTTP %s)', code)
    except Exception as error:
        log.warning('Web push gagal: %s', type(error).__name__)
    return 0


async def push_user(user_id, notification):
    if not configured(): return 0
    subs = await db.push_subscriptions.find({'user_id': user_id}, {'_id': 0}).to_list(20)
    payload = json.dumps({'id': notification['id'], 'title': notification.get('title') or 'CRM Maiharta',
                          'body': (notification.get('message') or '')[:300], 'url': notification.get('link') or '/notifications'}, ensure_ascii=False)
    return sum(await asyncio.gather(*(_send_one(s, payload) for s in subs)))


async def push_notifications(docs):
    for doc in docs:
        await push_user(doc['user_id'], doc)
