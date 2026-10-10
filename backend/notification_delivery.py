"""Preferences are re-read at delivery time so opt-outs take effect immediately."""
import os
import logging
import httpx
from core import db, uid, now
from mailer import send_email, email_configuration_error
from email_template import email_subject, email_html, email_text, whatsapp_text
from whatsapp import send_whatsapp, whatsapp_configuration_error, normalize_phone

log = logging.getLogger(__name__)
CHANNEL_LABELS = {'email': 'Email', 'whatsapp': 'WhatsApp'}
PAUSE_ID = 'notification_pause'


async def global_pause():
    row = await db.app_settings.find_one({'id': PAUSE_ID}, {'_id': 0}) or {}
    return {'email': bool(row.get('email')), 'whatsapp': bool(row.get('whatsapp'))}


def example_email(address):
    domain = address.rsplit('@', 1)[-1].lower()
    return domain.endswith(('.example', '.test', '.invalid', '.localhost')) or any(domain == d or domain.endswith('.' + d) for d in ['example.com', 'example.org', 'example.net'])


def http_reason(code, channel):
    target = 'Gmail' if channel == 'email' else 'WAHA'
    if code in (401, 403):
        return f'n8n menolak secret (HTTP {code}). Samakan N8N_WAHA_WEBHOOK_SECRET dengan credential Header Auth di n8n.'
    if code == 404:
        return 'Webhook n8n tidak ditemukan (HTTP 404). Pastikan workflow Active/Published dan URL memakai /webhook/.'
    if code == 422:
        return 'n8n menolak isi pesan (HTTP 422). Periksa node Validasi payload di n8n.'
    return f'n8n gagal meneruskan ke {target} (HTTP {code}). Buka n8n → Executions untuk detail.'


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
        delivery.update(status='failed', reason='Tidak dapat menghubungi n8n. Periksa URL webhook dan status service n8n.')
    return delivery


async def admin_contacts():
    admins = await db.users.find({'role': 'Admin', 'active': True}, {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'whatsapp_number': 1}).to_list(50)
    emails = {a['email'].lower(): a for a in admins if a.get('email') and not example_email(a['email'])}
    phones = {a['whatsapp_number']: a for a in admins if a.get('whatsapp_number')}
    env_email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    if env_email and not example_email(env_email): emails.setdefault(env_email, {'id': '', 'name': 'Admin'})
    try: env_phone = normalize_phone(os.environ.get('ADMIN_WHATSAPP_NUMBER', ''))
    except ValueError: env_phone = ''
    if env_phone: phones.setdefault(env_phone, {'id': '', 'name': 'Admin'})
    return emails, phones


async def alert_admins(notification, user, delivery, content):
    """Tell admins (email + WhatsApp) that a user notification failed, including its content."""
    label = CHANNEL_LABELS[delivery['channel']]
    recipient = delivery.get('recipient') or 'kontak kosong'
    alert = {'id': uid(), 'kind': 'peringatan', 'title': f"Notifikasi {label} gagal terkirim ke {user.get('name') or '-'}",
             'message': (f"Notifikasi {label} untuk {user.get('name') or '-'} ({recipient}) gagal terkirim.\nAlasan: {delivery.get('reason') or '-'}\n\n"
                         f"Judul: {notification.get('title') or '-'}\n\nIsi pesan:\n{content}"),
             'link': '/notifications', 'project_id': notification.get('project_id', ''), 'actor_name': 'Sistem', 'created_at': now()}
    emails, phones = await admin_contacts()
    paused = await global_pause()
    targets = [('email', address, admin) for address, admin in emails.items()] + [('whatsapp', phone, admin) for phone, admin in phones.items()]
    targets = [t for t in targets if not paused[t[0]]]
    for channel, address, admin in targets:
        record = {'id': uid(), 'notification_id': alert['id'], 'alert_for': notification['id'], 'user_id': admin['id'], 'channel': channel, 'provider': 'n8n_gmail' if channel == 'email' else 'n8n_waha', 'status': 'skipped', 'created_at': now(), 'reason': ''}
        problem = email_configuration_error() if channel == 'email' else whatsapp_configuration_error()
        if problem: record['reason'] = problem
        elif channel == 'email':
            await attempt(record, lambda: send_email(address, email_subject(alert), email_html(alert, admin), alert['id'], email_text(alert, admin)))
        else:
            await attempt(record, lambda: send_whatsapp(address, alert['id'], admin['id'], alert['project_id'], whatsapp_text(alert, admin)))
        await db.notification_deliveries.insert_one(record.copy())


async def deliver_notifications(notifications):
    paused = await global_pause()
    for notification in notifications:
        project_name = await project_title(notification.get('project_id'))
        force = notification.get('force_external')  # e.g. password reset: ignores pauses and preferences
        for channel in ['email', 'whatsapp']:
            user = await db.users.find_one({'id': notification['user_id'], 'active': True}, {'_id': 0})
            if not user: continue
            if not force and (paused[channel] or (user.get('notification_mute') or {}).get(channel) or not user.get('notification_preferences', {}).get(channel, channel == 'email')): continue
            delivery = {'id': uid(), 'notification_id': notification['id'], 'user_id': user['id'], 'channel': channel, 'provider': 'n8n_gmail' if channel == 'email' else 'n8n_waha', 'status': 'skipped', 'created_at': now(), 'reason': ''}
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
                await attempt(delivery, lambda: send_whatsapp(recipient, notification['id'], user['id'], notification.get('project_id', ''), content))
            await db.notification_deliveries.insert_one(delivery.copy())
            if delivery['status'] in ('failed', 'unknown'):
                try: await alert_admins(notification, user, {**delivery, 'recipient': recipient}, content)
                except Exception as error: log.warning('Peringatan admin gagal untuk notification_id=%s: %s', notification['id'], type(error).__name__)
