import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
from django.urls import reverse
from core.models import PublicAppointmentRequest, Hospital


@pytest.mark.django_db
class TestPhase2PublicAppointmentsAndNotifications:
    def setup_method(self):
        self.hospital = Hospital.objects.create(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
            phone="+91 94095 10501",
            is_active=True,
        )

    def test_public_appointment_submission_success_message(self, client):
        """Verify public booking submission succeeds and returns 'pending clinic confirmation' message."""
        tomorrow = timezone.now().date() + timedelta(days=1)
        response = client.post(
            reverse("public_book_appointment"),
            {
                "form_type": "appointment",
                "patient_name": "Rohan Sharma",
                "email": "rohan.sharma@example.com",
                "phone": "+91 98765 43210",
                "preferred_date": tomorrow.strftime("%Y-%m-%d"),
                "preferred_time": "10:30 AM",
                "service_or_reason": "Post-surgery knee rehabilitation",
                "preferred_contact_method": "phone",
                "consent": "on",
                "website": "",  # honeypot left blank
            },
            follow=True,
        )
        assert response.status_code == 200
        req = PublicAppointmentRequest.objects.filter(email="rohan.sharma@example.com").first()
        assert req is not None
        assert req.status == "pending"
        assert "Request received, pending clinic confirmation" in response.content.decode("utf-8")
        assert "confirmed" not in response.content.decode("utf-8").lower().replace("awaiting confirmation", "").replace("pending clinic confirmation", "").replace("pending confirmation", "")

    def test_retry_appointment_notifications_management_command(self, capsys):
        """Verify retry_appointment_notifications management command retries failed notifications."""
        tomorrow = timezone.now().date() + timedelta(days=2)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Anjali Mehta",
            email="anjali.mehta@example.com",
            phone="+91 98765 11223",
            preferred_date=tomorrow,
            preferred_time="11:00 AM",
            service_or_reason="Frozen shoulder physiotherapy",
            status="pending",
            email_notification_status="failed",
            notification_error="SMTP connection timed out",
        )

        call_command("retry_appointment_notifications", ref=req.reference_id)
        req.refresh_from_db()
        assert req.email_notification_status in ("sent", "failed")
