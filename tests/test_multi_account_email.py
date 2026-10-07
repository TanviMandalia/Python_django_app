"""
Comprehensive Test Suite for Multi-Portal Real Email API / SMTP Architecture.

Validates:
1. Multi-account database model (EmailAccount) with Fernet encryption at rest.
2. Tenant isolation (Clinic A vs Clinic B sender isolation).
3. Purpose-specific sender routing (Platform, Clinic, Doctor, Support, Notification).
4. Outgoing email header enforcement (From, Reply-To, Message-ID, X-Thread-ID).
5. EmailLog recording with sender accounts and audit metadata.
6. Role-Based Access Control (RBAC):
   - Super Admin: Full governance
   - Clinic Admin: Own clinic only
   - Staff: Forbidden (403)
   - Client: Forbidden (403)
7. Safe diagnostic connection testing without credential leakage.
"""

from django.core import mail
from django.urls import reverse
from django.contrib.auth.models import User

from core.models import EmailAccount, EmailLog, Hospital
from core.crypto import encrypt_credential, decrypt_credential
from core.email_service import (
    EmailPurpose,
    resolve_email_account,
    send_email_via_account,
    test_account_connection as run_account_connection_test,
)
from core.email_utils import send_clinic_email, send_appointment_confirmation, send_otp_email
from tests.test_helpers import BaseHospitalTestCase


class TestEmailAccountModel(BaseHospitalTestCase):
    """Test EmailAccount data integrity, encryption at rest, and credential protection."""

    def test_credential_encryption_and_decryption(self):
        """Verify Fernet AES-128 encryption at rest and transparent decryption."""
        raw_secret = "SuperSecretSmtpPassword123!@#"
        account = EmailAccount(
            name="Platform Primary Mailer",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.gmail.com",
            port=587,
            username="platform@physiorehab.com",
            from_email="platform@physiorehab.com",
            from_name="Platform Central",
            is_active=True,
        )
        account.set_password(raw_secret)
        account.save()

        # Reload directly from database to test persistent ciphertext
        db_account = EmailAccount.objects.get(id=account.id)
        self.assertNotEqual(db_account.encrypted_password, raw_secret)
        self.assertNotIn(raw_secret, db_account.encrypted_password)
        self.assertEqual(db_account.get_password(), raw_secret)

    def test_empty_password_handling(self):
        """Verify empty password does not crash crypto engine."""
        account = EmailAccount.objects.create(
            name="No-Password Relay",
            account_type="SYSTEM",
            scope_type="platform",
            host="localhost",
            port=25,
            username="relay",
            from_email="relay@domain.com",
        )
        account.set_password("")
        account.save()
        self.assertEqual(account.get_password(), "")


class TestSenderResolutionAndIsolation(BaseHospitalTestCase):
    """Verify strict tenant isolation and purpose-based routing."""

    def setUp(self):
        super().setUp()
        self.hospital_a = self.create_hospital(name="Alpha Health", email="alpha@hospital.com")
        self.hospital_b = self.create_hospital(name="Beta Clinic", email="beta@clinic.com")

        # 1. Platform Account
        self.platform_account = EmailAccount.objects.create(
            name="Platform Master SMTP",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.platform.com",
            port=587,
            username="platform_user",
            from_email="no-reply@platform.com",
            from_name="Platform Authority",
            is_active=True,
            is_default=True,
        )
        self.platform_account.set_password("PlatPass123")
        self.platform_account.save()

        # 2. Support Account
        self.support_account = EmailAccount.objects.create(
            name="Support Helpdesk",
            account_type="SUPPORT",
            scope_type="platform",
            host="smtp.platform.com",
            port=587,
            username="support_user",
            from_email="support@platform.com",
            from_name="Platform Support",
            is_active=True,
        )
        self.support_account.set_password("SuppPass123")
        self.support_account.save()

        # 3. Clinic A Account
        self.clinic_a_account = EmailAccount.objects.create(
            name="Alpha Health Notifications",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital_a,
            host="smtp.alpha.com",
            port=587,
            username="alpha_user",
            from_email="contact@alphahealth.com",
            from_name="Alpha Health Care",
            reply_to="doctors@alphahealth.com",
            is_active=True,
            is_default=True,
        )
        self.clinic_a_account.set_password("AlphaPass123")
        self.clinic_a_account.save()

        # 4. Clinic B Account
        self.clinic_b_account = EmailAccount.objects.create(
            name="Beta Clinic Notifications",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital_b,
            host="smtp.beta.com",
            port=587,
            username="beta_user",
            from_email="reception@betaclinic.com",
            from_name="Beta Clinic",
            reply_to="info@betaclinic.com",
            is_active=True,
            is_default=True,
        )
        self.clinic_b_account.set_password("BetaPass123")
        self.clinic_b_account.save()

        # 5. Doctor Account
        self.doctor_user = self.create_staff(
            self.hospital_a,
            username="dr_watson",
            email="watson@alphahealth.com",
            first_name="John",
            last_name="Watson",
        )
        self.doctor_account = EmailAccount.objects.create(
            name="Dr. Watson Private Mailer",
            account_type="DOCTOR",
            scope_type="user",
            user=self.doctor_user,
            hospital=self.hospital_a,
            host="smtp.gmail.com",
            port=587,
            username="watson_user",
            from_email="dr.watson@alphahealth.com",
            from_name="Dr. John Watson",
            is_active=True,
        )
        self.doctor_account.set_password("WatsonPass123")
        self.doctor_account.save()

    def test_clinic_a_resolves_clinic_a_account(self):
        """Action for Clinic A must strictly resolve Clinic A's EmailAccount."""
        resolved = resolve_email_account(
            purpose=EmailPurpose.APPOINTMENT_CONFIRMATION,
            hospital=self.hospital_a,
        )
        self.assertEqual(resolved.id, self.clinic_a_account.id)
        self.assertEqual(resolved.from_email, "contact@alphahealth.com")
        self.assertEqual(resolved.from_name, "Alpha Health Care")

    def test_clinic_b_resolves_clinic_b_account(self):
        """Action for Clinic B must strictly resolve Clinic B's EmailAccount."""
        resolved = resolve_email_account(
            purpose=EmailPurpose.APPOINTMENT_CONFIRMATION,
            hospital=self.hospital_b,
        )
        self.assertEqual(resolved.id, self.clinic_b_account.id)
        self.assertEqual(resolved.from_email, "reception@betaclinic.com")
        self.assertEqual(resolved.from_name, "Beta Clinic")

    def test_cross_clinic_isolation_strictly_enforced(self):
        """Clinic A can NEVER use or resolve Clinic B's account."""
        resolved = resolve_email_account(
            purpose=EmailPurpose.APPOINTMENT_CONFIRMATION,
            hospital=self.hospital_a,
        )
        self.assertNotEqual(resolved.id, self.clinic_b_account.id)
        self.assertNotEqual(resolved.from_email, self.clinic_b_account.from_email)

    def test_doctor_specific_resolution(self):
        """When doctor is specified, their dedicated account takes priority."""
        resolved = resolve_email_account(
            purpose=EmailPurpose.DOCTOR_COMMUNICATION,
            hospital=self.hospital_a,
            doctor=self.doctor_user,
        )
        self.assertEqual(resolved.id, self.doctor_account.id)
        self.assertEqual(resolved.from_email, "dr.watson@alphahealth.com")

    def test_platform_password_reset_routing(self):
        """Password resets and OTP verifications must route to the Platform account."""
        resolved_reset = resolve_email_account(purpose=EmailPurpose.PASSWORD_RESET)
        self.assertEqual(resolved_reset.id, self.platform_account.id)
        self.assertEqual(resolved_reset.from_email, "no-reply@platform.com")

        resolved_otp = resolve_email_account(purpose="otp_verification")
        self.assertEqual(resolved_otp.id, self.platform_account.id)

    def test_support_ticket_routing(self):
        """Support inquiries must route to the Support account."""
        resolved_support = resolve_email_account(purpose=EmailPurpose.SUPPORT_TICKET)
        self.assertEqual(resolved_support.id, self.support_account.id)
        self.assertEqual(resolved_support.from_email, "support@platform.com")


class TestEmailDispatchAndLogging(BaseHospitalTestCase):
    """Verify live sending, RFC headers, and database audit logs."""

    def setUp(self):
        super().setUp()
        self.hospital_a = self.create_hospital(name="Care Clinic", email="care@clinic.com")
        self.patient_a = self.create_patient(self.hospital_a, username="john_doe", email="john@example.com")
        self.appointment_a = self.create_appointment(self.hospital_a, self.patient_a)

        self.clinic_account = EmailAccount.objects.create(
            name="Care Clinic SMTP",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital_a,
            host="smtp.careclinic.com",
            port=587,
            username="care_user",
            from_email="alerts@careclinic.com",
            from_name="Care Clinic Team",
            reply_to="helpdesk@careclinic.com",
            is_active=True,
            is_default=True,
        )
        self.clinic_account.set_password("CarePassword999")
        self.clinic_account.save()

    def test_send_appointment_confirmation_multi_portal(self):
        """Verify appointment email uses clinic-specific sender identity and logs cleanly."""
        mail.outbox.clear()
        ok = send_appointment_confirmation(self.appointment_a)
        self.assertTrue(ok)

        # Inspect outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_msg = mail.outbox[0]
        self.assertIn("alerts@careclinic.com", sent_msg.from_email)
        self.assertIn("Care Clinic Team", sent_msg.from_email)
        self.assertEqual(sent_msg.to, ["john@example.com"])
        self.assertIn("helpdesk@careclinic.com", sent_msg.reply_to)
        self.assertIn("Message-ID", sent_msg.extra_headers)
        self.assertIn("X-Thread-ID", sent_msg.extra_headers)

        # Inspect EmailLog audit trail
        log_entry = EmailLog.objects.filter(recipient_email="john@example.com").first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.account_id, self.clinic_account.id)
        self.assertEqual(log_entry.sender_email, "alerts@careclinic.com")
        self.assertEqual(log_entry.hospital, self.hospital_a)
        self.assertEqual(log_entry.status, "sent")


class TestEmailConfigurationRBAC(BaseHospitalTestCase):
    """Verify strict Role-Based Access Control on email configuration interfaces."""

    def setUp(self):
        super().setUp()
        self.hospital_a = self.create_hospital(name="Alpha Hospital", email="alpha@test.com")
        self.hospital_b = self.create_hospital(name="Beta Hospital", email="beta@test.com")

        self.super_admin = self.create_super_admin(username="sa_user")
        self.clinic_admin_a = self.create_clinic_admin(self.hospital_a, username="ca_alpha")
        self.clinic_admin_b = self.create_clinic_admin(self.hospital_b, username="ca_beta")
        self.staff_user = self.create_staff(self.hospital_a, username="staff_alpha")
        self.client_user = self.create_patient(self.hospital_a, username="patient_alpha")

    def test_super_admin_governance_access(self):
        """Super Admin can access email accounts dashboard, save accounts, and test connections."""
        self.client.force_login(self.super_admin)
        res = self.client.get(reverse("super_admin_email_accounts"))
        self.assertEqual(res.status_code, 200)

        # Create account via Super Admin
        save_data = {
            "name": "Super Admin SMTP",
            "account_type": "PLATFORM",
            "scope_type": "platform",
            "host": "smtp.google.com",
            "port": "587",
            "provider": "gmail",
            "username": "super@google.com",
            "password": "NewSecretPassword123",
            "from_email": "super@google.com",
            "from_name": "Super System",
            "use_tls": "on",
            "is_default": "on",
        }
        res_post = self.client.post(reverse("super_admin_email_account_save"), save_data)
        self.assertEqual(res_post.status_code, 302)
        account = EmailAccount.objects.filter(name="Super Admin SMTP").first()
        self.assertIsNotNone(account)
        self.assertEqual(account.get_password(), "NewSecretPassword123")

    def test_clinic_admin_own_clinic_access(self):
        """Clinic Admin can access and update their own clinic's email configuration."""
        self.client.force_login(self.clinic_admin_a)
        res = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(res.status_code, 200)

        # Save clinic SMTP
        data = {
            "name": "Alpha Dedicated Mailer",
            "provider": "smtp",
            "account_type": "CLINIC",
            "host": "mail.alpha.com",
            "port": "587",
            "username": "mailer@alpha.com",
            "password": "AlphaPassSecret456",
            "from_email": "mailer@alpha.com",
            "from_name": "Alpha Health",
            "reply_to": "info@alpha.com",
            "use_tls": "on",
        }
        res_save = self.client.post(reverse("admin_email_settings"), data)
        self.assertEqual(res_save.status_code, 302)

        alpha_account = EmailAccount.objects.filter(hospital=self.hospital_a).first()
        self.assertIsNotNone(alpha_account)
        self.assertEqual(alpha_account.host, "mail.alpha.com")
        self.assertEqual(alpha_account.get_password(), "AlphaPassSecret456")

    def test_clinic_admin_forbidden_from_super_admin_email_governance(self):
        """Clinic Admin cannot access platform-level email governance."""
        self.client.force_login(self.clinic_admin_a)
        res = self.client.get(reverse("super_admin_email_accounts"))
        self.assertIn(res.status_code, [302, 403])

    def test_staff_forbidden_from_email_settings(self):
        """Staff members are forbidden (403) from accessing email settings."""
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(res.status_code, 403)

    def test_client_forbidden_from_email_settings(self):
        """Client / Patient users are forbidden (403) from accessing email settings."""
        self.client.force_login(self.client_user)
        res = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(res.status_code, 403)


class TestDiagnosticConnectionTest(BaseHospitalTestCase):
    """Verify live connection test executes safely without credential leakage."""

    def test_test_account_connection_safe_output(self):
        """Verify diagnostic testing returns clean status and never leaks passwords."""
        raw_password = "VerySensitivePassword999!"
        account = EmailAccount.objects.create(
            name="Diagnostic Test Account",
            account_type="PLATFORM",
            scope_type="platform",
            host="smtp.gmail.com",
            port=587,
            username="test_diag@gmail.com",
            from_email="test_diag@gmail.com",
            from_name="Diagnostic Runner",
            is_active=True,
        )
        account.set_password(raw_password)
        account.save()

        ok, msg = run_account_connection_test(account, "mandaliatanvi1504@gmail.com")
        self.assertTrue(ok)
        self.assertIn("✅", msg)
        self.assertNotIn(raw_password, msg)
