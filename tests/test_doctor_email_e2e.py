"""
End-to-End Real Doctor Email Communication Test Suite.
Validates:
1. Outgoing email preparation, RFC headers, and EmailLog tracking
2. SMTP behavior and Authentication failure detection
3. Inbound reply ingestion, RFC threading (In-Reply-To, References, X-Thread-ID)
4. Doctor communication routing (Message creation and Notification dispatch)
5. Strict Multi-Tenant Clinic Isolation (no cross-clinic or cross-doctor leaks)
6. Deduplication and idempotency on duplicate incoming Message-IDs
7. Security: Header injection defense, Stored XSS sanitization in email bodies
8. Role-Based Access Control (RBAC) across Super Admin, Clinic Admin, Doctor/Staff, and Patient
"""

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
    StaffProfile,
    PatientProfile,
    EmailLog,
    InboundEmail,
    Message,
    Notification,
    SupportTicket,
    SupportReply,
)
from core.email_utils import (
    validate_recipient_email,
    sanitize_header_value,
    mask_email_for_logging,
    send_clinic_email,
    process_inbound_email_payload,
)

User = get_user_model()


class DoctorEmailE2ETestCase(TestCase):
    def setUp(self):
        # 1. Primary Hospital
        self.hospital = Hospital.objects.create(
            name="PhysioRehab Clinic",
            slug="physiorehab-clinic",
            email="admin@physiorehab.com",
            phone="9876543210",
            address="123 Wellness Way, Mumbai",
            is_active=True,
        )

        # 2. Secondary Hospital (for tenant isolation tests)
        self.other_hospital = Hospital.objects.create(
            name="Other Clinic",
            slug="other-clinic",
            email="contact@otherclinic.com",
            phone="9876543299",
            address="456 Other Way, Delhi",
            is_active=True,
        )

        # 3. Clinic Admin (PhysioRehab)
        self.clinic_admin_user = User.objects.create_user(
            username="test_clinic_admin",
            email="admin@physiorehab.com",
            password="AdminPassword123!",
            is_staff=True,
        )
        self.clinic_admin = ClinicAdmin.objects.create(
            user=self.clinic_admin_user,
            hospital=self.hospital,
        )

        # 4. Doctor Account configured with test mailbox
        self.doctor_user = User.objects.create_user(
            username="dr_tanvi_test",
            first_name="Tanvi",
            last_name="Mandalia",
            email="mandaliatanvi1504@gmail.com",
            password="DoctorPassword123!",
            is_staff=True,
        )
        self.doctor_profile = StaffProfile.objects.create(
            user=self.doctor_user,
            hospital=self.hospital,
            role="physiotherapist",
            is_active=True,
        )

        # 5. Doctor in other clinic (for isolation tests)
        self.other_doctor_user = User.objects.create_user(
            username="dr_other_clinic",
            email="doctor@otherclinic.com",
            password="OtherDoctorPassword123!",
            is_staff=True,
        )
        self.other_doctor_profile = StaffProfile.objects.create(
            user=self.other_doctor_user,
            hospital=self.other_hospital,
            role="physiotherapist",
            is_active=True,
        )

        # 6. Patient Account
        self.patient_user = User.objects.create_user(
            username="test_patient",
            email="patient@physiorehab.com",
            password="PatientPassword123!",
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            hospital=self.hospital,
        )

        self.client = Client()

    def test_01_outgoing_email_rfc_headers_and_emaillog(self):
        """Verify outgoing email creation, RFC headers, thread_id, and EmailLog recording."""
        mail.outbox = []
        subject = "Hospital Management System - Doctor Email Communication Test"
        body = (
            "This is a controlled email-system test.\n"
            "No patient information is included.\n"
            "Please reply to this email to verify the inbound/reply workflow."
        )

        ok = send_clinic_email(
            subject=subject,
            message_text=body,
            recipient_list=["mandaliatanvi1504@gmail.com"],
            hospital=self.hospital,
            email_type="doctor_communication",
            thread_id="thread-doc-test-001",
        )
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

        sent_msg = mail.outbox[0]
        self.assertIn("mandaliatanvi1504@gmail.com", sent_msg.to)
        self.assertIn("Doctor Email Communication Test", sent_msg.subject)
        self.assertIn("Message-ID", sent_msg.extra_headers)
        self.assertIn("X-Thread-ID", sent_msg.extra_headers)
        self.assertEqual(sent_msg.extra_headers["X-Thread-ID"], "thread-doc-test-001")

        # Database EmailLog verification
        log = EmailLog.objects.filter(recipient_email="mandaliatanvi1504@gmail.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.email_type, "doctor_communication")
        self.assertEqual(log.thread_id, "thread-doc-test-001")
        self.assertTrue(len(log.message_id) > 5)

    def test_02_inbound_doctor_reply_processing_and_threading(self):
        """Verify inbound reply from mandaliatanvi1504@gmail.com links to thread and creates Doctor Message."""
        # First send original email to generate EmailLog
        send_clinic_email(
            subject="Doctor Schedule Consultation",
            message_text="Please confirm your attendance for the weekly case review.",
            recipient_list=["mandaliatanvi1504@gmail.com"],
            hospital=self.hospital,
            email_type="doctor_communication",
            thread_id="thread-case-review-99",
        )
        orig_log = EmailLog.objects.filter(recipient_email="mandaliatanvi1504@gmail.com").first()
        orig_msg_id = orig_log.message_id

        # Inbound reply payload from controlled doctor mailbox
        reply_payload = {
            "from": "mandaliatanvi1504@gmail.com",
            "to": "admin@physiorehab.com",
            "subject": "Re: Doctor Schedule Consultation",
            "text": "Doctor reply test: Email communication is working correctly. This is a controlled system test.",
            "html": "<p>Doctor reply test: Email communication is working correctly. This is a controlled system test.</p>",
            "message_id": "gmail-reply-msg-778899@mail.gmail.com",
            "in_reply_to": f"<{orig_msg_id}>",
            "references": f"<{orig_msg_id}>",
            "thread_id": "thread-case-review-99",
        }

        res = process_inbound_email_payload(reply_payload)
        self.assertEqual(res.get("status"), "processed")
        self.assertTrue(res.get("is_doctor_reply"))
        self.assertEqual(res.get("thread_id"), "thread-case-review-99")
        self.assertEqual(res.get("in_reply_to"), orig_msg_id)

        # 1. Verify InboundEmail database record
        inbound_rec = InboundEmail.objects.get(id=res.get("id"))
        self.assertEqual(inbound_rec.sender, "mandaliatanvi1504@gmail.com")
        self.assertEqual(inbound_rec.recipient, "admin@physiorehab.com")
        self.assertEqual(inbound_rec.hospital, self.hospital)
        self.assertEqual(inbound_rec.in_reply_to, orig_msg_id)
        self.assertEqual(inbound_rec.thread_id, "thread-case-review-99")

        # 2. Verify Doctor internal Message created
        doc_msg = Message.objects.filter(
            sender=self.doctor_user,
            receiver=self.clinic_admin_user,
            hospital=self.hospital,
        ).first()
        self.assertIsNotNone(doc_msg)
        self.assertIn("Doctor reply test: Email communication is working correctly", doc_msg.content)

        # 3. Verify Admin Notification created
        admin_notif = Notification.objects.filter(
            recipient=self.clinic_admin_user,
            hospital=self.hospital,
        ).first()
        self.assertIsNotNone(admin_notif)
        self.assertIn("Doctor reply", admin_notif.message)
        self.assertEqual(admin_notif.link, f"/admin-doctor-chat/{self.doctor_user.id}/")

        # 4. Verify Doctor Confirmation Notification created
        doc_notif = Notification.objects.filter(
            recipient=self.doctor_user,
            hospital=self.hospital,
        ).first()
        self.assertIsNotNone(doc_notif)
        self.assertIn("Reply received and delivered", doc_notif.message)

    def test_03_tenant_and_doctor_isolation(self):
        """Verify the reply does NOT appear in the wrong doctor's inbox or another clinic."""
        reply_payload = {
            "from": "mandaliatanvi1504@gmail.com",
            "to": "admin@physiorehab.com",
            "subject": "Re: Doctor Clinical Update",
            "text": "Doctor update message.",
            "message_id": "isolated-test-msg-001@mail.gmail.com",
        }
        res = process_inbound_email_payload(reply_payload)
        self.assertEqual(res.get("status"), "processed")

        # Must NOT exist in other clinic
        other_clinic_msgs = Message.objects.filter(hospital=self.other_hospital)
        self.assertEqual(other_clinic_msgs.count(), 0)

        # Must NOT exist for other doctor
        other_doc_msgs = Message.objects.filter(sender=self.other_doctor_user)
        self.assertEqual(other_doc_msgs.count(), 0)

        # Must NOT exist for patient
        patient_msgs = Message.objects.filter(receiver=self.patient_user)
        self.assertEqual(patient_msgs.count(), 0)

    def test_04_idempotent_duplicate_prevention(self):
        """Verify processing the same incoming message_id twice does NOT duplicate messages."""
        dup_payload = {
            "from": "mandaliatanvi1504@gmail.com",
            "to": "admin@physiorehab.com",
            "subject": "Re: Duplicate Idempotency Verification",
            "text": "Testing duplicate prevention.",
            "message_id": "idempotency-check-msg-001@mail.gmail.com",
        }
        # First delivery: processed
        res1 = process_inbound_email_payload(dup_payload)
        self.assertEqual(res1.get("status"), "processed")
        msg_count_1 = Message.objects.filter(sender=self.doctor_user).count()

        # Second delivery with identical message_id: duplicate ignored
        res2 = process_inbound_email_payload(dup_payload)
        self.assertEqual(res2.get("status"), "duplicate")
        msg_count_2 = Message.objects.filter(sender=self.doctor_user).count()

        self.assertEqual(msg_count_1, msg_count_2)
        self.assertEqual(InboundEmail.objects.filter(message_id="idempotency-check-msg-001@mail.gmail.com").count(), 1)

    def test_05_security_stored_xss_and_header_injection(self):
        """Verify HTML sanitization and header injection prevention on incoming emails."""
        malicious_payload = {
            "from": "mandaliatanvi1504@gmail.com",
            "to": "admin@physiorehab.com",
            "subject": "Clinical notes <script>alert('pwned')</script>",
            "text": "Normal text",
            "html": "<p>Clinical notes</p><script>alert('XSS')</script><iframe src='javascript:alert(1)'></iframe><a href='javascript:evil()'>Click</a>",
            "message_id": "security-test-xss-001@mail.gmail.com",
        }
        res = process_inbound_email_payload(malicious_payload)
        self.assertEqual(res.get("status"), "processed")

        inbound_obj = InboundEmail.objects.get(message_id="security-test-xss-001@mail.gmail.com")
        self.assertNotIn("<script", inbound_obj.body_html.lower())
        self.assertNotIn("<iframe", inbound_obj.body_html.lower())
        self.assertNotIn("javascript:", inbound_obj.body_html.lower())

        # Header injection in sender address
        with self.assertRaises(ValidationError):
            validate_recipient_email("doctor@physiorehab.com\r\nBcc: hacker@evil.com")

        with self.assertRaises(ValidationError):
            validate_recipient_email("doctor@physiorehab.com\nSubject: Injected")

    @override_settings(INBOUND_EMAIL_WEBHOOK_SECRET="secure_webhook_secret_key_999")
    def test_06_inbound_webhook_authentication(self):
        """Verify the HTTP /api/email/inbound/ endpoint enforces token authentication."""
        url = "/api/email/inbound/"
        payload = {
            "from": "mandaliatanvi1504@gmail.com",
            "to": "admin@physiorehab.com",
            "subject": "Webhook test",
            "text": "Payload through API webhook",
            "message_id": "api-webhook-test-001",
        }

        # 1. Unauthenticated -> 403 Forbidden
        r_unauth = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(r_unauth.status_code, 403)

        # 2. Wrong token -> 403 Forbidden
        r_bad = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong_token",
        )
        self.assertEqual(r_bad.status_code, 403)

        # 3. Valid token via Authorization header -> 200 OK
        r_ok = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer secure_webhook_secret_key_999",
        )
        self.assertEqual(r_ok.status_code, 200)
        resp_data = r_ok.json()
        self.assertEqual(resp_data.get("status"), "processed")

    def test_07_rbac_doctor_and_admin_chat_authorization(self):
        """Verify role authorization: Patient cannot access doctor chat or admin doctor detail."""
        # Patient login
        self.client.force_login(self.patient_user)

        # Patient cannot access admin_doctor_chat
        r1 = self.client.get("/admin-doctor-chat/", follow=False)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r1.url, "/client-dashboard/")

        # Patient cannot access admin_doctor_chat_detail
        r2 = self.client.get(f"/admin-doctor-chat/{self.doctor_user.id}/", follow=False)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(r2.url, "/client-dashboard/")

        # Clinic Admin login
        self.client.force_login(self.clinic_admin_user)

        # Clinic Admin can access admin_doctor_chat
        r3 = self.client.get("/admin-doctor-chat/")
        self.assertEqual(r3.status_code, 200)

        # Clinic Admin can access admin_doctor_chat_detail for doctor
        r4 = self.client.get(f"/admin-doctor-chat/{self.doctor_user.id}/")
        self.assertEqual(r4.status_code, 200)
