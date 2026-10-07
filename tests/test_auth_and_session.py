"""
Comprehensive Authentication, Login, Logout, Session, OTP, and Password Test Cases.
Covers:
  - Role-based login redirection for all 4 roles: Super Admin, Clinic Admin, Staff, Client
  - Invalid credentials & error handling
  - Brute force lockout & login attempt limiting
  - Logout and cache prevention headers
  - Password reset via OTP workflow
  - Change password flow
"""
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from core.models import PasswordResetOTP
from tests.test_helpers import BaseHospitalTestCase


class AuthenticationAndSessionTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
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

    # ── Role Login Redirection Tests ─────────────────────────────

    def test_super_admin_login_redirect(self):
        """TC-AUTH-001: Super Admin login redirects to Super Admin dashboard."""
        response = self.client.post(reverse("login"), {
            "username": "super_hero",
            "password": "SuperSecret123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("super_admin_dashboard"))

    def test_clinic_admin_login_redirect(self):
        """TC-AUTH-002: Clinic Admin login redirects to Clinic Admin dashboard."""
        response = self.client.post(reverse("login"), {
            "username": "clinic_boss",
            "password": "BossPassword123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_dashboard"))

    def test_staff_login_redirect(self):
        """TC-AUTH-003: Staff user login redirects to Staff dashboard."""
        response = self.client.post(reverse("login"), {
            "username": "staff_alex",
            "password": "StaffSecret123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("staff_dashboard"))

    def test_client_login_redirect(self):
        """TC-AUTH-004: Patient/Client user login redirects to Client dashboard."""
        response = self.client.post(reverse("login"), {
            "username": "patient_amy",
            "password": "ClientSecret123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

    def test_authenticated_user_accessing_login_page_redirects(self):
        """TC-AUTH-005: Already authenticated user is immediately redirected to their dashboard."""
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("login"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

    # ── Invalid Credential Tests ─────────────────────────────────

    def test_invalid_password(self):
        """TC-AUTH-006: Submitting wrong password denies access with error message."""
        response = self.client.post(reverse("login"), {
            "username": "patient_amy",
            "password": "WrongPassword999!",
        }, follow=True)
        self.assertContains(response, "Invalid username or password")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_nonexistent_username(self):
        """TC-AUTH-007: Submitting non-existent user denies access safely."""
        response = self.client.post(reverse("login"), {
            "username": "ghost_user_12345",
            "password": "SomePassword123!",
        }, follow=True)
        self.assertContains(response, "Invalid username or password")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_empty_credentials(self):
        """TC-AUTH-008: Submitting empty credentials fails gracefully."""
        response = self.client.post(reverse("login"), {
            "username": "",
            "password": "",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_leading_trailing_whitespace_handling(self):
        """TC-AUTH-009: Leading and trailing whitespace on username is stripped."""
        response = self.client.post(reverse("login"), {
            "username": "  patient_amy  ",
            "password": "ClientSecret123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

    # ── Account Lockout / Rate Limiting ──────────────────────────

    def test_five_failed_attempts_locks_account(self):
        """TC-AUTH-010: 5 consecutive failed login attempts trigger security lockout."""
        for i in range(5):
            self.client.post(reverse("login"), {
                "username": "patient_amy",
                "password": f"BadPassword{i}!",
            })

        # The 6th attempt should be blocked with lockout warning
        response = self.client.post(reverse("login"), {
            "username": "patient_amy",
            "password": "ClientSecret123!",
        }, follow=True)
        self.assertTrue(
            "locked" in response.content.decode().lower() or
            "too many" in response.content.decode().lower()
        )

    # ── Logout & Session Cleanup ─────────────────────────────────

    def test_logout_clears_session_and_redirects_home(self):
        """TC-AUTH-011: Logout invalidates session and redirects to home page."""
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("logout"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

        # Protected client dashboard should now redirect to login
        dash_response = self.client.get(reverse("client_dashboard"), follow=False)
        self.assertEqual(dash_response.status_code, 302)
        self.assertIn("/login/", dash_response.url)

    def test_prevent_back_after_logout_headers(self):
        """TC-AUTH-012: Responses include never-cache headers to prevent browser history leaks."""
        response = self.client.get(reverse("home"))
        self.assertIn("no-cache", response.get("Cache-Control", ""))

    # ── Password Reset via OTP ───────────────────────────────────

    def test_request_otp_with_registered_email(self):
        """TC-AUTH-013: Submitting registered email generates a 6-digit OTP."""
        response = self.client.post(reverse("request_otp"), {
            "email": "amy@example.com",
        }, follow=False)
        # Should redirect to verify_otp
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("verify_otp"))
        self.assertTrue(PasswordResetOTP.objects.filter(user=self.client_user).exists())

    def test_request_otp_with_unregistered_email(self):
        """TC-AUTH-014: Submitting unregistered email displays appropriate error."""
        response = self.client.post(reverse("request_otp"), {
            "email": "unknown_email@example.com",
        }, follow=True)
        self.assertContains(response, "No account found with that email")

    def test_verify_valid_otp(self):
        """TC-AUTH-015: Entering the correct OTP verifies successfully."""
        # Step 1: Request OTP
        self.client.post(reverse("request_otp"), {"email": self.client_user.email})
        otp_obj = PasswordResetOTP.objects.filter(user=self.client_user).latest("created_at")

        # Step 2: Verify OTP
        response = self.client.post(reverse("verify_otp"), {
            "otp": otp_obj.otp,
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("reset_password"))
        self.assertTrue(self.client.session.get("otp_verified"))

    def test_verify_invalid_otp(self):
        """TC-AUTH-016: Entering incorrect OTP rejects verification."""
        self.client.post(reverse("request_otp"), {"email": self.client_user.email})

        response = self.client.post(reverse("verify_otp"), {
            "otp": "000000",
        }, follow=True)
        self.assertContains(response, "Incorrect OTP")

    def test_reset_password_with_verified_session(self):
        """TC-AUTH-017: Reset password updates the password and permits login with new password."""
        # Establish verified OTP session
        self.client.post(reverse("request_otp"), {"email": self.client_user.email})
        otp_obj = PasswordResetOTP.objects.filter(user=self.client_user).latest("created_at")
        self.client.post(reverse("verify_otp"), {"otp": otp_obj.otp})

        # Submit new password
        response = self.client.post(reverse("reset_password"), {
            "password": "NewBrandPassword2026!",
            "confirm_password": "NewBrandPassword2026!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

        # Verify old password is now rejected and new password is valid
        self.assertFalse(self.client.login(username="patient_amy", password="ClientSecret123!"))
        self.assertTrue(self.client.login(username="patient_amy", password="NewBrandPassword2026!"))

    # ── Change Password Tests (Authenticated User OTP Workflow) ──

    def test_change_password_workflow_success(self):
        """TC-AUTH-018: Authenticated user requests change password OTP and resets password."""
        self.client.force_login(self.client_user)

        # Step 1: Request password change OTP
        response = self.client.post(reverse("change_password"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("verify_otp"))

        # Step 2: Verify OTP
        otp_obj = PasswordResetOTP.objects.filter(user=self.client_user).latest("created_at")
        verify_resp = self.client.post(reverse("verify_otp"), {"otp": otp_obj.otp}, follow=False)
        self.assertEqual(verify_resp.status_code, 302)
        self.assertEqual(verify_resp.url, reverse("reset_password"))

        # Step 3: Set new password
        reset_resp = self.client.post(reverse("reset_password"), {
            "password": "BrandNewSecret2026!",
            "confirm_password": "BrandNewSecret2026!",
        }, follow=False)
        self.assertEqual(reset_resp.status_code, 302)
        self.assertEqual(reset_resp.url, reverse("login"))

        # Verify login with new password
        self.client.logout()
        self.assertTrue(self.client.login(username="patient_amy", password="BrandNewSecret2026!"))

    def test_reset_password_mismatched_confirmation(self):
        """TC-AUTH-019: Mismatched new password and confirmation rejects password reset."""
        self.client.post(reverse("request_otp"), {"email": self.client_user.email})
        otp_obj = PasswordResetOTP.objects.filter(user=self.client_user).latest("created_at")
        self.client.post(reverse("verify_otp"), {"otp": otp_obj.otp})

        response = self.client.post(reverse("reset_password"), {
            "password": "BrandNewSecret2026!",
            "confirm_password": "DifferentPassword2026!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("reset_password"))

    def test_reset_password_same_as_old_rejected(self):
        """TC-AUTH-020: Setting new password identical to old password is prohibited."""
        self.client.post(reverse("request_otp"), {"email": self.client_user.email})
        otp_obj = PasswordResetOTP.objects.filter(user=self.client_user).latest("created_at")
        self.client.post(reverse("verify_otp"), {"otp": otp_obj.otp})

        response = self.client.post(reverse("reset_password"), {
            "password": "ClientSecret123!",
            "confirm_password": "ClientSecret123!",
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("reset_password"))

    def test_login_page_renders_with_premium_ui_and_accessibility(self):
        """TC-AUTH-021: Redesigned login page contains semantic markup, accessible controls, and branding."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

        # Branding
        self.assertContains(response, "Dr. Dhvani Patalia")
        self.assertContains(response, "Physio Rehab")
        self.assertContains(response, "Dhvani_Patalia.jpeg")

        # Semantic Form & Fields
        self.assertContains(response, 'id="loginForm"')
        self.assertContains(response, 'for="username"')
        self.assertContains(response, 'id="username"')
        self.assertContains(response, 'for="password"')
        self.assertContains(response, 'id="password"')

        # Accessibility and Show/Hide Password Toggle
        self.assertContains(response, 'id="togglePassword"')
        self.assertContains(response, 'aria-label="Show password"')
        self.assertContains(response, 'aria-pressed="false"')

        # Utility Links
        self.assertContains(response, 'name="remember_me"')
        self.assertContains(response, reverse("request_otp"))
        self.assertContains(response, reverse("register"))
        self.assertContains(response, reverse("home"))

        # Submit button
        self.assertContains(response, 'id="submitBtn"')
        self.assertContains(response, "Sign In to Account")

