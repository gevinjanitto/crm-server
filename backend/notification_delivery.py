"""Preferences are re-read at delivery time so opt-outs take effect immediately."""
import logging
import httpx
from core import db, uid, now
from mailer import send_email, email_configuration_error
from email_template import email_subject, email_html, email_text, whatsapp_text
from whatsapp import send_whatsapp, whatsapp_configuration_error
from whatsapp_template import SETTING_ID as WA_TEMPLATE_ID, TEMPLATE_BODY, template_variables

log = logging.getLogger(__name__)
CHANNEL_LABELS = {'email': 'Email', 'whatsapp': 'WhatsApp'}
PAUSE_ID = 'notification_pause'


async def global_pause():
    row = await db.app_settings.find_one({'id': PAUSE_ID}, {'_id': 0}) or {}
    result = {}
    for channel in ['email', 'whatsapp']:
        result[channel] = channel_muted(row, channel)
        result[f'{channel}_until'] = row.get(f'{channel}_until') if result[channel] else None
    return result


def channel_muted(state, channel):
    """Pause/mute is active only until its `<channel>_until` time (if set); afterwards it lapses automatically."""
    state = state or {}
    if not state.get(channel): return False
    until = state.get(f'{channel}_until')
    return not until or until > now()


def example_email(address):
    domain = address.rsplit('@', 1)[-1].lower()
    return domain.endswith(('.example', '.test', '.invalid', '.localhost')) or any(domain == d or domain.endswith('.' + d) for d in ['example.com', 'example.org', 'example.net'])


def http_reason(code, channel):
    target = 'Gmail API' if channel == 'email' else 'Twilio WhatsApp'
    if code in (401, 403):
        return f'{target} menolak kredensial (HTTP {code}). Periksa token/izin di pengaturan server.'
    if code == 404:
        return f'Endpoint {target} tidak ditemukan (HTTP 404). Periksa URL di pengaturan server.'
    if code in (400, 422):
        return f'{target} menolak isi pesan (HTTP {code}). Periksa format nomor/template.'
    if code == 429:
        return f'{target} membatasi jumlah pengiriman (HTTP 429). Coba lagi nanti.'
    return f'{target} gagal mengirim (HTTP {code}).'


async def project_title(project_id):
    if not project_id: return ''
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
    return project['name'] if project else ''


async def attempt(delivery, send):
    """Run one provider call and record the outcome on the delivery dict."""
    channel, nid = delivery['channel'], delivery['notification_id']
    try:
        provider_id = await send()
        if not provider_id: raise ValueError('Provider tidak mengembalikan ID pesan.')
        delivery.update(status='accepted', provider_id=provider_id)
    except httpx.TimeoutException:
        delivery.update(status='unknown', reason='Layanan belum memberi jawaban. Periksa log sebelum mengirim ulang agar tidak ganda.')
    except httpx.HTTPStatusError as error:
        code = error.response.status_code
        log.warning('Pengiriman %s gagal HTTP %s untuk notification_id=%s', channel, code, nid)
        delivery.update(status='failed', reason=http_reason(code, channel))
    except ValueError as error:
        log.warning('Pengiriman %s ditolak untuk notification_id=%s: %s', channel, nid, error)
        delivery.update(status='failed', reason=str(error))
    except Exception as error:
        log.warning('Pengiriman %s gagal untuk notification_id=%s: %s', channel, nid, type(error).__name__)
        delivery.update(status='failed', reason='Tidak dapat menghubungi layanan pengiriman. Periksa koneksi server dan konfigurasi API.')
    return delivery


IMPORTANT_KINDS = {'pengingat', 'akun', 'sambutan'}


def is_important(notification):
    return notification.get('kind') in IMPORTANT_KINDS


async def already_sent(notification_id, channel):
    return bool(await db.notification_deliveries.find_one({'notification_id': notification_id, 'channel': channel, 'status': {'$in': ['accepted', 'unknown']}}, {'_id': 0, 'id': 1}))


async def queue_notification(notification, channel):
    """Important notifications blocked by a pause wait here and are sent exactly once when the pause ends."""
    qid = f"{notification['id']}:{channel}"
    await db.notification_queue.update_one({'id': qid}, {'$setOnInsert': {'id': qid, 'notification': notification, 'notification_id': notification['id'], 'user_id': notification['user_id'], 'channel': channel, 'status': 'pending', 'created_at': now()}}, upsert=True)


async def approved_template_sid():
    row = await db.app_settings.find_one({'id': WA_TEMPLATE_ID}, {'_id': 0}) or {}
    return row.get('content_sid', '') if row.get('status') == 'approved' and row.get('body') == TEMPLATE_BODY else ''


async def deliver_channel(notification, channel, user, project_name, force=False):
    if await already_sent(notification['id'], channel): return
    delivery = {'id': uid(), 'notification_id': notification['id'], 'user_id': user['id'], 'channel': channel, 'provider': 'gmail_api' if channel == 'email' else 'whatsapp_api', 'status': 'skipped', 'created_at': now(), 'reason': ''}
    problem = email_configuration_error() if channel == 'email' else whatsapp_configuration_error()
    recipient = user.get('email') if channel == 'email' else user.get('whatsapp_number')
    content = email_text(notification, user, project_name) if channel == 'email' else whatsapp_text(notification, user, project_name)
    if problem: delivery['reason'] = problem
    elif not recipient: delivery['reason'] = 'Kontak akun belum terdaftar.'
    elif channel == 'email' and example_email(recipient):
        delivery['reason'] = 'Alamat contoh tidak dikirim.'
    elif channel == 'whatsapp' and not force and not user.get('whatsapp_opt_in_at'):
        delivery['reason'] = 'Persetujuan WhatsApp belum tercatat.'
    elif channel == 'email':
        await attempt(delivery, lambda: send_email(recipient, email_subject(notification), email_html(notification, user, project_name), notification['id'], content))
    else:
        sid = await approved_template_sid()
        variables = template_variables(notification, user, project_name) if sid else None
        await attempt(delivery, lambda: send_whatsapp(recipient, notification['id'], user['id'], notification.get('project_id', ''), content, sid, variables))
    await db.notification_deliveries.insert_one(delivery.copy())


async def deliver_notifications(notifications):
    paused = await global_pause()
    for notification in notifications:
        project_name = await project_title(notification.get('project_id'))
        force = notification.get('force_external')  # e.g. password reset: ignores pauses and preferences
        for channel in ['email', 'whatsapp']:
            user = await db.users.find_one({'id': notification['user_id'], 'active': True}, {'_id': 0})
            if not user: continue
            if not force and not user.get('notification_preferences', {}).get(channel, channel == 'email'): continue
            if not force and (paused[channel] or channel_muted(user.get('notification_mute'), channel)):
                if is_important(notification): await queue_notification(notification, channel)
                continue
            await deliver_channel(notification, channel, user, project_name, force)


async def flush_notification_queue():
    """Send queued important notifications whose pause has ended. Each item is claimed atomically so it goes out once."""
    pending = await db.notification_queue.find({'status': 'pending'}, {'_id': 0}).sort('created_at', 1).to_list(1000)
    if not pending: return 0
    paused, sent = await global_pause(), 0
    for item in pending:
        channel = item['channel']
        user = await db.users.find_one({'id': item['user_id'], 'active': True}, {'_id': 0})
        if not user or not user.get('notification_preferences', {}).get(channel, channel == 'email'):
            await db.notification_queue.update_one({'id': item['id']}, {'$set': {'status': 'dropped', 'finished_at': now()}}); continue
        if paused[channel] or channel_muted(user.get('notification_mute'), channel): continue
        claimed = await db.notification_queue.update_one({'id': item['id'], 'status': 'pending'}, {'$set': {'status': 'sending', 'claimed_at': now()}})
        if not claimed.modified_count: continue
        try:
            await deliver_channel(item['notification'], channel, user, await project_title(item['notification'].get('project_id')))
            await db.notification_queue.update_one({'id': item['id']}, {'$set': {'status': 'sent', 'finished_at': now()}}); sent += 1
        except Exception:
            log.exception('Antrean notifikasi gagal untuk %s', item['id'])
            await db.notification_queue.update_one({'id': item['id']}, {'$set': {'status': 'pending'}})
    return sent
