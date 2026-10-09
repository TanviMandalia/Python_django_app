from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from core.models import EmailLog
from core.email_utils import send_platform_email, send_clinic_email
from tests.test_helpers import BaseHospitalTestCase

class EmailAuditAndOtpRetentionTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Central Care Clinic", slug="central-care")
        self.user = self.create_patient(hospital=self.hospital, username="test_patient", email="patient@example.com")

    def test_send_platform_email_creates_audit_log(self):
        success = send_platform_email(
            subject="Welcome to SaaS Platform",
            message_text="Your account is activated.",
            recipient_list=["patient@example.com"],
            email_type="welcome"
        )
        self.assertTrue(success)
        log = EmailLog.objects.filter(recipient_email="patient@example.com", email_type="welcome").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.direction, "outgoing")
        self.assertEqual(log.status, "sent")
        self.assertFalse(log.is_otp)
        self.assertIsNone(log.expires_at)

    def test_send_otp_email_creates_audit_log_with_24h_expiry(self):
        success = send_platform_email(
            subject="Your Login Security Code",
            message_text="Use verification code 849201 to authenticate your session.",
            recipient_list=["patient@example.com"],
            email_type="otp_login"
        )
        self.assertTrue(success)
        log = EmailLog.objects.filter(recipient_email="patient@example.com", email_type="otp_login").first()
        self.assertIsNotNone(log)
        self.assertTrue(log.is_otp)
        self.assertIsNotNone(log.expires_at)
        expected_expiry_min = timezone.now() + timedelta(hours=23, minutes=50)
        expected_expiry_max = timezone.now() + timedelta(hours=24, minutes=10)
        self.assertTrue(expected_expiry_min <= log.expires_at <= expected_expiry_max)

    def test_send_clinic_email_with_otp_flag(self):
        success = send_clinic_email(
            hospital=self.hospital,
            subject="Clinical Portal 2FA Verification",
            message_text="Your temporary verification token is ready.",
            recipient_list=["patient@example.com"],
            email_type="otp_verification"
        )
        self.assertTrue(success)
        log = EmailLog.objects.filter(hospital=self.hospital, email_type="otp_verification").first()
        self.assertIsNotNone(log)
        self.assertTrue(log.is_otp)
        self.assertIsNotNone(log.expires_at)

    def test_cleanup_expired_otp_logs_command(self):
        now = timezone.now()

        expired_otp_log = EmailLog.objects.create(
            sender_email="platform@example.com",
            recipient_email="expired@example.com",
            subject="Expired OTP Code",
            email_type="otp",
            status="sent",
            direction="outgoing",
            is_otp=True,
            expires_at=now - timedelta(hours=1),
            sent_at=now - timedelta(hours=25)
        )

        active_otp_log = EmailLog.objects.create(
            sender_email="platform@example.com",
            recipient_email="active_otp@example.com",
            subject="Active OTP Code",
            email_type="otp",
            status="sent",
            direction="outgoing",
            is_otp=True,
            expires_at=now + timedelta(hours=23),
            sent_at=now - timedelta(hours=1)
        )

        general_log = EmailLog.objects.create(
            sender_email="platform@example.com",
            recipient_email="patient@example.com",
            subject="Appointment Confirmation",
            email_type="appointment_reminder",
            status="sent",
            direction="outgoing",
            is_otp=False,
            expires_at=None,
            sent_at=now - timedelta(days=30)
        )

        call_command("cleanup_expired_otp_logs", "--dry-run")
        self.assertTrue(EmailLog.objects.filter(id=expired_otp_log.id).exists())
        self.assertTrue(EmailLog.objects.filter(id=active_otp_log.id).exists())
        self.assertTrue(EmailLog.objects.filter(id=general_log.id).exists())

        call_command("cleanup_expired_otp_logs")

        self.assertFalse(EmailLog.objects.filter(id=expired_otp_log.id).exists())
        self.assertTrue(EmailLog.objects.filter(id=active_otp_log.id).exists())
        self.assertTrue(EmailLog.objects.filter(id=general_log.id).exists())

    def test_cleanup_command_is_idempotent(self):
        call_command("cleanup_expired_otp_logs")
        call_command("cleanup_expired_otp_logs")
