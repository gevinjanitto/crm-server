"""Iteration 14: notification pause/mute + reset-password + delivery logic."""
import os, re, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

# ---------- auth helpers ----------
def _captcha_answer(sess):
    cap = sess.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = {"+": a+b, "-": a-b, "*": a*b}[op]
    return cap["id"], str(ans)

def login(username, password):
    s = requests.Session()
    cid, ans = _captcha_answer(s)
    r = s.post(f"{BASE}/api/auth/login", json={
        "username": username, "password": password,
        "captcha_id": cid, "captcha_answer": ans,
    })
    r.raise_for_status()
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    return s, data

@pytest.fixture(scope="module")
def admin():
    s, d = login("admin", "Preview123!")
    return s, d

@pytest.fixture(scope="module")
def accounting():
    s, d = login("accounting", "Preview123!")
    return s, d

@pytest.fixture(scope="module")
def users_by_name(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/users")
    assert r.status_code == 200
    return {u["username"]: u for u in r.json()}


# ---------- 1. Global notification pause ----------
class TestGlobalPause:
    def test_get_pause_default(self, admin):
        s, _ = admin
        r = s.get(f"{BASE}/api/admin/notification-pause")
        assert r.status_code == 200
        data = r.json()
        assert "email" in data and "whatsapp" in data

    def test_set_pause_and_persist(self, admin):
        s, _ = admin
        r = s.put(f"{BASE}/api/admin/notification-pause", json={"email": True, "whatsapp": True})
        assert r.status_code == 200
        g = s.get(f"{BASE}/api/admin/notification-pause").json()
        assert g["email"] is True and g["whatsapp"] is True

    def test_restore_pause_off(self, admin):
        s, _ = admin
        r = s.put(f"{BASE}/api/admin/notification-pause", json={"email": False, "whatsapp": False})
        assert r.status_code == 200
        g = s.get(f"{BASE}/api/admin/notification-pause").json()
        assert g["email"] is False and g["whatsapp"] is False

    def test_non_admin_forbidden(self, accounting):
        s, _ = accounting
        r = s.get(f"{BASE}/api/admin/notification-pause")
        assert r.status_code == 403
        r = s.put(f"{BASE}/api/admin/notification-pause", json={"email": True, "whatsapp": False})
        assert r.status_code == 403


# ---------- 2. Per-user mute ----------
class TestUserMute:
    def test_mute_persists(self, admin, users_by_name):
        s, _ = admin
        uid = users_by_name["accounting"]["id"]
        r = s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": True, "whatsapp": False})
        assert r.status_code == 200
        # Verify via GET /api/users
        all_users = s.get(f"{BASE}/api/users").json()
        acc = next(u for u in all_users if u["id"] == uid)
        assert acc.get("notification_mute", {}).get("email") is True
        assert acc.get("notification_mute", {}).get("whatsapp") is False

    def test_mute_restore(self, admin, users_by_name):
        s, _ = admin
        uid = users_by_name["accounting"]["id"]
        r = s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": False, "whatsapp": False})
        assert r.status_code == 200
        all_users = s.get(f"{BASE}/api/users").json()
        acc = next(u for u in all_users if u["id"] == uid)
        assert acc.get("notification_mute", {}).get("email") is False

    def test_mute_non_admin_forbidden(self, accounting, users_by_name):
        s, _ = accounting
        uid = users_by_name["accounting"]["id"]
        r = s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": True, "whatsapp": True})
        assert r.status_code == 403


# ---------- 3. Reset password ----------
class TestResetPassword:
    def test_reset_self_rejected(self, admin):
        s, d = admin
        r = s.post(f"{BASE}/api/users/{d['user']['id']}/reset-password")
        assert r.status_code == 400

    def test_reset_non_admin_forbidden(self, accounting, users_by_name):
        s, _ = accounting
        uid = users_by_name["adminproject"]["id"]
        r = s.post(f"{BASE}/api/users/{uid}/reset-password")
        assert r.status_code == 403

    def test_reset_flow_e2e(self, admin, users_by_name):
        """Reset accounting; old token invalidated; login with 12345678; must_change_password true;
        force_external deliveries created despite global pause + user mute; then restore password."""
        s, _ = admin
        acc = users_by_name["accounting"]
        uid = acc["id"]

        # Login as accounting to grab an old token
        old_sess, old_data = login("accounting", "Preview123!")

        # Turn ON global pause + mute to prove force_external bypass
        s.put(f"{BASE}/api/admin/notification-pause", json={"email": True, "whatsapp": True})
        s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": True, "whatsapp": True})

        # Reset
        r = s.post(f"{BASE}/api/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        rj = r.json()
        assert rj["default_password"] == "12345678"
        assert "message" in rj and "channels" in rj

        # Old token should be invalidated
        r_old = old_sess.get(f"{BASE}/api/auth/me")
        assert r_old.status_code == 401, f"Old session not invalidated: {r_old.status_code}"

        # Login with 12345678
        new_sess, new_data = login("accounting", "12345678")
        assert new_data["user"].get("must_change_password") is True

        # Check deliveries exist for both channels for this user (force_external path)
        deliveries = new_sess.get(f"{BASE}/api/account/notifications/deliveries").json()
        # recent deliveries for this reset event
        recent = deliveries if isinstance(deliveries, list) else deliveries.get("items", [])
        channels_found = {d.get("channel") for d in recent[:20]}
        assert "email" in channels_found, f"email delivery missing: {channels_found}"
        assert "whatsapp" in channels_found, f"whatsapp delivery missing: {channels_found}"

        # Restore pause/mute off
        s.put(f"{BASE}/api/admin/notification-pause", json={"email": False, "whatsapp": False})
        s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": False, "whatsapp": False})

        # Restore password back to Preview123! via admin PATCH
        rp = s.patch(f"{BASE}/api/users/{uid}", json={"new_password": "Preview123!"})
        assert rp.status_code == 200, rp.text
        # Verify we can log in with Preview123! again (must_change_password may still be true, that's fine)
        try:
            login("accounting", "Preview123!")
        except Exception as e:
            pytest.fail(f"Could not restore accounting login: {e}")


# ---------- 4. Delivery logic: mute suppresses delivery row ----------
class TestDeliveryMute:
    def test_test_notification_respects_mute(self, admin, users_by_name):
        """When user email mute true -> no email delivery row for the test notification.
        In-app notification should still exist."""
        s_admin, _ = admin
        uid = users_by_name["accounting"]["id"]
        # Ensure mute email ON, whatsapp OFF
        s_admin.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": True, "whatsapp": False})
        s_admin.put(f"{BASE}/api/admin/notification-pause", json={"email": False, "whatsapp": False})

        s_acc, _ = login("accounting", "Preview123!")
        # trigger (may be rate-limited 60s)
        r = s_acc.post(f"{BASE}/api/account/notifications/test")
        if r.status_code == 429:
            pytest.skip("Rate-limited; skip delivery check")
        assert r.status_code in (200, 201), r.text
        time.sleep(2)
        deliveries = s_acc.get(f"{BASE}/api/account/notifications/deliveries").json()
        items = deliveries if isinstance(deliveries, list) else deliveries.get("items", [])
        # look at most recent delivery rows (for the just-triggered notification)
        recent = items[:10]
        channels = [d.get("channel") for d in recent]
        # email suppressed for muted user, whatsapp may appear if preference enabled; main check: no email row for the just-created notif
        # weak assertion: within last few, email count should be low (0 for the newest notification)
        # Fetch the newest notification id from /api/notifications
        notifs = s_acc.get(f"{BASE}/api/notifications").json()
        notif_items = notifs if isinstance(notifs, list) else notifs.get("items", [])
        assert notif_items, "No notifications returned"
        newest_id = notif_items[0].get("id")
        new_delivs = [d for d in items if d.get("notification_id") == newest_id]
        email_rows = [d for d in new_delivs if d.get("channel") == "email"]
        assert len(email_rows) == 0, f"Expected no email delivery row for muted channel, got {email_rows}"

    def test_restore_mute_off(self, admin, users_by_name):
        s, _ = admin
        uid = users_by_name["accounting"]["id"]
        s.put(f"{BASE}/api/users/{uid}/notification-mute", json={"email": False, "whatsapp": False})
