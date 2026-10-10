"""Tests for email content (subject/html) and panduan-notifikasi guide."""
import os
import re
import sys
import pytest
import requests

sys.path.insert(0, '/app/backend')

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL')
            or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split('\n')[0]).rstrip('/')
PWD = 'Maiharta2026!'


# ---------------- Unit tests: email_subject / email_html / _assert_safe_email ----------------

from notification_delivery import email_subject, email_html  # noqa: E402
from mailer import _assert_safe_email  # noqa: E402


class TestEmailSubject:
    def test_subject_prefix_and_title(self):
        s = email_subject({'title': 'Tiket baru dibuat'})
        assert s == 'CRM Maiharta: Tiket baru dibuat'

    def test_subject_fallback_title(self):
        s = email_subject({'title': ''})
        assert s.startswith('CRM Maiharta:')
        assert 'Pembaruan pekerjaan' in s

    def test_subject_max_150(self):
        s = email_subject({'title': 'A' * 500})
        assert len(s) <= 150

    def test_subject_fixed_phrase_removed(self):
        # must NOT be the old generic subject
        assert email_subject({'title': 'Foo'}) != 'Pembaruan CRM Maiharta'


class TestEmailHtml:
    user = {'name': 'Admin Test', 'email': 'admin@example.com'}

    def test_contains_escaped_user_title_message_actor(self):
        notif = {'title': 'Tiket Baru', 'message': 'Pesan tes', 'actor_name': 'Budi', 'link': '/tickets/1'}
        html = email_html(notif, self.user)
        assert 'Admin Test' in html
        assert 'Tiket Baru' in html
        assert 'Pesan tes' in html
        assert 'Budi' in html
        assert 'Lihat di CRM' in html

    def test_escapes_html_special_chars(self):
        notif = {'title': '<script>alert(1)</script>', 'message': '<b>x</b>', 'actor_name': '<i>a</i>', 'link': '/x'}
        html = email_html(notif, {'name': '<img>', 'email': 'a@b.co'})
        # Raw tags must not appear
        assert '<script>' not in html
        assert '<b>x</b>' not in html
        assert '<i>a</i>' not in html
        # Must contain escaped versions
        assert '&lt;script&gt;' in html
        assert '&lt;b&gt;x&lt;/b&gt;' in html

    def test_no_phishing_phrases(self):
        notif = {'title': 'X', 'message': 'Y', 'actor_name': 'Z', 'link': '/a'}
        html = email_html(notif, self.user).lower()
        assert 'password' not in html
        assert 'kode verifikasi' not in html
        assert 'kata sandi' not in html

    def test_button_link_uses_app_url_https(self):
        notif = {'title': 'X', 'message': 'Y', 'actor_name': 'Z', 'link': '/notifications/42'}
        html = email_html(notif, self.user)
        app_url = os.environ.get('APP_URL', '').rstrip('/')
        assert app_url.startswith('https://'), f"APP_URL must be https for this test, got {app_url!r}"
        assert f'href="{app_url}/notifications/42"' in html

    def test_passes_assert_safe_email(self):
        notif = {'title': 'Hello', 'message': 'World', 'actor_name': 'Bot', 'link': '/x'}
        subject = email_subject(notif)
        html = email_html(notif, self.user)
        # Should not raise
        _assert_safe_email(subject, html)

    def test_passes_safe_email_with_escaped_script(self):
        notif = {'title': '<script>alert(1)</script>', 'message': 'ok', 'actor_name': 'Bot', 'link': '/x'}
        subject = email_subject(notif)
        html = email_html(notif, self.user)
        _assert_safe_email(subject, html)  # should not raise


# ---------------- API integration test (rate-limited, at most once) ----------------

def _login(username):
    c = requests.get(f"{BASE_URL}/api/auth/captcha", timeout=15).json()
    q = c['question'].split()
    ans = int(q[0]) + int(q[2]) if q[1] == '+' else int(q[0]) - int(q[2])
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": username, "password": PWD,
        "captcha_id": c['id'], "captcha_answer": str(ans)
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()['token']


@pytest.fixture(scope='module')
def admin_h():
    return {"Authorization": f"Bearer {_login('admin')}"}


class TestNotificationTestEndpoint:
    def test_post_test_notification_once(self, admin_h):
        """Call /api/account/notifications/test AT MOST ONCE (real email -> rate limited 1/min)."""
        r = requests.post(f"{BASE_URL}/api/account/notifications/test", headers=admin_h, timeout=60)
        if r.status_code == 429:
            pytest.skip(f"Rate-limited (previous test within 1 min): {r.text}")
        assert r.status_code == 200, r.text
        msg = r.json().get('message', '')
        assert 'diterima layanan' in msg, msg
        # Expect at least 1 accepted delivery
        m = re.search(r'(\d+) diterima layanan', msg)
        assert m and int(m.group(1)) >= 1, f"Expected >=1 accepted: {msg}"

    def test_deliveries_list_shows_accepted(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/account/notifications/deliveries", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        deliveries = r.json()
        assert isinstance(deliveries, list) and len(deliveries) >= 1
        # Most recent (sorted desc by created_at) should include an accepted email
        statuses = [d.get('status') for d in deliveries[:5]]
        assert 'accepted' in statuses, f"No accepted delivery in top 5: {deliveries[:5]}"


# ---------------- Guide content tests ----------------

class TestPanduanGuide:
    @pytest.fixture(scope='class')
    def guide_text(self):
        r = requests.get(f"{BASE_URL}/panduan-notifikasi.md", timeout=15)
        assert r.status_code == 200
        return r.text

    def test_section_3_1_enter_not_click_link(self, guide_text):
        # Section 3.1 must mention devlikeapro/waha:latest + press Enter and warn NOT to click hub.docker.com link
        assert 'devlikeapro/waha:latest' in guide_text
        assert 'Enter' in guide_text
        assert 'hub.docker.com' in guide_text
        assert 'Jangan klik' in guide_text or 'jangan klik' in guide_text.lower()

    def test_spam_section_present(self, guide_text):
        assert 'Spam' in guide_text or 'spam' in guide_text.lower()
        # Must mention concrete steps
        assert 'Laporkan bukan spam' in guide_text
        assert 'Tambahkan ke kontak' in guide_text or 'tambahkan ke kontak' in guide_text.lower()
        assert 'Jangan pernah kirim ke Spam' in guide_text

    def test_no_resend_product_mention(self, guide_text):
        # "RESEND_API_KEY" listed in migration-cleanup block is OK; no "Resend" as a product
        assert 'Resend' not in guide_text
        # Also: no instruction to use Resend as provider
        assert 'via Resend' not in guide_text
        assert 'resend.com' not in guide_text.lower()
