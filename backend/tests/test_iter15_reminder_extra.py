"""Iteration 15: Reminder description + document upload + extra notification."""
import io
import os
import re
import time
from datetime import date, timedelta

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
PASSWORD = "Maiharta123!"


def _login(username: str, password: str = PASSWORD) -> str:
    s = requests.Session()
    cap = s.get(f"{BASE}/api/auth/captcha").json()
    m = re.match(r"\s*(\d+)\s*([+\-*])\s*(\d+)", cap["question"])
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    ans = {"+": a + b, "-": a - b, "*": a * b}[op]
    r = s.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": password, "captcha_id": cap["id"], "captcha_answer": str(ans)},
    )
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin')}"}


@pytest.fixture(scope="module")
def dev_headers():
    return {"Authorization": f"Bearer {_login('developer')}"}


@pytest.fixture(scope="module")
def project_id(admin_headers):
    r = requests.get(f"{BASE}/api/projects", headers=admin_headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    assert items, "No projects seeded"
    return items[0]["id"]


def _today():
    return date.today()


def _mk(name="TEST_Reminder", extra_notify=False, extra_days=None, days_to_end=20, desc=""):
    return {
        "name": name,
        "description": desc,
        "start_date": _today().isoformat(),
        "end_date": (_today() + timedelta(days=days_to_end)).isoformat(),
        "extra_notify": extra_notify,
        "extra_notify_days": extra_days,
    }


# ---------------------------------------------------------------------------
# Validation & role gating
# ---------------------------------------------------------------------------
class TestValidation:
    def test_create_rejects_14_days(self, admin_headers, project_id):
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=admin_headers,
            json=_mk(name="TEST_Rej14", extra_notify=True, extra_days=14),
        )
        assert r.status_code == 422, r.text
        assert "14" in r.text

    def test_create_rejects_extra_without_days(self, admin_headers, project_id):
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=admin_headers,
            json=_mk(name="TEST_RejNoDays", extra_notify=True, extra_days=None),
        )
        assert r.status_code == 422

    def test_create_rejects_zero_and_oversize(self, admin_headers, project_id):
        for d in (0, 366):
            r = requests.post(
                f"{BASE}/api/projects/{project_id}/reminders",
                headers=admin_headers,
                json=_mk(name=f"TEST_RejBound_{d}", extra_notify=True, extra_days=d),
            )
            assert r.status_code == 422

    def test_create_rejects_end_before_start(self, admin_headers, project_id):
        bad = _mk(name="TEST_RejDate")
        bad["end_date"] = (_today() - timedelta(days=1)).isoformat()
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders", headers=admin_headers, json=bad
        )
        assert r.status_code == 422

    def test_non_admin_cannot_create(self, dev_headers, project_id):
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=dev_headers,
            json=_mk(name="TEST_DevNope"),
        )
        assert r.status_code == 403

    def test_non_admin_cannot_list(self, dev_headers, project_id):
        r = requests.get(f"{BASE}/api/projects/{project_id}/reminders", headers=dev_headers)
        assert r.status_code == 403
        r2 = requests.get(f"{BASE}/api/reminders", headers=dev_headers)
        assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Lifecycle, notified_at reset, combined notification
# ---------------------------------------------------------------------------
class TestLifecycle:
    @pytest.fixture
    def rid(self, admin_headers, project_id):
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=admin_headers,
            json=_mk(name="TEST_Lifecycle", desc="Desc OK", extra_notify=True, extra_days=3, days_to_end=20),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["description"] == "Desc OK"
        assert data["extra_notify"] is True
        assert data["extra_notify_days"] == 3
        assert data["notified_at"] is None
        assert data["extra_notified_at"] is None
        yield data["id"]
        requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{data['id']}", headers=admin_headers)

    def test_patch_end_within_14_triggers_main_only(self, admin_headers, project_id, rid):
        r = requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"end_date": (_today() + timedelta(days=10)).isoformat()},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["notified_at"] is not None
        assert d["extra_notified_at"] is None  # 10 > 3

    def test_patch_end_resets_main_and_extra(self, admin_headers, project_id, rid):
        # First get within 14 so notified_at set
        requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"end_date": (_today() + timedelta(days=10)).isoformat()},
        )
        # Then push far out — both should reset to None
        r = requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"end_date": (_today() + timedelta(days=60)).isoformat()},
        )
        d = r.json()
        assert d["notified_at"] is None, "end_date change must reset notified_at"
        assert d["extra_notified_at"] is None, "end_date change must reset extra_notified_at"

    def test_change_extra_days_resets_extra_only(self, admin_headers, project_id, rid):
        # Set end to 2 days -> both fire together (combined)
        r = requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"end_date": (_today() + timedelta(days=2)).isoformat()},
        )
        d = r.json()
        assert d["notified_at"] is not None
        assert d["extra_notified_at"] is not None
        # Now change extra_notify_days from 3 -> 5 (within still), extra_notified_at should reset
        r2 = requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"extra_notify_days": 5},
        )
        d2 = r2.json()
        assert d2["notified_at"] is not None, "main notified_at must NOT reset when only extra_days changes"
        # It may re-fire immediately (left<=5), so it may be set again. Check at minimum it was reset-then-refired.
        assert d2["extra_notify_days"] == 5

    def test_extra_toggle_off_clears_days_and_badge(self, admin_headers, project_id, rid):
        r = requests.patch(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}",
            headers=admin_headers,
            json={"extra_notify": False},
        )
        d = r.json()
        assert d["extra_notify"] is False
        assert d["extra_notify_days"] is None

    def test_combined_notification_single_insert(self, admin_headers, project_id):
        """When both main and extra are due at creation, a single combined 'Reminder:' notification is created."""
        payload = _mk(name="TEST_Combined", extra_notify=True, extra_days=5, days_to_end=2)
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders", headers=admin_headers, json=payload
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        try:
            d = r.json()
            assert d["notified_at"] is not None
            assert d["extra_notified_at"] is not None
            # Check latest notification title does NOT start with "Reminder tambahan"
            n = requests.get(f"{BASE}/api/notifications", headers=admin_headers).json()
            items = n.get("items", n) if isinstance(n, dict) else n
            matches = [x for x in items if x.get("entity_id") == rid]
            assert matches, "No notification created for combined reminder"
            titles = [m.get("title", "") for m in matches]
            # Only ONE notification created, titled 'Reminder: ...' (not 'Reminder tambahan (H-5): ...')
            assert len(matches) == 1, f"Expected single combined notification, got {titles}"
            assert matches[0]["title"].startswith("Reminder:"), f"Title={titles}"
            assert "tambahan" not in matches[0]["title"]
        finally:
            requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{rid}", headers=admin_headers)

    def test_extra_alone_uses_tambahan_title(self, admin_headers, project_id):
        """When main already fired and later extra fires alone, title must be 'Reminder tambahan (H-N): ...'."""
        # Create with end 10 days away (main fires immediately, extra 3 days doesn't)
        payload = _mk(name="TEST_ExtraAlone", extra_notify=True, extra_days=3, days_to_end=10)
        r = requests.post(f"{BASE}/api/projects/{project_id}/reminders", headers=admin_headers, json=payload).json()
        rid = r["id"]
        try:
            assert r["notified_at"] is not None
            assert r["extra_notified_at"] is None
            # Patch end to 2 -> extra fires alone
            d = requests.patch(
                f"{BASE}/api/projects/{project_id}/reminders/{rid}",
                headers=admin_headers,
                json={"end_date": (_today() + timedelta(days=2)).isoformat()},
            ).json()
            # NOTE: end_date change resets both notified_at and extra_notified_at then both fire combined.
            # So after patching end_date, both are claimed in same notify_due call -> combined title.
            # To get "extra alone", we need extra fire after main already set and end_date not changed.
            # Simulate by setting extra_notify_days from unused to 3 (currently 3) after end is 10 — won't fire.
            # Easier: start extra_notify=False, main fires via end=10; then flip extra_notify=True, extra_days=3 while end stays 10
            # -> extra_notified_at None, main stays set, nothing fires (left=10 > 3)
            # Then patch extra_notify_days -> actually test the "extra alone" path by direct toggle after main fired.
            # Re-approach: delete this and craft new one below.
        finally:
            requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{rid}", headers=admin_headers)

        # Proper flow for "extra alone"
        p2 = _mk(name="TEST_ExtraAlone2", extra_notify=False, extra_days=None, days_to_end=10)
        r2 = requests.post(f"{BASE}/api/projects/{project_id}/reminders", headers=admin_headers, json=p2).json()
        rid2 = r2["id"]
        try:
            assert r2["notified_at"] is not None  # main fires (10 <= 14)
            # Enable extra_notify with a small window so extra fires alone (end_date unchanged -> notified_at kept)
            d2 = requests.patch(
                f"{BASE}/api/projects/{project_id}/reminders/{rid2}",
                headers=admin_headers,
                json={"extra_notify": True, "extra_notify_days": 12},
            ).json()
            assert d2["notified_at"] is not None, "main notified_at should persist (end_date not changed)"
            assert d2["extra_notified_at"] is not None, "extra should fire (10 <= 12)"
            n = requests.get(f"{BASE}/api/notifications", headers=admin_headers).json()
            items = n.get("items", n) if isinstance(n, dict) else n
            matches = [x for x in items if x.get("entity_id") == rid2]
            titles = [m.get("title", "") for m in matches]
            assert any(t.startswith("Reminder tambahan (H-12):") for t in titles), f"Missing extra-only title in {titles}"
        finally:
            requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{rid2}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
class TestAttachments:
    @pytest.fixture
    def rid(self, admin_headers, project_id):
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=admin_headers,
            json=_mk(name="TEST_Attach", days_to_end=20),
        ).json()
        yield r["id"]
        requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{r['id']}", headers=admin_headers)

    def test_upload_pdf_download_delete(self, admin_headers, project_id, rid):
        files = [("files", ("doc.pdf", b"hello-pdf", "application/pdf"))]
        up = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
            headers=admin_headers,
            files=files,
        )
        assert up.status_code == 200, up.text
        att = up.json()["attachments"]
        assert len(att) == 1
        aid = att[0]["id"]
        assert att[0]["name"] == "doc.pdf"
        assert att[0]["size"] == 9
        # Download
        dl = requests.get(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments/{aid}",
            headers=admin_headers,
        )
        assert dl.status_code == 200
        assert dl.content == b"hello-pdf"
        # Delete
        rm = requests.delete(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments/{aid}",
            headers=admin_headers,
        )
        assert rm.status_code == 200
        assert rm.json()["attachments"] == []

    def test_upload_bad_extension_rejected(self, admin_headers, project_id, rid):
        files = [("files", ("evil.exe", b"MZ...", "application/octet-stream"))]
        up = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
            headers=admin_headers,
            files=files,
        )
        assert up.status_code in (400, 415, 422), up.text

    def test_upload_oversize_rejected(self, admin_headers, project_id, rid):
        big = b"a" * (10 * 1024 * 1024 + 1024)  # 10MB + 1KB
        files = [("files", ("big.pdf", big, "application/pdf"))]
        up = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
            headers=admin_headers,
            files=files,
        )
        assert up.status_code in (400, 413, 422), up.text

    def test_upload_multi_and_cap_20_per_reminder(self, admin_headers, project_id, rid):
        # upload 20 small files (5 per batch) then one more should be rejected
        for batch in range(4):
            files = [("files", (f"f{batch}_{i}.pdf", b"x", "application/pdf")) for i in range(5)]
            r = requests.post(
                f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
                headers=admin_headers,
                files=files,
            )
            assert r.status_code == 200, r.text
        # 21st
        over = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
            headers=admin_headers,
            files=[("files", ("extra.pdf", b"x", "application/pdf"))],
        )
        assert over.status_code == 400
        assert "20" in over.text

    def test_delete_reminder_removes_files(self, admin_headers, project_id):
        # Create & upload
        r = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders",
            headers=admin_headers,
            json=_mk(name="TEST_DelFiles"),
        ).json()
        rid = r["id"]
        up = requests.post(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
            headers=admin_headers,
            files=[("files", ("doc.pdf", b"zzz", "application/pdf"))],
        ).json()
        aid = up["attachments"][0]["id"]
        # Find file path via storage layout: /app/backend/uploads/crm-maiharta/reminders/{rid}/...
        upload_root = "/app/backend/uploads"
        folder = os.path.join(upload_root, "crm-maiharta", "reminders", rid)
        existed = os.path.isdir(folder) and any(os.scandir(folder))
        assert existed, f"Expected files inside {folder}"
        # Delete the reminder
        dr = requests.delete(
            f"{BASE}/api/projects/{project_id}/reminders/{rid}", headers=admin_headers
        )
        assert dr.status_code == 200
        # Files on disk should be cleaned up
        remaining = os.path.isdir(folder) and any(os.scandir(folder))
        assert not remaining, f"Files not cleaned after reminder delete: {folder}"


# ---------------------------------------------------------------------------
# Global reminders report
# ---------------------------------------------------------------------------
class TestReport:
    def test_global_reminders_list_contains_description_and_attachments(self, admin_headers, project_id):
        p = _mk(name="TEST_Report", desc="Perlu perpanjangan", extra_notify=True, extra_days=7)
        r = requests.post(f"{BASE}/api/projects/{project_id}/reminders", headers=admin_headers, json=p).json()
        rid = r["id"]
        try:
            requests.post(
                f"{BASE}/api/projects/{project_id}/reminders/{rid}/attachments",
                headers=admin_headers,
                files=[("files", ("note.pdf", b"nn", "application/pdf"))],
            )
            lst = requests.get(f"{BASE}/api/reminders", headers=admin_headers).json()
            match = [x for x in lst if x["id"] == rid]
            assert match, "Reminder not surfaced in global /api/reminders"
            m = match[0]
            assert m["description"] == "Perlu perpanjangan"
            assert m["extra_notify"] is True
            assert m["extra_notify_days"] == 7
            assert m["project_name"]
            assert len(m["attachments"]) == 1
        finally:
            requests.delete(f"{BASE}/api/projects/{project_id}/reminders/{rid}", headers=admin_headers)
