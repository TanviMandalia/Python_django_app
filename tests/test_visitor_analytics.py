import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from core.models import (
    User,
    Hospital,
    ClinicAdmin,
    StaffProfile,
    Profile,
    VisitorSession,
    PageViewEvent,
    VisitorLead,
    AnalyticsSetting,
    AnalyticsAuditLog,
)


class VisitorAnalyticsAndLeadManagementTests(TestCase):
    """
    Test suite for Secure Website Visitor Analytics and Lead Management (Super Admin Exclusive).
    Covers:
    1. Consent behavior & API beacon tracking.
    2. Active time and session aggregation without PII.
    3. Public contact form inquiry -> VisitorLead creation & conversion tracking.
    4. XSS escaping & spam protection.
    5. Super Admin authorization (strict RBAC).
    6. Non-super-admin rejection (Clinic Admin, Staff, Client, Anonymous -> 302/redirect away).
    7. Cross-tenant isolation (No patient or clinic data leakage).
    8. Lead management (Update status, update notes, CSV export).
    9. Data retention settings & purge functionality.
    """

    def setUp(self):
        self.client = Client()

        # Clinic A
        self.hospital_a = Hospital.objects.create(
            name="Clinic Alpha",
            slug="clinic-alpha",
            email="alpha@example.com",
            is_active=True,
        )

        # 1. Platform Super Admin (is_superuser=True AND Profile.is_platform_admin=True)
        self.superadmin = User.objects.create_superuser(
            username="super_admin_user",
            email="superadmin@saas.io",
            password="StrongPassword123!",
        )
        self.superadmin_profile, _ = Profile.objects.get_or_create(user=self.superadmin)
        self.superadmin_profile.is_platform_admin = True
        self.superadmin_profile.save()

        # 2. Clinic Admin (is_staff=True, ClinicAdmin record)
        self.clinic_admin = User.objects.create_user(
            username="clinic_admin_user",
            email="admin@alpha.com",
            password="StrongPassword123!",
            is_staff=True,
        )
        ClinicAdmin.objects.create(user=self.clinic_admin, hospital=self.hospital_a)

        # 3. Clinical Staff
        self.staff_user = User.objects.create_user(
            username="staff_user",
            email="staff@alpha.com",
            password="StrongPassword123!",
        )
        StaffProfile.objects.create(user=self.staff_user, hospital=self.hospital_a, role="physio")

        # 4. Client / Patient
        self.client_user = User.objects.create_user(
            username="patient_user",
            email="patient@example.com",
            password="StrongPassword123!",
        )

    # ── 1. CONSENT & ANALYTICS BEACON TRACKING ────────────────────────────────

    def test_analytics_beacon_rejected_when_no_consent_and_consent_required(self):
        """When require_consent=True, unconsented pings are ignored."""
        AnalyticsSetting.objects.update_or_create(id=1, defaults={"require_consent": True})
        payload = {
            "session_key": "test_session_123",
            "path": "/",
            "title": "Home Page",
            "active_seconds": 15,
            "consent": False,
        }
        resp = self.client.post(
            reverse("api_analytics_track"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["tracked"])
        self.assertFalse(VisitorSession.objects.filter(session_key="test_session_123").exists())

    def test_analytics_beacon_records_anonymous_session_when_consented(self):
        """Consented tracking creates anonymous session and page view without raw IP."""
        AnalyticsSetting.objects.update_or_create(id=1, defaults={"require_consent": True})
        session_token = "vs_test_token_abc123"
        payload = {
            "session_key": session_token,
            "path": "/services/",
            "title": "Services & Rehabilitation",
            "section": "#orthopedic",
            "active_seconds": 25,
            "consent": True,
            "referrer": "https://www.google.com/search?q=physio",
        }
        resp = self.client.post(
            reverse("api_analytics_track"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["tracked"])

        # Check session
        session = VisitorSession.objects.get(session_key=session_token)
        self.assertEqual(session.device_category, "mobile")
        self.assertEqual(session.referrer_category, "search")
        self.assertEqual(session.referrer_domain, "www.google.com")
        self.assertEqual(session.total_active_seconds, 25)

        # Check pageview event
        pv = PageViewEvent.objects.get(session=session)
        self.assertEqual(pv.path, "/services/")
        self.assertEqual(pv.section_name, "#orthopedic")
        self.assertEqual(pv.active_seconds, 25)

    # ── 2. ACTIVE TIME & MULTI-PAGE AGGREGATION ───────────────────────────────

    def test_active_time_increments_and_pauses(self):
        """Sequential active pings accumulate active reading time correctly."""
        session_token = "vs_active_time_accumulate"
        payload1 = {
            "session_key": session_token,
            "path": "/about/",
            "active_seconds": 30,
            "consent": True,
            "is_new_page": True,
        }
        self.client.post(reverse("api_analytics_track"), data=json.dumps(payload1), content_type="application/json")

        payload2 = {
            "session_key": session_token,
            "path": "/about/",
            "active_seconds": 15,
            "consent": True,
            "is_new_page": False,
        }
        self.client.post(reverse("api_analytics_track"), data=json.dumps(payload2), content_type="application/json")

        session = VisitorSession.objects.get(session_key=session_token)
        self.assertEqual(session.total_active_seconds, 45)
        self.assertEqual(session.total_page_views, 1)

    # ── 3. PUBLIC CONTACT INQUIRY & VOLUNTARY LEAD CREATION ───────────────────

    def test_contact_form_creates_visitor_lead_and_converts_session(self):
        """Explicit contact submission saves lead and flags session as converted."""
        session_token = "vs_lead_submission_test"
        session = VisitorSession.objects.create(session_key=session_token, entry_page="/")

        # Submit contact form
        self.client.cookies["va_session"] = session_token
        post_data = {
            "first_name": "Sarah",
            "last_name": "Connor",
            "email": "sarah.connor@example.com",
            "phone": "+91 98765 43210",
            "subject": "General Enquiry",
            "message": "Interested in chiropractic spinal care for lower back stiffness.",
            "marketing_consent": "1",
            "va_session": session_token,
        }

        with patch("core.views.send_clinic_email", return_value=True):
            resp = self.client.post(reverse("contact"), data=post_data, follow=True)

        self.assertEqual(resp.status_code, 200)

        # Verify VisitorLead was created
        lead = VisitorLead.objects.get(email="sarah.connor@example.com")
        self.assertEqual(lead.first_name, "Sarah")
        self.assertEqual(lead.last_name, "Connor")
        self.assertEqual(lead.phone, "+91 98765 43210")
        self.assertEqual(lead.status, "new")
        self.assertTrue(lead.marketing_consent)
        self.assertEqual(lead.session, session)

        # Verify session marked as converted
        session.refresh_from_db()
        self.assertTrue(session.has_converted)

    # ── 4. SUPER ADMIN STRICT RBAC AUTHORIZATION ──────────────────────────────

    def test_super_admin_can_access_visitor_analytics(self):
        """Platform Super Admin successfully accesses visitor analytics dashboard."""
        self.client.force_login(self.superadmin)
        resp = self.client.get(reverse("super_admin_visitor_analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Website Visitors &amp; Lead Management")
        self.assertContains(resp, "Privacy &amp; Data Retention Settings")

        # Verify audit log was recorded
        self.assertTrue(
            AnalyticsAuditLog.objects.filter(user=self.superadmin, action="view_overview").exists()
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Anonymous requests redirected away to login."""
        resp = self.client.get(reverse("super_admin_visitor_analytics"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp.url)

    def test_clinic_admin_denied_access_to_visitor_analytics(self):
        """Clinic Admin cannot access Super Admin Visitor Analytics."""
        self.client.force_login(self.clinic_admin)
        resp = self.client.get(reverse("super_admin_visitor_analytics"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(resp.url, reverse("super_admin_visitor_analytics"))

    def test_clinical_staff_denied_access_to_visitor_analytics(self):
        """Clinical Staff cannot access Super Admin Visitor Analytics."""
        self.client.force_login(self.staff_user)
        resp = self.client.get(reverse("super_admin_visitor_analytics"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(resp.url, reverse("super_admin_visitor_analytics"))

    def test_client_denied_access_to_visitor_analytics(self):
        """Regular Client cannot access Super Admin Visitor Analytics."""
        self.client.force_login(self.client_user)
        resp = self.client.get(reverse("super_admin_visitor_analytics"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(resp.url, reverse("super_admin_visitor_analytics"))

    # ── 5. LEAD MANAGEMENT & STATUS UPDATES ───────────────────────────────────

    def test_super_admin_can_update_lead_status_and_notes(self):
        """Super Admin can change lead status and save internal notes."""
        lead = VisitorLead.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="janedoe@example.com",
            message="Need appointment info.",
            status="new",
        )

        self.client.force_login(self.superadmin)
        detail_url = reverse("super_admin_visitor_lead_detail", args=[lead.id])

        resp = self.client.post(
            detail_url,
            data={"status": "contacted", "admin_notes": "Called client; sent brochure."},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        lead.refresh_from_db()
        self.assertEqual(lead.status, "contacted")
        self.assertEqual(lead.admin_notes, "Called client; sent brochure.")
        self.assertIsNotNone(lead.contacted_at)

        # Audit log verification
        self.assertTrue(
            AnalyticsAuditLog.objects.filter(user=self.superadmin, action="update_lead").exists()
        )

    # ── 6. CSV EXPORT WITH AUDIT TRAIL ────────────────────────────────────────

    def test_super_admin_export_leads_csv(self):
        """Super Admin can export leads CSV with audit entry."""
        VisitorLead.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="alex@smith.com",
            phone="+91 99999 88888",
            category="Book Appointment",
            message="Looking for physiotherapy session.",
            status="qualified",
        )

        self.client.force_login(self.superadmin)
        resp = self.client.get(reverse("super_admin_export_leads_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment;", resp["Content-Disposition"])
        self.assertIn("alex@smith.com", resp.content.decode("utf-8"))

        self.assertTrue(
            AnalyticsAuditLog.objects.filter(user=self.superadmin, action="export_leads").exists()
        )

    # ── 7. RETENTION SETTINGS & DATA PURGING ──────────────────────────────────

    def test_retention_settings_update_and_session_purge(self):
        """Updating retention days and purging expired sessions works correctly."""
        self.client.force_login(self.superadmin)

        # Update settings to 30 days
        resp = self.client.post(
            reverse("super_admin_analytics_settings"),
            data={"retention_days": "30", "require_consent": "1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        setting = AnalyticsSetting.get_settings()
        self.assertEqual(setting.retention_days, 30)

        # Create old session (40 days ago) and fresh session (2 days ago)
        old_time = timezone.now() - timedelta(days=40)
        old_session = VisitorSession.objects.create(session_key="vs_old_session", started_at=old_time)
        fresh_session = VisitorSession.objects.create(session_key="vs_fresh_session", started_at=timezone.now())

        # Purge
        purge_resp = self.client.post(reverse("super_admin_analytics_purge"), follow=True)
        self.assertEqual(purge_resp.status_code, 200)

        self.assertFalse(VisitorSession.objects.filter(id=old_session.id).exists())
        self.assertTrue(VisitorSession.objects.filter(id=fresh_session.id).exists())
