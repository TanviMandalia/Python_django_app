"""
Comprehensive automated tests for Remember Me login feature, session expiry,
cookie security attributes, and SessionTimeoutMiddleware integration.
"""
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.test import override_settings
from django.contrib.sessions.models import Session
from tests.test_helpers import BaseHospitalTestCase


class RememberMeAuthenticationTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Care Clinic", email="care@example.com")
        self.super_admin = self.create_super_admin(
            username="super_hero", email="super@example.com", password="SuperSecret123!"
        )
        self.clinic_admin = self.create_clinic_admin(
            self.hospital, username="clinic_boss", email="boss@example.com", password="BossPassword123!"
        )
        self.staff_user = self.create_staff(
            self.hospital, username="staff_alex", email="alex@example.com", password="StaffSecret123!"
        )
        self.client_user = self.create_patient(
            self.hospital, username="patient_amy", email="amy@example.com", password="ClientSecret123!"
        )

    # ── 1. Remember Me Checked Tests ─────────────────────────────────

    def test_login_with_remember_me_checked_sets_persistent_expiry(self):
        """TC-REM-001: Checking Remember Me sets persistent 14-day expiry on session and cookie."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

        # Session inspection
        session = self.client.session
        self.assertTrue(session.get("remember_me"))
        self.assertFalse(session.get_expire_at_browser_close())
        self.assertEqual(session.get_expiry_age(), 1209600)  # 14 days in seconds

        # Cookie inspection
        cookie = response.cookies.get("physiorehab_sessionid")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie["max-age"], 1209600)
        self.assertTrue(cookie["httponly"])

    def test_login_with_remember_me_alternative_truthy_values(self):
        """TC-REM-002: Accepts 'true' or '1' as truthy remember_me input."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "true",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertTrue(session.get("remember_me"))
        self.assertFalse(session.get_expire_at_browser_close())
        self.assertEqual(session.get_expiry_age(), 1209600)

    # ── 2. Remember Me Unchecked Tests ───────────────────────────────

    def test_login_with_remember_me_unchecked_sets_browser_session_expiry(self):
        """TC-REM-003: Unchecked Remember Me sets browser-session expiry (expires on browser close)."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        session = self.client.session
        self.assertFalse(session.get("remember_me"))
        self.assertTrue(session.get_expire_at_browser_close())

        # Cookie should have no max-age/expires so the browser discards it on close
        cookie = response.cookies.get("physiorehab_sessionid")
        self.assertIsNotNone(cookie)
        self.assertFalse(cookie["max-age"])
        self.assertFalse(cookie["expires"])

    def test_missing_checkbox_behaves_as_unchecked(self):
        """TC-REM-004: Omission of remember_me parameter defaults strictly to unchecked."""
        response = self.client.post(
            reverse("login"),
            {"username": "patient_amy", "password": "ClientSecret123!"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertFalse(session.get("remember_me"))
        self.assertTrue(session.get_expire_at_browser_close())

    def test_explicit_empty_checkbox_behaves_as_unchecked(self):
        """TC-REM-005: Explicit empty string behaves as unchecked."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertFalse(session.get("remember_me"))
        self.assertTrue(session.get_expire_at_browser_close())

    # ── 3. Invalid Credentials & Validation Errors ───────────────────

    def test_invalid_credentials_do_not_create_authenticated_session(self):
        """TC-REM-006: Bad password fails authentication without creating session."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "WrongPassword123!",
                "remember_me": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        # Form preserves username and remember_me state for good UX
        self.assertEqual(response.context["username"], "patient_amy")
        self.assertTrue(response.context["remember_me"])

    def test_empty_form_submission_does_not_create_session(self):
        """TC-REM-007: Submitting empty form denies access."""
        response = self.client.post(
            reverse("login"),
            {"username": "", "password": ""},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    # ── 4. SessionTimeoutMiddleware Integration ──────────────────────

    def test_session_timeout_middleware_exempts_remembered_user(self):
        """TC-REM-008: Remembered user is NOT logged out by 30-min idle timeout middleware."""
        # Log in with remember_me="on"
        self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
            },
        )
        # Simulate 45 minutes of idle time
        session = self.client.session
        past_time = timezone.now().replace(tzinfo=None) - timedelta(minutes=45)
        session["last_activity"] = past_time.isoformat()
        session.save()

        # Access dashboard
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 200)
        # User remains authenticated
        self.assertTrue(response.context["user"].is_authenticated)

    def test_session_timeout_middleware_logs_out_unremembered_user(self):
        """TC-REM-009: Unremembered user is logged out by 30-min idle timeout middleware."""
        # Log in without remember_me
        self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
            },
        )
        # Simulate 45 minutes of idle time
        session = self.client.session
        past_time = timezone.now().replace(tzinfo=None) - timedelta(minutes=45)
        session["last_activity"] = past_time.isoformat()
        session.save()

        # Access dashboard -> should be redirected to login
        response = self.client.get(reverse("client_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    # ── 5. Logout & Invalidation ─────────────────────────────────────

    def test_logout_invalidates_session_and_cleans_db(self):
        """TC-REM-010: Logout flushes session, removes database entry, and blocks dashboard access."""
        # Login with remember_me
        self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
            },
        )
        session_key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

        # Logout
        response = self.client.get(reverse("logout"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

        # Database session entry must be deleted
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

        # Protected client dashboard redirects to login
        dash_response = self.client.get(reverse("client_dashboard"), follow=False)
        self.assertEqual(dash_response.status_code, 302)
        self.assertIn("/login/", dash_response.url)

    # ── 6. Cookie Security Attributes in Production ──────────────────

    @override_settings(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    def test_session_cookie_production_security_attributes(self):
        """TC-REM-011: Production session cookies enforce Secure, HttpOnly, and SameSite=Lax."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
            },
            follow=False,
            secure=True,  # HTTPS request
        )
        cookie = response.cookies.get("physiorehab_sessionid")
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    # ── 7. Role-Based Login Flows with Remember Me ───────────────────

    def test_super_admin_login_with_remember_me(self):
        """TC-REM-012a: Super Admin logs in with Remember Me and redirects correctly."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "super_hero",
                "password": "SuperSecret123!",
                "remember_me": "on",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("super_admin_dashboard"))
        self.assertTrue(self.client.session.get("remember_me"))
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_clinic_admin_login_with_remember_me(self):
        """TC-REM-012b: Clinic Admin logs in with Remember Me and redirects correctly."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "clinic_boss",
                "password": "BossPassword123!",
                "remember_me": "on",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_dashboard"))
        self.assertTrue(self.client.session.get("remember_me"))

    def test_staff_login_with_remember_me(self):
        """TC-REM-012c: Staff user logs in with Remember Me and redirects correctly."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "staff_alex",
                "password": "StaffSecret123!",
                "remember_me": "on",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("staff_dashboard"))
        self.assertTrue(self.client.session.get("remember_me"))

    # ── 8. Safe 'next' Redirect Preservation ─────────────────────────

    def test_login_redirects_to_safe_next_url(self):
        """TC-REM-013: Safe relative 'next' destination is honored after Remember Me login."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
                "next": "/profile/",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/profile/")

    def test_login_rejects_unsafe_external_next_url(self):
        """TC-REM-014: Malicious external 'next' url is rejected, falling back to role dashboard."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "patient_amy",
                "password": "ClientSecret123!",
                "remember_me": "on",
                "next": "https://attacker-domain.example.com/steal-creds",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))
