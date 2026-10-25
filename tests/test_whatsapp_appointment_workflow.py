import pytest
import urllib.parse
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from core.models import PublicAppointmentRequest, Appointment, Hospital, ClinicAdmin
from core.whatsapp import (
    sanitize_phone_to_international,
    get_doctor_whatsapp_number,
    build_whatsapp_appointment_message,
    build_whatsapp_click_to_chat_url,
    build_doctor_to_patient_whatsapp_url,
)


@pytest.mark.django_db
class TestWhatsAppAppointmentWorkflow:
    def setup_method(self):
        self.hospital = Hospital.objects.create(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
            phone="+91 94095 10501",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username="test_admin_whatsapp",
            password="AdminPassword123#",
            is_staff=True,
        )
        ClinicAdmin.objects.create(user=self.admin_user, hospital=self.hospital)

    def test_phone_sanitization_helper(self):
        """Verify phone sanitization strictly conforms to international E.164 digits without +, spaces, dashes."""
        assert sanitize_phone_to_international("+91 94095 10501") == "919409510501"
        assert sanitize_phone_to_international("9409510501") == "919409510501"  # 10-digit Indian prefix added
        assert sanitize_phone_to_international("+1 (555) 234-5678") == "15552345678"
        assert sanitize_phone_to_international("") == ""
        assert sanitize_phone_to_international("abc") == ""
        assert sanitize_phone_to_international("123") == ""  # Too short

    def test_whatsapp_message_content_and_url_encoding(self, settings):
        """Verify WhatsApp message contains only required fields and is strictly URL encoded."""
        settings.DOCTOR_WHATSAPP_NUMBER = "919409510501"
        tomorrow = timezone.now().date() + timedelta(days=2)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Priya Sharma",
            email="priya.sharma@example.com",
            phone="+91 98765 43210",
            preferred_date=tomorrow,
            preferred_time="10:30 AM",
            service_or_reason="Neck pain & cervical rehab",
            preferred_contact_method="whatsapp",
            status="pending",
        )

        message = build_whatsapp_appointment_message(req)
        assert "New Appointment Request" in message
        assert req.reference_id in message
        assert "Priya Sharma" in message
        assert "Neck pain & cervical rehab" in message
        assert "Pending Confirmation" in message
        assert "Please review this request and contact the patient to confirm availability." in message

        # Test URL generation
        url, is_configured = build_whatsapp_click_to_chat_url(req)
        assert is_configured is True
        assert url.startswith("https://wa.me/919409510501?text=")
        # Verify valid URL encoding: no raw spaces or unescaped line breaks
        assert " " not in url
        assert "\n" not in url
        # Decode and verify payload matches
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        assert "text" in params
        assert "Priya Sharma" in params["text"][0]
        assert req.reference_id in params["text"][0]

    def test_missing_whatsapp_configuration_handled_safely(self, settings):
        """Verify that when DOCTOR_WHATSAPP_NUMBER is empty or unset, WhatsApp URL generation fails safely."""
        settings.DOCTOR_WHATSAPP_NUMBER = ""
        settings.CLINIC_WHATSAPP_NUMBER = ""
        settings.CLINIC_WHATSAPP = ""
        tomorrow = timezone.now().date() + timedelta(days=2)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Karan Patel",
            email="karan@example.com",
            phone="+91 98765 00000",
            preferred_date=tomorrow,
            preferred_time="11:00 AM",
            status="pending",
        )
        url, is_configured = build_whatsapp_click_to_chat_url(req)
        assert is_configured is False
        assert url == ""
        assert req.doctor_whatsapp_click_url == ""

    def test_public_booking_flow_saves_request_and_renders_whatsapp_button(self, client, settings):
        """Verify public booking form saves appointment in PostgreSQL, returns pending status, and renders WhatsApp button."""
        settings.DOCTOR_WHATSAPP_NUMBER = "919409510501"
        future_date = timezone.now().date() + timedelta(days=3)
        post_data = {
            "form_type": "appointment",
            "patient_name": "Deepak Mehta",
            "email": "deepak.mehta@example.com",
            "phone": "+91 98765 12345",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "10:30 AM",
            "service_or_reason": "Sports rehabilitation for ankle sprain",
            "preferred_contact_method": "whatsapp",
            "consent": "on",
            "website": "",  # honeypot left blank
        }

        response = client.post(reverse("public_book_appointment"), post_data, follow=True)
        assert response.status_code == 200

        # Verify record in DB
        req = PublicAppointmentRequest.objects.filter(email="deepak.mehta@example.com").first()
        assert req is not None
        assert req.status == "pending"
        assert req.patient_name == "Deepak Mehta"

        # Verify confirmation card output
        content = response.content.decode("utf-8")
        assert "Request received, pending clinic confirmation" in content
        assert "btnSendWhatsApp" in content
        assert "Send Request via WhatsApp" in content
        assert "https://wa.me/919409510501" in content
        assert "Deepak%20Mehta" in content or "Deepak+Mehta" in content

    def test_whatsapp_click_tracking_does_not_mutate_status_or_duplicate_appointments(self, client):
        """Verify clicking WhatsApp action logs click audit event but NEVER marks request as confirmed or creates duplicate."""
        tomorrow = timezone.now().date() + timedelta(days=2)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Sanjay Verma",
            email="sanjay@example.com",
            phone="+91 98765 99999",
            preferred_date=tomorrow,
            preferred_time="10:30 AM",
            status="pending",
        )

        initial_count = PublicAppointmentRequest.objects.count()
        initial_appointment_count = Appointment.objects.count()

        # Simulate visitor clicking 'Send Request via WhatsApp'
        response = client.post(
            reverse("track_whatsapp_click"),
            data={"reference_id": req.reference_id},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

        req.refresh_from_db()
        # Status MUST remain pending
        assert req.status == "pending"
        # Click event recorded in admin notes
        assert "[System] Visitor opened WhatsApp click-to-chat" in req.admin_notes
        # Zero duplicate records created
        assert PublicAppointmentRequest.objects.count() == initial_count
        assert Appointment.objects.count() == initial_appointment_count

    def test_doctor_admin_dashboard_shows_patient_whatsapp_action(self, client):
        """Verify doctor/admin dashboard displays WhatsApp contact button for public requests and scheduled appointments."""
        tomorrow = timezone.now().date() + timedelta(days=2)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Neha Joshi",
            email="neha@example.com",
            phone="+91 94095 10501",
            preferred_date=tomorrow,
            preferred_time="10:30 AM",
            status="pending",
        )

        appt = Appointment.objects.create(
            hospital=self.hospital,
            name="Amit Shah",
            email="amit@example.com",
            phone="9409510501",
            date=tomorrow,
            time="10:30 AM",
            service="orthopedic",
            status="pending",
        )

        client.force_login(self.admin_user)
        response = client.get(reverse("admin_appointments"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Verify WhatsApp contact links exist for both
        assert "Contact Patient via WhatsApp" in content
        assert f"https://wa.me/{req.phone_digits}" in content
        assert f"https://wa.me/{appt.phone_digits}" in content
