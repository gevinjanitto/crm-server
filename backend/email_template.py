"""Branded, table-based notification email (inline styles for Gmail/Outlook) plus plain-text twin."""
import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

KIND_LABELS = {'penugasan': 'Penugasan', 'maintenance': 'Maintenance', 'revisi': 'Revisi', 'tiket': 'Tiket',
               'akun': 'Akun', 'sambutan': 'Selamat Datang', 'peringatan': 'Peringatan', 'pengingat': 'Pengingat', 'project': 'Project', 'info': 'Info'}


def _app_url():
    return os.environ.get('APP_URL', '').strip().rstrip('/')


def _logo_url():
    """Logo email: EMAIL_LOGO_URL (CDN publik, disarankan) atau aset di APP_URL."""
    custom = os.environ.get('EMAIL_LOGO_URL', '').strip()
    return custom if custom.startswith('https://') else _app_url() + '/assets/logo-mark-white.png'


def _cta(notification):
    kind = notification.get('kind')
    return 'Masuk ke CRM Maiharta' if kind == 'akun' else 'Buka CRM Maiharta' if kind == 'sambutan' else 'Lihat di CRM'


def _link(notification):
    link = notification.get('link') or '/notifications'
    return _app_url() + (link if link.startswith('/') else '/notifications')


def _when(value):
    try:
        moment = datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Makassar'))
        return moment.strftime('%d/%m/%Y %H:%M') + ' WITA'
    except (TypeError, ValueError):
        return ''


def email_subject(notification):
    title = notification.get('title') or 'Pembaruan pekerjaan'
    return (title if 'CRM Maiharta' in title else 'CRM Maiharta: ' + title)[:150]


def _details(notification, project_name):
    rows = [('Project', project_name), ('Oleh', notification.get('actor_name') or 'Sistem'), ('Waktu', _when(notification.get('created_at')))]
    return [(k, v) for k, v in rows if v]


def email_text(notification, user, project_name=''):
    lines = [f"Halo {user.get('name') or ''},", '', notification.get('title') or '', notification.get('message') or '', '']
    lines += [f'{k}: {v}' for k, v in notification.get('credentials') or []]
    lines += [f'{k}: {v}' for k, v in _details(notification, project_name)]
    lines += ['', _cta(notification) + ': ' + _link(notification), '',
              'Email ini dikirim otomatis oleh CRM Maiharta karena notifikasi email aktif di akun Anda.',
              'Atur notifikasi: ' + _app_url() + '/settings', '', 'CV Maiharta - Denpasar, Bali']
    return '\n'.join(lines)


def whatsapp_text(notification, user, project_name=''):
    kind = KIND_LABELS.get(notification.get('kind', ''), (notification.get('kind') or 'Info').capitalize())
    lines = [f'*CRM Maiharta* | {kind}', '', f"Halo {user.get('name') or ''},", '',
             f"*{notification.get('title') or 'Pembaruan pekerjaan'}*", notification.get('whatsapp_message') or notification.get('message') or '', '']
    lines += [f'{k}: *{v}*' for k, v in _details(notification, project_name)]
    lines += ['', _cta(notification) + ':', _link(notification), '', '_Atur notifikasi: ' + _app_url() + '/settings_']
    return '\n'.join(lines)[:3900]


def email_html(notification, user, project_name=''):
    esc = html.escape
    base = _app_url()
    kind = KIND_LABELS.get(notification.get('kind', ''), (notification.get('kind') or 'Info').capitalize())
    details = ''.join(
        f'<tr><td style="padding:10px 0;border-top:1px solid #e6ebf2;font-size:13px;color:#6b7a90;width:96px">{esc(k)}</td>'
        f'<td style="padding:10px 0;border-top:1px solid #e6ebf2;font-size:13px;color:#14284b;font-weight:600">{esc(v)}</td></tr>'
        for k, v in _details(notification, project_name))
    credentials = ''.join(
        f'<tr><td style="padding:8px 14px;font-size:13px;color:#6b7a90;width:120px">{esc(k)}</td>'
        f'<td style="padding:8px 14px;font-size:15px;color:#14284b;font-weight:700;font-family:Consolas,Menlo,monospace">{esc(v)}</td></tr>'
        for k, v in notification.get('credentials') or [])
    if credentials:
        credentials = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#f2f6ff;border:1px solid #d6e2ff;border-radius:10px">{credentials}</table>'
    preheader = esc((notification.get('message') or '')[:140])
    welcome = notification.get('kind') == 'sambutan'
    logo = f'<img src="{esc(_logo_url())}" width="30" height="30" alt="MH" style="display:block;margin:5px auto;width:30px;height:30px;border:0;outline:none;text-decoration:none;color:#ffffff;font-size:14px;font-weight:800;line-height:30px;text-align:center">'
    cta = (f'<p style="margin:0;font-size:14px;line-height:1.7;color:#33445f">Alamat CRM: <a href="{esc(_link(notification))}" style="color:#2563eb;text-decoration:underline">{esc(_link(notification))}</a></p>' if welcome else
           f'<table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="border-radius:10px;background:#2563eb"><a href="{esc(_link(notification))}" style="display:inline-block;padding:13px 26px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px">{esc(_cta(notification))} &rarr;</a></td></tr></table>')
    signature = '<p style="margin:22px 0 0;font-size:14px;line-height:1.7;color:#33445f">Salam,<br><b>Tim CV Maiharta</b></p>' if welcome else ''
    return f'''<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{esc(email_subject(notification))}</title></head>
<body style="margin:0;padding:0;background:#eef2f8;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#14284b">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f8"><tr><td align="center" style="padding:32px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #dfe6f0">
<tr><td style="background:#123367;padding:22px 30px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle"><table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-table;vertical-align:middle"><tr><td width="40" height="40" align="center" valign="middle" style="width:40px;height:40px;border-radius:10px;background:#1f4f8f;font-size:14px;font-weight:800;color:#ffffff;line-height:40px;font-family:'Segoe UI',Helvetica,Arial,sans-serif">{logo or 'MH'}</td></tr></table>
<span style="display:inline-block;vertical-align:middle;margin-left:10px;font-size:16px;color:#ffffff;letter-spacing:.3px">CRM <b>maiharta</b></span></td>
<td align="right" style="vertical-align:middle"><span style="display:inline-block;padding:5px 12px;border-radius:999px;background:#1f4f8f;color:#bfe3ff;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase">{esc(kind)}</span></td>
</tr></table></td></tr>
<tr><td style="height:4px;background:#2bb3c0;line-height:4px;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:34px 30px 8px">
<p style="margin:0 0 6px;font-size:14px;color:#6b7a90">Halo {esc(user.get('name') or '')},</p>
<h1 style="margin:0 0 14px;font-size:22px;line-height:1.35;color:#14284b">{esc(notification.get('title') or '')}</h1>
<p style="margin:0 0 22px;font-size:15px;line-height:1.7;color:#33445f;white-space:pre-line">{esc(notification.get('message') or '')}</p>
{credentials}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 26px">{details}</table>
{cta}{signature}
</td></tr>
<tr><td style="padding:26px 30px 30px"><p style="margin:0;font-size:12px;line-height:1.7;color:#8592a6">Anda menerima email ini karena notifikasi email aktif di akun CRM Maiharta Anda. <a href="{esc(base)}/settings" style="color:#2563eb;text-decoration:underline">Atur notifikasi</a></p></td></tr>
<tr><td style="background:#f6f8fc;padding:16px 30px;border-top:1px solid #e6ebf2"><p style="margin:0;font-size:11px;color:#97a3b6">CV Maiharta &middot; Software House &middot; Denpasar, Bali</p></td></tr>
</table></td></tr></table></body></html>'''
