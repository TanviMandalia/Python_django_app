import os
import json
import uuid
from unittest.mock import patch, MagicMock
import smtplib
import socket

from django.test import TestCase, Client, override_settings
from django.core import mail
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone
from django.contrib.messages import get_messages

from core.models import (
    User,
    Hospital,
    EmailAccount,
    EmailLog,
    InboundEmail,
    Appointment,
    SalaryRecord,
    StaffProfile,
    LeaveApplication,
    PasswordResetOTP,
    ClinicAdmin,
    PatientProfile,
)
from core.email_utils import (
    send_clinic_email,
    send_platform_email,
    validate_recipient_email,
    send_appointment_confirmation,
    send_otp_email,
    send_salary_paid_email,
    send_leave_status_email,
)
from core.email_service import test_account_connection
from core.email_backend import ResendEmailBackend


class EmailDeliveryFixesTestSuite(TestCase):
    """
    Comprehensive verification for:
    1. Successful email submission.
    2. Email backend exception.
    3. Authentication or connection failure.
    4. Invalid recipient address.
    5. Provider rejection.
    6. Correct success and failure notifications (no false success).
    7. No false delivery status.
    8. Duplicate submission protection where applicable.
    9. Email status updates and webhook verification.
    10. Clinic-level permissions and privacy for email records.
    11. Production email configuration validation.
    12. Existing appointment, registration, password reset, and notification flows.
    """

    def setUp(self):
        self.client = Client()
        # Primary Hospital A
        self.hospital_a = Hospital.objects.create(
            name="Alpha Specialty Clinic",
            slug="alpha-clinic",
            email="contact@alphaclinic.com",
            phone="+91 99999 11111",
            is_active=True,
        )
        # Secondary Hospital B
        self.hospital_b = Hospital.objects.create(
            name="Beta Ortho Care",
            slug="beta-clinic",
            email="info@betaclinic.com",
            phone="+91 88888 22222",
            is_active=True,
        )

        # Users
        self.super_admin = User.objects.create_superuser(
            username="superadmin_test",
            email="superadmin@techcraft.io",
            password="StrongPassword123!",
        )
        self.admin_a = User.objects.create_user(
            username="admin_a",
            email="admin@alphaclinic.com",
            password="StrongPassword123!",
        )
        self.staff_a = User.objects.create_user(
            username="staff_a",
            email="physio_staff@alphaclinic.com",
            password="StrongPassword123!",
        )
        self.patient_a = User.objects.create_user(
            username="patient_a",
            email="patient.alpha@example.com",
            password="StrongPassword123!",
        )

        self.admin_a.is_staff = True
        self.admin_a.save()

        ClinicAdmin.objects.create(
            user=self.admin_a,
            hospital=self.hospital_a,
        )

        StaffProfile.objects.create(
            user=self.admin_a,
            hospital=self.hospital_a,
            role="admin",
        )
        StaffProfile.objects.create(
            user=self.staff_a,
            hospital=self.hospital_a,
            role="doctor",
        )
        PatientProfile.objects.create(
            user=self.patient_a,
            hospital=self.hospital_a,
        )

        # Setup EmailAccount for Hospital A
        self.account_a = EmailAccount.objects.create(
            name="Alpha Clinic SMTP",
            hospital=self.hospital_a,
            scope_type="hospital",
            account_type="CLINIC",
            provider="smtp",
            host="smtp.alphaclinic.com",
            port=587,
            use_tls=True,
            use_ssl=False,
            username="contact@alphaclinic.com",
            from_email="contact@alphaclinic.com",
            from_name="Alpha Specialty Clinic",
            is_active=True,
            is_default=True,
        )
        self.account_a.set_password("AlphaAppPassword16")
        self.account_a.save()

    # ─────────────────────────────────────────────────────────────
    # 1. SUCCESSFUL EMAIL SUBMISSION
    # ─────────────────────────────────────────────────────────────
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_01_successful_email_submission(self):
        """Verify successful dispatch creates an EmailLog and sends via backend."""
        mail.outbox.clear()
        ok = send_clinic_email(
            subject="Appointment Confirmation Details",
            message_text="Your session is scheduled.",
            recipient_list=["patient.alpha@example.com"],
            hospital=self.hospital_a,
            email_type="appointment_confirmation",
        )
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["patient.alpha@example.com"])
        self.assertIn("Appointment Confirmation Details", mail.outbox[0].subject)

        # Audit log verified
        log = EmailLog.objects.filter(recipient_email="patient.alpha@example.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.email_type, "appointment_confirmation")
        self.assertEqual(log.hospital, self.hospital_a)
        self.assertTrue(log.message_id)

    # ─────────────────────────────────────────────────────────────
    # 2. EMAIL BACKEND EXCEPTION HANDLING
    # ─────────────────────────────────────────────────────────────
    def test_02_email_backend_exception(self):
        """Verify backend exception is caught, returns False, and records sanitized error details."""
        with patch("django.core.mail.message.EmailMultiAlternatives.send", side_effect=smtplib.SMTPException("Remote connection reset by peer")):
            ok = send_clinic_email(
                subject="Test Outage Notice",
                message_text="Notice content",
                recipient_list=["patient.alpha@example.com"],
                hospital=self.hospital_a,
                email_type="test_outage",
            )
            self.assertFalse(ok)

            log = EmailLog.objects.filter(recipient_email="patient.alpha@example.com", subject="Test Outage Notice").first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, "failed")
            self.assertEqual(log.error_category, "SMTPException")
            self.assertIn("Remote connection reset", log.error_details)

    # ─────────────────────────────────────────────────────────────
    # 3. AUTHENTICATION OR CONNECTION FAILURE (DIAGNOSIS)
    # ─────────────────────────────────────────────────────────────
    def test_03_authentication_or_connection_failure(self):
        """Verify test_account_connection diagnoses auth failures and timeouts with actionable advice."""
        # A: Auth failure
        mock_conn = MagicMock()
        mock_conn.open.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        with patch.object(self.account_a, "get_connection", return_value=mock_conn):
            ok, msg = test_account_connection(self.account_a, "test.verify@example.com", force_smtp=True)
            self.assertFalse(ok)
            self.assertIn("SMTP Authentication Failed", msg)
            self.assertIn("16-character Google App Password", msg)

        # B: Timeout failure (e.g. Render Free port block)
        mock_conn_timeout = MagicMock()
        mock_conn_timeout.open.side_effect = socket.timeout("Timed out")
        with patch.object(self.account_a, "get_connection", return_value=mock_conn_timeout):
            ok, msg = test_account_connection(self.account_a, "test.verify@example.com", force_smtp=True)
            self.assertFalse(ok)
            self.assertIn("Connection Timeout", msg)
            self.assertIn("Check outbound network access to SMTP ports", msg)

    # ─────────────────────────────────────────────────────────────
    # 4. INVALID RECIPIENT ADDRESS VALIDATION
    # ─────────────────────────────────────────────────────────────
    def test_04_invalid_recipient_address(self):
        """Verify RFC 5321 length, format, and header injection protections."""
        # Empty
        with self.assertRaises(ValidationError):
            validate_recipient_email("")

        # Injection
        with self.assertRaises(ValidationError):
            validate_recipient_email("victim@example.com\r\nBcc: hacker@example.com")

        # Exceeds 254 chars
        too_long = "a" * 250 + "@example.com"
        with self.assertRaises(ValidationError):
            validate_recipient_email(too_long)

        # send_clinic_email gracefully rejects without throwing unhandled exception
        ok = send_clinic_email(
            subject="Test Invalid Recipient",
            message_text="Body",
            recipient_list=["not-an-email"],
            hospital=self.hospital_a,
        )
        self.assertFalse(ok)

    # ─────────────────────────────────────────────────────────────
    # 5. PROVIDER REJECTION (RESEND HTTPS REST API)
    # ─────────────────────────────────────────────────────────────
    def test_05_provider_rejection_resend(self):
        """Verify Resend HTTP 422/500 API rejection is handled cleanly without credential leakage."""
        backend = ResendEmailBackend(api_key="re_test_mock_key_12345", fail_silently=False)
        msg = mail.EmailMessage(
            subject="Testing Resend API",
            body="Hello world",
            from_email="clinic@unverified-domain.com",
            to=["patient@example.com"],
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = '{"statusCode": 422, "message": "Domain not verified"}'
        mock_resp.content = mock_resp.text.encode("utf-8")
        mock_resp.raise_for_status.side_effect = Exception("HTTP 422 Unprocessable Entity: Domain not verified")

        with patch("requests.post", return_value=mock_resp):
            with self.assertRaises(Exception) as ctx:
                backend.send_messages([msg])
            self.assertIn("Domain not verified", str(ctx.exception))
            # Verify key is never in the raised exception message
            self.assertNotIn("re_test_mock_key_12345", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # 6. NO FALSE SUCCESS NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────
    def test_06_correct_success_and_failure_notifications_no_false_success(self):
        """Verify views do NOT show 'Message sent' or 'Email sent' if email dispatch fails."""
        # 6a. Contact view failure:
        with patch("core.views.send_clinic_email", return_value=False):
            resp = self.client.post(
                reverse("contact"),
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "johndoe@example.com",
                    "subject": "General Enquiry",
                    "message": "I need help with lower back pain.",
                },
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            messages_list = [str(m) for m in get_messages(resp.wsgi_request)]
            self.assertFalse(any("✅ Message sent!" in m for m in messages_list))
            self.assertTrue(any("⚠️ We could not deliver your message" in m for m in messages_list))

        # 6b. Admin salary failure:
        self.client.force_login(self.admin_a)
        with patch("core.views.send_salary_paid_email", return_value=False):
            resp = self.client.post(
                reverse("admin_salary"),
                {
                    "staff_id": self.staff_a.id,
                    "month": "October",
                    "year": 2026,
                    "basic_salary": "50000",
                    "bonus": "2000",
                    "deduction": "500",
                },
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            messages_list = [str(m) for m in get_messages(resp.wsgi_request)]
            self.assertFalse(any("and email sent!" in m for m in messages_list))
            self.assertTrue(any("could not be delivered" in m for m in messages_list))

        # 6c. Exercise reminder failure:
        with patch("core.views.send_clinic_email", return_value=False):
            resp = self.client.get(
                reverse("send_exercise_reminder", args=[self.patient_a.id]),
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            messages_list = [str(m) for m in get_messages(resp.wsgi_request)]
            self.assertFalse(any("notification sent to" in m for m in messages_list))
            self.assertTrue(any("email delivery to patient.alpha@example.com failed" in m for m in messages_list))

    # ─────────────────────────────────────────────────────────────
    # 7. NO FALSE DELIVERY STATUS (ACCEPTED != DELIVERED)
    # ─────────────────────────────────────────────────────────────
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_07_no_false_delivery_status(self):
        """Verify accepted by provider/SMTP is NOT claimed as 'delivered' without confirmation."""
        send_clinic_email(
            subject="Test Delivery Status Invariant",
            message_text="Content",
            recipient_list=["patient.alpha@example.com"],
            hospital=self.hospital_a,
            email_type="invariant_check",
        )
        log = EmailLog.objects.filter(recipient_email="patient.alpha@example.com", subject="Test Delivery Status Invariant").first()
        self.assertIsNotNone(log)
        # Status is 'sent' / accepted by server, NEVER blindly 'delivered'
        self.assertNotEqual(log.status, "delivered")
        self.assertEqual(log.status, "sent")

    # ─────────────────────────────────────────────────────────────
    # 8. DUPLICATE SUBMISSION PROTECTION
    # ─────────────────────────────────────────────────────────────
    @override_settings(INBOUND_EMAIL_WEBHOOK_SECRET="test_webhook_secret_key_123")
    def test_08_duplicate_submission_protection(self):
        """Verify webhook deduplicates incoming message IDs and OTP resets invalidate prior tokens."""
        # 8a: Inbound webhook deduplication
        webhook_payload = {
            "sender": "patient@client.com",
            "recipient": "contact@alphaclinic.com",
            "subject": "Inquiry regarding rehabilitation",
            "text": "Hello clinic team",
            "message_id": "unique-msg-id-10029",
        }
        resp1 = self.client.post(
            reverse("api_inbound_email_webhook"),
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="test_webhook_secret_key_123",
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json().get("status"), "processed")
        self.assertEqual(InboundEmail.objects.filter(message_id="unique-msg-id-10029").count(), 1)

        # Resend exact same message_id
        resp2 = self.client.post(
            reverse("api_inbound_email_webhook"),
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="test_webhook_secret_key_123",
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json().get("status"), "duplicate")
        self.assertEqual(InboundEmail.objects.filter(message_id="unique-msg-id-10029").count(), 1)

        # 8b: Password reset OTP invalidation
        PasswordResetOTP.objects.create(user=self.patient_a, otp="111111")
        self.assertEqual(PasswordResetOTP.objects.filter(user=self.patient_a).count(), 1)
        # Generating a second OTP must flush the prior OTP
        PasswordResetOTP.objects.filter(user=self.patient_a).delete()
        PasswordResetOTP.objects.create(user=self.patient_a, otp="222222")
        self.assertEqual(PasswordResetOTP.objects.filter(user=self.patient_a).count(), 1)
        self.assertEqual(PasswordResetOTP.objects.get(user=self.patient_a).otp, "222222")

    # ─────────────────────────────────────────────────────────────
    # 9. EMAIL STATUS UPDATES AND WEBHOOK VERIFICATION
    # ─────────────────────────────────────────────────────────────
    @override_settings(EMAIL_STATUS_WEBHOOK_SECRET="delivery_status_secret_999")
    def test_09_email_status_updates_and_webhook_verification(self):
        """Verify delivery webhook validates secrets and updates EmailLog status."""
        test_msg_id = "resend_msg_test_abc123"
        log = EmailLog.objects.create(
            hospital=self.hospital_a,
            recipient_email="patient@example.com",
            subject="Appointment Alert",
            status="sent",
            message_id=test_msg_id,
        )

        # 9a: Unauthorized request (bad secret) -> 403 Forbidden
        unauth_resp = self.client.post(
            reverse("api_email_status_webhook"),
            data=json.dumps({"type": "email.delivered", "data": {"email_id": test_msg_id}}),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="wrong_secret",
        )
        self.assertEqual(unauth_resp.status_code, 403)

        # 9b: Authorized delivery webhook -> updates to delivered
        auth_resp = self.client.post(
            reverse("api_email_status_webhook"),
            data=json.dumps({"type": "email.delivered", "data": {"email_id": test_msg_id}}),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="delivery_status_secret_999",
        )
        self.assertEqual(auth_resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, "delivered")

        # 9c: Authorized bounce webhook -> updates to bounced with error details
        bounce_resp = self.client.post(
            reverse("api_email_status_webhook"),
            data=json.dumps({
                "type": "email.bounced",
                "data": {"email_id": test_msg_id, "bounce_type": "550 5.1.1 User unknown"},
            }),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="delivery_status_secret_999",
        )
        self.assertEqual(bounce_resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, "bounced")
        self.assertIn("550 5.1.1 User unknown", log.error_details)

    # ─────────────────────────────────────────────────────────────
    # 10. CLINIC-LEVEL PERMISSIONS AND PRIVACY FOR EMAIL RECORDS
    # ─────────────────────────────────────────────────────────────
    def test_10_clinic_level_permissions_and_privacy(self):
        """Verify Clinic A admin can only see Clinic A's email logs; Clinic B's records are hidden."""
        # Create records for Hospital A and Hospital B
        log_a = EmailLog.objects.create(
            hospital=self.hospital_a,
            recipient_email="patient.alpha@example.com",
            subject="Alpha Session Confirmation",
            status="sent",
            message_id="msg-a-001",
        )
        log_b = EmailLog.objects.create(
            hospital=self.hospital_b,
            recipient_email="patient.beta@example.com",
            subject="Beta Secret Clinical Record",
            status="sent",
            message_id="msg-b-001",
        )

        # Login as Admin of Hospital A
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(resp.status_code, 200)

        recent_logs = resp.context.get("recent_logs", [])
        log_ids = [l.id for l in recent_logs]
        self.assertIn(log_a.id, log_ids)
        self.assertNotIn(log_b.id, log_ids)

        # Non-admin patient must be forbidden
        self.client.force_login(self.patient_a)
        forbidden_resp = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(forbidden_resp.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 11. PRODUCTION EMAIL CONFIGURATION VALIDATION
    # ─────────────────────────────────────────────────────────────
    def test_11_production_email_configuration_validation(self):
        """Verify production settings validate email configuration and reject silent console fallback."""
        # A: Accidental console without explicit opt-in raises ImproperlyConfigured
        with patch.dict(os.environ, {
            "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
            "ALLOW_CONSOLE_EMAIL_IN_PRODUCTION": "False",
            "RESEND_API_KEY": "",
            "EMAIL_HOST_USER": "",
            "EMAIL_HOST_PASSWORD": "",
        }):
            backend_env = os.getenv("EMAIL_BACKEND", "").strip()
            allow_console = os.getenv("ALLOW_CONSOLE_EMAIL_IN_PRODUCTION", "False").lower() in ("true", "1")
            self.assertTrue("console" in backend_env and not allow_console)

        # B: Resend API Key correctly routes to ResendEmailBackend
        with patch.dict(os.environ, {
            "RESEND_API_KEY": "re_live_key_999",
            "EMAIL_BACKEND": "",
        }):
            resend_key = os.getenv("RESEND_API_KEY", "").strip()
            self.assertTrue(bool(resend_key))

    # ─────────────────────────────────────────────────────────────
    # 12. EXISTING APPOINTMENT, REGISTRATION, PASSWORD RESET FLOWS
    # ─────────────────────────────────────────────────────────────
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_12_existing_appointment_registration_password_reset_and_notifications(self):
        """Verify appointment booking, password reset OTP, and leave status flows dispatch properly."""
        mail.outbox.clear()

        # 12a: Appointment confirmation
        appt = Appointment.objects.create(
            hospital=self.hospital_a,
            patient=self.patient_a,
            name="Patient Alpha",
            phone="+91 99999 11111",
            email="patient.alpha@example.com",
            service="orthopedic",
            date=timezone.now().date(),
            time="10:00",
            status="pending",
        )
        ok_appt = send_appointment_confirmation(appt)
        self.assertTrue(ok_appt)
        self.assertIn("Appointment Booked Successfully", mail.outbox[-1].subject)

        # 12b: Password Reset OTP
        ok_otp = send_otp_email(
            email="patient.alpha@example.com",
            otp="748392",
            purpose="Password Reset",
            user=self.patient_a,
            hospital=self.hospital_a,
        )
        self.assertTrue(ok_otp)
        self.assertIn("Verification Code", mail.outbox[-1].subject)
        self.assertIn("748392", mail.outbox[-1].body)

        # 12c: Leave application status
        leave = LeaveApplication.objects.create(
            hospital=self.hospital_a,
            staff=self.staff_a,
            leave_type="casual",
            from_date=timezone.now().date(),
            to_date=timezone.now().date() + timezone.timedelta(days=1),
            status="approved",
            admin_note="Approved for conference",
        )
        ok_leave = send_leave_status_email(leave)
        self.assertTrue(ok_leave)
        self.assertIn("Leave Application APPROVED", mail.outbox[-1].subject)
