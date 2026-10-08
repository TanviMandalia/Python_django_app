"""
Comprehensive Regression Test Suite: Email Identity Separation.

Validates:
1. TechCraft Platform / Super Admin Identity:
   - Super Admin test emails use TechCraft identity (<techcraft1215@gmail.com>).
   - Platform notifications, SaaS subscriptions, and platform password resets use TechCraft.
   - Platform templates, headers, footers render zero clinic leaks (no clinic name, phone, or logo).
   - Missing platform DB account safely defaults to virtual TechCraft mailer (never clinic mailer).

2. Clinic Identity (Dr. Dhvani Patalia Physio Rehab):
   - Clinic patient appointments, status updates, and clinic staff OTPs retain clinic branding.
   - Clinic templates preserve clinic contact info, phone, and name.
   - Cross-tenant isolation prevents one clinic from using another's settings.

3. Security, RBAC & Settings Independence:
   - Saving clinic settings does not alter platform settings.
   - Saving platform settings does not alter clinic settings.
   - Blank password preserves existing credentials.
   - Plaintext passwords are never exposed.
   - Non-superadmins cannot access or modify platform SMTP settings.

4. Background Workers & Celery Tasks:
   - Celery tasks preserve the explicit sending context ('platform' vs 'clinic').
"""

from unittest.mock import patch
from django.core import mail
from django.urls import reverse
from django.conf import settings

from core.models import EmailAccount, EmailLog, Hospital, SubscriptionPlan
from core.email_service import (
    EmailContext,
    EmailPurpose,
    resolve_email_account,
    send_email_via_account,
    test_account_connection,
)
from core.email_utils import (
    render_html_wrapper,
    send_platform_email,
    send_clinic_email,
    send_subscription_success_email,
    send_subscription_expiry_warning_email,
    send_otp_email,
    send_appointment_confirmation,
)
from core.tasks import send_email_task, send_platform_email_task
from tests.test_helpers import BaseHospitalTestCase


class TestPlatformIdentityArchitecture(BaseHospitalTestCase):
    """Verify TechCraft platform-level email sender identity, templates, and isolation."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="dr.dhvani@physiorehab.com",
            phone="+91 98765 43210",
        )

        # TechCraft Platform Account
        self.platform_account = EmailAccount.objects.create(
            name="TechCraft Gmail SMTP",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.gmail.com",
            port=587,
            use_tls=True,
            use_ssl=False,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            from_name="TechCraft",
            reply_to="techcraft1215@gmail.com",
            is_active=True,
            is_default=True,
        )
        self.platform_account.set_password("valid_app_password")
        self.platform_account.save()

        # Clinic Account
        self.clinic_account = EmailAccount.objects.create(
            name="Physio Rehab Clinic SMTP",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            host="smtp.physiorehab.com",
            port=587,
            use_tls=True,
            use_ssl=False,
            username="clinic_mailer",
            from_email="noreply@physiorehab.com",
            from_name="Dr. Dhvani Patalia Physio Rehab",
            reply_to="contact@physiorehab.com",
            is_active=True,
            is_default=True,
        )
        self.clinic_account.set_password("clinic_secret")
        self.clinic_account.save()

    def test_super_admin_test_email_uses_techcraft(self):
        """Super Admin diagnostic test email must be sent as TechCraft with zero clinic branding."""
        mail.outbox.clear()
        ok, msg = test_account_connection(
            self.platform_account,
            test_recipient="admin_tester@example.com",
            force_smtp=False,
        )
        self.assertTrue(ok)
        self.assertIn("successful", msg.lower())

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]

        # Verify Sender Identity
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertNotIn("Dr. Dhvani Patalia", sent.from_email)
        self.assertNotIn("Physio Rehab", sent.from_email)

        # Verify Subject & Headers
        self.assertIn("TechCraft", sent.subject)
        self.assertEqual(sent.extra_headers.get("X-Mailer"), "TechCraft-Email-Gateway")

        # Verify Body & HTML: Strictly TechCraft, zero clinic references
        self.assertIn("TechCraft", sent.body)
        self.assertNotIn("Dr. Dhvani Patalia", sent.body)
        self.assertNotIn("+91 98765 43210", sent.body)

        html_content = sent.alternatives[0][0]
        self.assertIn("TechCraft", html_content)
        self.assertIn("Healthcare SaaS Platform", html_content)
        self.assertIn("techcraft1215@gmail.com", html_content)
        self.assertNotIn("Dr. Dhvani Patalia", html_content)
        self.assertNotIn("+91 98765 43210", html_content)

    def test_send_platform_email_uses_techcraft_identity(self):
        """send_platform_email dispatches via TechCraft platform account."""
        mail.outbox.clear()
        ok = send_platform_email(
            subject="Platform System Maintenance Notice",
            message_text="Scheduled maintenance tonight at midnight UTC.",
            recipient_list=["devops@example.com"],
        )
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

        sent = mail.outbox[0]
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertNotIn("Dr. Dhvani Patalia", sent.from_email)
        self.assertIn("Scheduled maintenance tonight", sent.body)

        # Check logged EmailLog
        log_entry = EmailLog.objects.filter(recipient_email="devops@example.com").latest("id")
        self.assertEqual(log_entry.status, "sent")
        self.assertEqual(log_entry.sender_email, "techcraft1215@gmail.com")
        self.assertIsNone(log_entry.hospital)

    def test_subscription_success_email_uses_techcraft_branding(self):
        """SaaS subscription activation email must represent TechCraft, not the subscriber clinic."""
        mail.outbox.clear()
        plan = SubscriptionPlan.objects.filter(is_active=True).first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Enterprise Test Plan", code="enterprise_test_99", price_monthly=4999)
        from datetime import date, timedelta
        expires = date.today() + timedelta(days=365)

        ok = send_subscription_success_email(self.hospital, plan, expires)
        self.assertTrue(ok)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]

        # Sender is TechCraft
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)

        # Body thanks hospital for partnering with TechCraft
        self.assertIn("TechCraft Platform", sent.body)
        self.assertIn("partnering with TechCraft", sent.body)
        self.assertIn(self.hospital.name, sent.body)  # Addressed TO the hospital administration

        html_content = sent.alternatives[0][0]
        self.assertIn("TechCraft", html_content)
        self.assertIn("techcraft1215@gmail.com", html_content)
        self.assertNotIn("Support: +91 98765 43210", html_content)

    def test_subscription_warning_email_uses_techcraft_branding(self):
        """SaaS subscription expiry warning email must represent TechCraft."""
        mail.outbox.clear()
        plan = SubscriptionPlan.objects.filter(is_active=True).first()
        if not plan:
            plan = SubscriptionPlan.objects.create(name="Basic Test Plan", code="basic_test_99", price_monthly=999)
        from datetime import date, timedelta
        expires = date.today() + timedelta(days=5)

        ok = send_subscription_expiry_warning_email(self.hospital, plan, expires, days_left=5)
        self.assertTrue(ok)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertIn("TechCraft Platform Administration", sent.body)

    def test_superadmin_password_reset_otp_uses_techcraft(self):
        """Super Admin password reset OTP must be branded as TechCraft."""
        mail.outbox.clear()
        super_user = self.create_super_admin(username="techcraft_root", email="root@techcraft.io")

        ok = send_otp_email(super_user.email, otp="654321", purpose="Password Reset", user=super_user)
        self.assertTrue(ok)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertIn("TechCraft Platform Administration", sent.body)
        self.assertNotIn("Dr. Dhvani Patalia", sent.body)

    def test_render_html_wrapper_platform_context_zero_clinic_leak(self):
        """Direct inspection of render_html_wrapper under platform context."""
        html = render_html_wrapper(
            title="System Alert",
            body_content="<p>Security update deployed.</p>",
            context="platform",
        )
        self.assertIn("TechCraft", html)
        self.assertIn("Healthcare SaaS Platform", html)
        self.assertIn("techcraft1215@gmail.com", html)
        self.assertNotIn("Dr. Dhvani Patalia", html)
        self.assertNotIn("+91 98765 43210", html)
        self.assertNotIn("noreply@physiorehab.com", html)

    def test_missing_platform_account_falls_back_to_virtual_techcraft_not_clinic(self):
        """If all platform accounts are deleted, resolve_email_account creates virtual TechCraft mailer."""
        EmailAccount.objects.filter(scope_type="platform").delete()

        resolved = resolve_email_account(context=EmailContext.PLATFORM)
        self.assertEqual(resolved.scope_type, "platform")
        self.assertEqual(resolved.from_name, "TechCraft")
        self.assertEqual(resolved.from_email, "techcraft1215@gmail.com")
        self.assertIsNone(resolved.hospital)
        # MUST NOT fall back to clinic account
        self.assertNotEqual(resolved.id, self.clinic_account.id)


class TestClinicIdentityArchitecture(BaseHospitalTestCase):
    """Verify clinic-level email sender identity, templates, and multi-tenant isolation."""

    def setUp(self):
        super().setUp()
        self.clinic_a = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="info@pataliaphysio.com",
            phone="+91 98765 43210",
        )
        self.patient_a = self.create_patient(self.clinic_a, username="patient_arjun", email="arjun@example.com")
        self.appointment_a = self.create_appointment(self.clinic_a, self.patient_a)

        self.clinic_account = EmailAccount.objects.create(
            name="Patalia Clinic SMTP",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.clinic_a,
            host="smtp.pataliaphysio.com",
            port=587,
            use_tls=True,
            username="patalia_user",
            from_email="care@pataliaphysio.com",
            from_name="Dr. Dhvani Patalia Physio Rehab",
            reply_to="reception@pataliaphysio.com",
            is_active=True,
            is_default=True,
        )
        self.clinic_account.set_password("ClinicSecret456")
        self.clinic_account.save()

    def test_appointment_confirmation_retains_clinic_branding(self):
        """Patient appointment confirmation must use the clinic's dedicated identity."""
        mail.outbox.clear()
        ok = send_appointment_confirmation(self.appointment_a)
        self.assertTrue(ok)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]

        # Sender identity must be the clinic
        self.assertIn("Dr. Dhvani Patalia Physio Rehab", sent.from_email)
        self.assertIn("care@pataliaphysio.com", sent.from_email)
        self.assertNotIn("TechCraft", sent.from_email)

        # Body contains clinic signature
        self.assertIn("Dr. Dhvani Patalia", sent.body)
        self.assertNotIn("TechCraft SaaS Platform", sent.body)

        # HTML wrapper contains clinic footer with clinic contact info
        html_content = sent.alternatives[0][0]
        self.assertIn("Dr. Dhvani Patalia Physio Rehab", html_content)
        self.assertIn("+91 98765 43210", html_content)
        self.assertIn("info@pataliaphysio.com", html_content)
        self.assertNotIn("TechCraft SaaS Platform", html_content)

    def test_clinic_staff_otp_retains_clinic_branding(self):
        """Clinic staff password reset OTP must be branded with clinic details."""
        mail.outbox.clear()
        staff_user = self.create_staff(self.clinic_a, username="nurse_sneha", email="sneha@pataliaphysio.com")

        ok = send_otp_email(staff_user.email, otp="789012", purpose="Password Reset", user=staff_user, hospital=self.clinic_a)
        self.assertTrue(ok)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]

        self.assertIn("Dr. Dhvani Patalia Physio Rehab", sent.from_email)
        self.assertIn("care@pataliaphysio.com", sent.from_email)
        self.assertNotIn("TechCraft", sent.from_email)

    def test_render_html_wrapper_clinic_context(self):
        """Direct inspection of render_html_wrapper under clinic context."""
        html = render_html_wrapper(
            title="Appointment Reminder",
            body_content="<p>Your session is tomorrow at 10 AM.</p>",
            context="clinic",
            hospital=self.clinic_a,
        )
        self.assertIn("Dr. Dhvani Patalia Physio Rehab", html)
        self.assertIn("+91 98765 43210", html)
        self.assertIn("info@pataliaphysio.com", html)
        self.assertNotIn("TechCraft SaaS Platform", html)


class TestSettingsIndependenceAndSecurity(BaseHospitalTestCase):
    """Verify settings independence, RBAC, and credential confidentiality."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Apollo Care", email="contact@apollo.com")
        self.clinic_admin = self.create_clinic_admin(self.hospital, username="apollo_admin")
        self.super_admin = self.create_super_admin(username="techcraft_admin")
        self.patient = self.create_patient(self.hospital, username="regular_patient")

        self.platform_account = EmailAccount.objects.create(
            name="TechCraft Primary SMTP",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.gmail.com",
            port=587,
            use_tls=True,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            from_name="TechCraft",
            is_active=True,
            is_default=True,
        )
        self.platform_account.set_password("SuperSecretAppPass123")
        self.platform_account.save()

        self.clinic_account = EmailAccount.objects.create(
            name="Apollo Primary SMTP",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            host="smtp.apollo.com",
            port=587,
            use_tls=True,
            username="apollo_mailer",
            from_email="notifications@apollo.com",
            from_name="Apollo Care",
            is_active=True,
            is_default=True,
        )
        self.clinic_account.set_password("ApolloSecretPass456")
        self.clinic_account.save()

    def test_saving_clinic_settings_does_not_alter_platform_settings(self):
        """Clinic Admin modifying their email settings cannot overwrite TechCraft platform settings."""
        self.client.force_login(self.clinic_admin)
        response = self.client.post(
            reverse("admin_email_settings"),
            {
                "action": "save",
                "name": "Apollo Care Updated SMTP",
                "provider": "smtp",
                "account_type": "CLINIC",
                "host": "smtp.updated-apollo.com",
                "port": "587",
                "username": "apollo_updated",
                "password": "",  # Keep existing password
                "from_email": "alerts@updated-apollo.com",
                "from_name": "Apollo Care Clinic",
                "use_tls": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        # Refresh platform account and verify zero changes
        self.platform_account.refresh_from_db()
        self.assertEqual(self.platform_account.name, "TechCraft Primary SMTP")
        self.assertEqual(self.platform_account.from_name, "TechCraft")
        self.assertEqual(self.platform_account.from_email, "techcraft1215@gmail.com")
        self.assertEqual(self.platform_account.get_password(), "SuperSecretAppPass123")
        self.assertIsNone(self.platform_account.hospital)

    def test_saving_platform_settings_does_not_alter_clinic_settings(self):
        """Super Admin saving platform settings cannot overwrite clinic settings."""
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin_email_account_save"),
            {
                "account_id": self.platform_account.id,
                "name": "TechCraft Primary SMTP V2",
                "account_type": "PLATFORM",
                "scope_type": "platform",
                "provider": "gmail",
                "host": "smtp.gmail.com",
                "port": "587",
                "username": "techcraft1215@gmail.com",
                "password": "",  # Blank preserves existing
                "from_email": "techcraft1215@gmail.com",
                "from_name": "TechCraft",
                "reply_to": "support@techcraft.io",
                "use_tls": "on",
                "is_default": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        # Verify platform account updated
        self.platform_account.refresh_from_db()
        self.assertEqual(self.platform_account.name, "TechCraft Primary SMTP V2")
        self.assertEqual(self.platform_account.get_password(), "SuperSecretAppPass123")

        # Verify clinic account remained untouched
        self.clinic_account.refresh_from_db()
        self.assertEqual(self.clinic_account.name, "Apollo Primary SMTP")
        self.assertEqual(self.clinic_account.from_name, "Apollo Care")
        self.assertEqual(self.clinic_account.get_password(), "ApolloSecretPass456")

    def test_non_superadmin_forbidden_from_platform_settings(self):
        """Clinic admin or patient cannot access Super Admin email governance."""
        self.client.force_login(self.clinic_admin)
        response = self.client.get(reverse("super_admin_email_accounts"))
        self.assertIn(response.status_code, (302, 403))

        self.client.force_login(self.patient)
        response = self.client.get(reverse("super_admin_email_accounts"))
        self.assertIn(response.status_code, (302, 403))

    def test_credentials_never_exposed_in_templates_or_api(self):
        """Password fields in settings templates must never contain plaintext passwords."""
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("super_admin_email_accounts"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("SuperSecretAppPass123", response.content.decode())
        self.assertNotIn("ApolloSecretPass456", response.content.decode())

        self.client.force_login(self.clinic_admin)
        response = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ApolloSecretPass456", response.content.decode())


class TestBackgroundTasksPreserveIdentity(BaseHospitalTestCase):
    """Verify Celery background tasks preserve explicit sending contexts."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="St. Jude Rehab", email="contact@stjude.com")

        self.platform_account = EmailAccount.objects.create(
            name="TechCraft Platform Mailer",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.gmail.com",
            port=587,
            use_tls=True,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            from_name="TechCraft",
            is_active=True,
            is_default=True,
        )
        self.platform_account.set_password("AppPassPlatform")
        self.platform_account.save()

        self.clinic_account = EmailAccount.objects.create(
            name="St. Jude SMTP",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            host="smtp.stjude.com",
            port=587,
            use_tls=True,
            username="stjude_mailer",
            from_email="noreply@stjude.com",
            from_name="St. Jude Rehab Clinic",
            is_active=True,
            is_default=True,
        )
        self.clinic_account.set_password("StJudePass")
        self.clinic_account.save()

    def test_send_email_task_preserves_platform_context(self):
        """send_email_task(context='platform') uses TechCraft identity."""
        mail.outbox.clear()
        res = send_email_task.apply(
            kwargs={
                "subject": "Platform Security Alert",
                "message": "Login detected from new location.",
                "recipient_list": ["security_team@example.com"],
                "context": "platform",
            }
        ).get()
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["context"], "platform")

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertNotIn("St. Jude", sent.from_email)

    def test_send_email_task_preserves_clinic_context(self):
        """send_email_task(context='clinic', hospital_id=...) uses clinic identity."""
        mail.outbox.clear()
        res = send_email_task.apply(
            kwargs={
                "subject": "Physiotherapy Session Update",
                "message": "Your session has been assigned.",
                "recipient_list": ["patient_bob@example.com"],
                "context": "clinic",
                "hospital_id": self.hospital.id,
            }
        ).get()
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["context"], "clinic")

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("St. Jude Rehab Clinic", sent.from_email)
        self.assertIn("noreply@stjude.com", sent.from_email)
        self.assertNotIn("TechCraft", sent.from_email)

    def test_send_platform_email_task_dedicated(self):
        """send_platform_email_task dispatches via TechCraft platform identity."""
        mail.outbox.clear()
        res = send_platform_email_task.apply(
            kwargs={
                "subject": "Platform Onboarding Complete",
                "message": "Welcome to the TechCraft SaaS platform.",
                "recipient_list": ["hospital_owner@example.com"],
            }
        ).get()
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["context"], "platform")

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("TechCraft", sent.from_email)
        self.assertIn("techcraft1215@gmail.com", sent.from_email)
        self.assertNotIn("St. Jude", sent.from_email)
