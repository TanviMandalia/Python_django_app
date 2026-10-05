import json
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.core import mail
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import (
    Hospital,
    ClinicAdmin,
    PatientProfile,
    Appointment,
    EmailLog,
    InboundEmail,
    SupportTicket,
    SupportReply,
    Notification,
)
from core.email_utils import (
    validate_recipient_email,
    sanitize_header_value,
    mask_email_for_logging,
    send_clinic_email,
    send_welcome_email,
    send_password_reset_otp_email,
    send_appointment_confirmation_email,
    send_appointment_status_update,
    send_appointment_cancellation_email,
    send_invoice_email,
    process_inbound_email_payload,
)

User = get_user_model()


class EmailSystemTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Apex Specialty Clinic",
            slug="apex-clinic",
            email="contact@apexclinic.com",
            phone="9876543210",
            address="123 Health Ave, Mumbai",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username="apex_admin",
            email="admin@apexclinic.com",
            password="SecureAdminPassword123!",
            is_staff=True,
        )
        self.clinic_admin = ClinicAdmin.objects.create(
            user=self.admin_user,
            hospital=self.hospital,
        )
        self.patient_user = User.objects.create_user(
            username="john_patient",
            email="john.patient@example.com",
            password="SecurePatientPassword123!",
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            hospital=self.hospital,
        )
        self.appointment = Appointment.objects.create(
            hospital=self.hospital,
            patient=self.patient_user,
            name="John Patient",
            email="john.patient@example.com",
            phone="9876543211",
            service="orthopedic",
            date=timezone.now().date(),
            time="10:00 AM",
            status="confirmed",
        )
        self.client = Client()

    def test_email_validation_and_header_injection_defense(self):
        # Valid email
        clean = validate_recipient_email("  User.Test@Example.COM  ")
        self.assertEqual(clean, "user.test@example.com")

        # Header injection attempt with newlines
        with self.assertRaises(ValidationError):
            validate_recipient_email("victim@example.com\nBcc: hacker@example.com")

        with self.assertRaises(ValidationError):
            validate_recipient_email("victim@example.com\r\nSubject: Injected")

        # Over-length email
        long_email = "a" * 250 + "@example.com"
        with self.assertRaises(ValidationError):
            validate_recipient_email(long_email)

        # Subject sanitization
        dirty_subject = "Appointment Confirmed\r\nBcc: hacker@example.com\n"
        clean_subject = sanitize_header_value(dirty_subject)
        self.assertNotIn("\r", clean_subject)
        self.assertNotIn("\n", clean_subject)
        self.assertIn("Appointment Confirmed", clean_subject)

    def test_mask_email_for_logging(self):
        self.assertEqual(mask_email_for_logging("patient@hospital.com"), "p*****t@hospital.com")
        self.assertEqual(mask_email_for_logging("ab@test.com"), "a*@test.com")
        self.assertEqual(mask_email_for_logging("invalid"), "***")

    def test_outgoing_send_and_emaillog_tracking(self):
        mail.outbox = []
        success = send_clinic_email(
            subject="Test Clinic Notification",
            message_text="This is a test notification body.",
            recipient_list=["patient@example.com"],
            hospital=self.hospital,
            email_type="notification",
        )
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("Test Clinic Notification", sent.subject)
        self.assertIn("patient@example.com", sent.to)

        # Verify EmailLog in database
        log_entry = EmailLog.objects.filter(recipient_email="patient@example.com").first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.status, "sent")
        self.assertEqual(log_entry.email_type, "notification")
        self.assertEqual(log_entry.hospital, self.hospital)

    def test_all_outgoing_template_functions(self):
        mail.outbox = []

        # 1. Welcome email
        ok1 = send_welcome_email(self.patient_user, hospital=self.hospital)
        self.assertTrue(ok1)

        # 2. OTP email
        ok2 = send_password_reset_otp_email(self.patient_user.email, "654321")
        self.assertTrue(ok2)

        # 3. Appointment confirmation
        ok3 = send_appointment_confirmation_email(self.appointment)
        self.assertTrue(ok3)

        # 4. Status update
        self.appointment.status = "completed"
        ok4 = send_appointment_status_update(self.appointment)
        self.assertTrue(ok4)

        # 5. Cancellation
        ok5 = send_appointment_cancellation_email(self.appointment, reason="Doctor emergency")
        self.assertTrue(ok5)

        # 6. Invoice email
        ok6 = send_invoice_email(
            self.patient_user,
            invoice_num="INV-2026-001",
            amount=Decimal("1500.00"),
            description="Physiotherapy Initial Consultation",
            hospital=self.hospital,
        )
        self.assertTrue(ok6)

        self.assertEqual(len(mail.outbox), 6)

    def test_inbound_email_processing_and_deduplication(self):
        inbound_payload = {
            "sender": "inquiry@clientdomain.com",
            "recipient": "contact@apexclinic.com",
            "subject": "Inquiry regarding rehabilitation session",
            "text": "Hello, I would like to know if you accept insurance.",
            "html": "<p>Hello, I would like to know if you accept insurance.</p><script>alert('hack')</script>",
            "message_id": "msg-unique-1001",
        }

        # First delivery: processed
        res1 = process_inbound_email_payload(inbound_payload)
        self.assertEqual(res1.get("status"), "processed")
        inbound_id = res1.get("id")

        inbound_record = InboundEmail.objects.get(id=inbound_id)
        self.assertEqual(inbound_record.sender, "inquiry@clientdomain.com")
        self.assertEqual(inbound_record.recipient, "contact@apexclinic.com")
        self.assertEqual(inbound_record.hospital, self.hospital)
        # HTML script tag must have been sanitized
        self.assertNotIn("<script", inbound_record.body_html.lower())

        # Notification created for clinic admin
        notif = Notification.objects.filter(recipient=self.admin_user).first()
        self.assertIsNotNone(notif)
        self.assertIn("inquiry@clientdomain.com", notif.message)

        # Second delivery with same message_id: must be ignored as duplicate (Idempotency)
        res2 = process_inbound_email_payload(inbound_payload)
        self.assertEqual(res2.get("status"), "duplicate")
        self.assertEqual(InboundEmail.objects.filter(message_id="msg-unique-1001").count(), 1)

    def test_inbound_email_support_ticket_routing(self):
        # Create a support ticket
        ticket = SupportTicket.objects.create(
            hospital=self.hospital,
            submitted_by=self.admin_user,
            subject="Billing system query",
            message="Need clarification on invoice export",
            status="open",
        )

        inbound_payload = {
            "sender": "support@partner.com",
            "recipient": "contact@apexclinic.com",
            "subject": f"Re: [Ticket #{ticket.id}] Billing system query",
            "text": "We have reviewed your request and updated the settings.",
            "message_id": f"msg-ticket-{ticket.id}-001",
        }

        res = process_inbound_email_payload(inbound_payload)
        self.assertEqual(res.get("status"), "processed")

        # Verify SupportReply was created automatically
        reply = SupportReply.objects.filter(ticket=ticket).first()
        self.assertIsNotNone(reply)
        self.assertIn("We have reviewed your request", reply.message)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "in_progress")

    @override_settings(INBOUND_EMAIL_WEBHOOK_SECRET="test_webhook_secret_key_123")
    def test_api_inbound_email_webhook_authentication(self):
        url = "/api/email/inbound/"
        payload = {
            "from": "patient@domain.com",
            "to": "contact@apexclinic.com",
            "subject": "Appointment reschedule request",
            "text": "Can I move my appointment to Friday?",
            "message_id": "webhook-msg-001",
        }

        # 1. GET request rejected (405)
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 405)

        # 2. POST without secret rejected (403)
        resp_no_auth = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp_no_auth.status_code, 403)

        # 3. POST with wrong secret rejected (403)
        resp_bad_auth = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="wrong_secret",
        )
        self.assertEqual(resp_bad_auth.status_code, 403)

        # 4. POST with correct Bearer token accepted (200)
        resp_valid = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test_webhook_secret_key_123",
        )
        self.assertEqual(resp_valid.status_code, 200)
        data = resp_valid.json()
        self.assertEqual(data.get("status"), "processed")
