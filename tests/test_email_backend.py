"""
Automated unit tests for Resend HTTPS Email Backend, System Checks,
and Resilient Appointment Booking Workflow.
"""
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.core.mail import EmailMultiAlternatives, EmailMessage, get_connection
from django.core.exceptions import ImproperlyConfigured
from django.contrib.messages import get_messages
from django.urls import reverse

from core.email_backend import ResendEmailBackend
from core.models import User, Hospital, Appointment, EmailAccount, PatientProfile
from core.checks import check_smtp_configuration


class ResendEmailBackendTests(TestCase):
    """Test suite for Resend HTTPS REST API email backend."""

    def test_missing_api_key_raises_improperly_configured(self):
        backend = ResendEmailBackend(api_key="", fail_silently=False)
        msg = EmailMessage(
            subject="Test",
            body="Hello",
            from_email="clinic@example.com",
            to=["patient@example.com"],
        )
        with self.assertRaises(ImproperlyConfigured):
            backend.send_messages([msg])

    def test_missing_api_key_fail_silently(self):
        backend = ResendEmailBackend(api_key="", fail_silently=True)
        msg = EmailMessage(
            subject="Test",
            body="Hello",
            from_email="clinic@example.com",
            to=["patient@example.com"],
        )
        sent = backend.send_messages([msg])
        self.assertEqual(sent, 0)

    @patch("requests.post")
    def test_successful_send_message(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "msg_test_123"}'
        mock_response.json.return_value = {"id": "msg_test_123"}
        mock_post.return_value = mock_response

        backend = ResendEmailBackend(api_key="re_test_key_12345", fail_silently=False)
        msg = EmailMultiAlternatives(
            subject="Appointment Confirmation",
            body="Your appointment is confirmed.",
            from_email="PhysioRehab Clinic <onboarding@resend.dev>",
            to=["patient@example.com"],
            reply_to=["support@physiorehab.com"],
            headers={"X-Entity-Ref-ID": "ref-456"},
        )
        msg.attach_alternative("<p>Your appointment is <strong>confirmed</strong>.</p>", "text/html")
        msg.attach("instructions.txt", "Please bring your medical report.", "text/plain")

        sent = backend.send_messages([msg])
        self.assertEqual(sent, 1)

        self.assertTrue(mock_post.called)
        call_kwargs = mock_post.call_args[1]
        self.assertIn("Authorization", call_kwargs["headers"])
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer re_test_key_12345")

        payload = call_kwargs["json"]
        self.assertEqual(payload["to"], ["patient@example.com"])
        self.assertEqual(payload["subject"], "Appointment Confirmation")
        self.assertEqual(payload["text"], "Your appointment is confirmed.")
        self.assertEqual(payload["html"], "<p>Your appointment is <strong>confirmed</strong>.</p>")
        self.assertEqual(payload["reply_to"], ["support@physiorehab.com"])
        self.assertEqual(payload["headers"]["X-Entity-Ref-ID"], "ref-456")
        self.assertEqual(len(payload["attachments"]), 1)
        self.assertEqual(payload["attachments"][0]["filename"], "instructions.txt")

    @patch("requests.post")
    def test_api_rejection_error_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = '{"message": "Domain not verified"}'
        mock_response.raise_for_status.side_effect = Exception("HTTP 422 Unprocessable Entity")
        mock_post.return_value = mock_response

        backend = ResendEmailBackend(api_key="re_test_key_12345", fail_silently=False)
        msg = EmailMessage(
            subject="Test",
            body="Hello",
            from_email="clinic@unverified.com",
            to=["patient@example.com"],
        )

        with self.assertRaises(Exception):
            backend.send_messages([msg])

    @patch("requests.post")
    def test_api_rejection_fail_silently(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"message": "Internal Server Error"}'
        mock_post.return_value = mock_response

        backend = ResendEmailBackend(api_key="re_test_key_12345", fail_silently=True)
        msg = EmailMessage(
            subject="Test",
            body="Hello",
            from_email="clinic@example.com",
            to=["patient@example.com"],
        )

        sent = backend.send_messages([msg])
        self.assertEqual(sent, 0)


class EmailSystemChecksTests(TestCase):
    """Test system checks for Resend and SMTP email configurations."""

    @override_settings(
        EMAIL_BACKEND="core.email_backend.ResendEmailBackend",
        RESEND_API_KEY="",
        DEFAULT_FROM_EMAIL="test@example.com",
        DEBUG=False,
    )
    def test_resend_check_missing_api_key_production(self):
        errors = check_smtp_configuration(None)
        self.assertTrue(any(e.id == "core.E003" for e in errors))

    @override_settings(
        EMAIL_BACKEND="core.email_backend.ResendEmailBackend",
        RESEND_API_KEY="re_valid_test_key",
        DEFAULT_FROM_EMAIL="clinic@physiorehab.com",
        DEBUG=False,
    )
    def test_resend_check_valid_configuration(self):
        errors = check_smtp_configuration(None)
        self.assertEqual(len(errors), 0)


class AppointmentBookingReliabilityTests(TestCase):
    """Test appointment booking persistence and resilient email notification handling."""

    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Apex Physio Clinic",
            slug="apex-physio",
            email="admin@apexphysio.com",
            phone="9876543210",
        )
        self.patient = User.objects.create_user(
            username="testpatient",
            email="patient@example.com",
            password="TestPassword123!",
        )
        self.profile = PatientProfile.objects.create(
            user=self.patient,
            hospital=self.hospital,
        )
        self.client.login(username="testpatient", password="TestPassword123!")

    def test_booking_succeeds_even_when_email_fails(self):
        """
        When email provider fails or times out, the appointment MUST still be persisted
        in the database, and the user must be notified that the booking is saved.
        """
        booking_data = {
            "name": "Test Patient",
            "email": "patient@example.com",
            "phone": "9876543210",
            "service": "orthopedic",
            "date": (date.today() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "time": "10:00",
            "notes": "Recovering from ankle sprain",
        }

        # Mock email confirmation throwing an unexpected exception
        with patch("core.views.send_appointment_confirmation", side_effect=Exception("Render SMTP block simulation")):
            response = self.client.post(reverse("book_appointment"), booking_data, follow=True)

        self.assertEqual(response.status_code, 200)

        # Database record must exist
        appt = Appointment.objects.filter(
            patient=self.patient,
            service="orthopedic",
            time="10:00",
        ).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.status, "pending")

        # User messages must show appointment secured, not a failure
        messages = list(get_messages(response.wsgi_request))
        msg_texts = [str(m) for m in messages]
        self.assertTrue(any("Appointment booked" in t for t in msg_texts))

    def test_booking_succeeds_with_successful_email(self):
        """When email succeeds, confirmation message specifies email sent."""
        booking_data = {
            "name": "Test Patient",
            "email": "patient@example.com",
            "phone": "9876543210",
            "service": "sports",
            "date": (date.today() + timedelta(days=3)).strftime("%Y-%m-%d"),
            "time": "11:00",
            "notes": "Knee rehabilitation",
        }

        with patch("core.views.send_appointment_confirmation", return_value=True):
            response = self.client.post(reverse("book_appointment"), booking_data, follow=True)

        self.assertEqual(response.status_code, 200)
        appt = Appointment.objects.filter(
            patient=self.patient,
            service="sports",
            time="11:00",
        ).first()
        self.assertIsNotNone(appt)

        messages = list(get_messages(response.wsgi_request))
        msg_texts = [str(m) for m in messages]
        self.assertTrue(any("Confirmation email sent" in t for t in msg_texts))
