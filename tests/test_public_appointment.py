"""
Automated tests for the Public Book Appointment page, form validation,
doctor email notifications, duplicate deterrence, safe persistence, and public navbar integration.
"""
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import PublicAppointmentRequest, Appointment, Hospital
from tests.test_helpers import BaseHospitalTestCase


class PublicAppointmentBookingTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
        )
        self.public_url = reverse("public_book_appointment")

    def _get_future_date(self, days=2):
        target = timezone.now().date() + timedelta(days=days)
        # Avoid Sunday if clinic is by appointment
        if target.weekday() == 6:
            target += timedelta(days=1)
        return target

    def test_unauthenticated_visitor_can_access_page(self):
        """Anyone can open /book-appointment/ without logging in or being redirected."""
        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book Your Physiotherapy Appointment")
        self.assertContains(
            response,
            "Take the first step towards better movement and recovery. Request an appointment with our physiotherapy team."
        )
        # Verify page is not a login redirect or dashboard
        self.assertNotContains(response, "Login to your account")
        self.assertNotContains(response, "Dashboard Overview")

    def test_unauthenticated_visitor_can_submit_valid_request(self):
        """Unauthenticated visitor submits a valid appointment request and sees confirmation."""
        future_date = self._get_future_date(3)
        payload = {
            "patient_name": "Meera Sharma",
            "email": "meera.sharma@example.com",
            "phone": "9876543210",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "10:30 AM",
            "service_or_reason": "Lower back pain and sciatica rehab",
            "preferred_contact_method": "phone",
            "consent": "on",
            "website": "",  # honeypot left empty
        }

        response = self.client.post(self.public_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # Confirm request is safely saved in database
        req = PublicAppointmentRequest.objects.filter(email="meera.sharma@example.com").first()
        self.assertIsNotNone(req)
        self.assertEqual(req.patient_name, "Meera Sharma")
        self.assertEqual(req.phone, "9876543210")
        self.assertEqual(req.preferred_date, future_date)
        self.assertEqual(req.preferred_time, "10:30 AM")
        self.assertEqual(req.status, "pending")
        self.assertTrue(req.reference_id.startswith("PAR-"))

        # Verify confirmation message displayed on response
        self.assertContains(response, "Thank you for your appointment request")
        self.assertContains(response, "awaiting confirmation")
        self.assertContains(response, req.reference_id)

    def test_invalid_email_format_is_rejected(self):
        """Invalid email formats are rejected by server-side validation."""
        future_date = self._get_future_date(2)
        payload = {
            "patient_name": "Test User",
            "email": "not-an-email-address",
            "phone": "9876543210",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "11:00 AM",
            "consent": "on",
        }
        response = self.client.post(self.public_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PublicAppointmentRequest.objects.filter(phone="9876543210").exists())
        self.assertContains(response, "Please provide a valid email address format.")

    def test_missing_required_fields_rejected(self):
        """Submissions missing required fields (name, phone, date, time) are rejected."""
        payload = {
            "patient_name": "",
            "email": "test@example.com",
            "phone": "",
            "preferred_date": "",
            "preferred_time": "",
            "consent": "on",
        }
        response = self.client.post(self.public_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PublicAppointmentRequest.objects.count(), 0)

    def test_missing_consent_is_rejected(self):
        """Submissions without consent checkbox are rejected."""
        future_date = self._get_future_date(2)
        payload = {
            "patient_name": "Karan Varma",
            "email": "karan@example.com",
            "phone": "9876543210",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "11:30 AM",
            # consent omitted
        }
        response = self.client.post(self.public_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PublicAppointmentRequest.objects.filter(email="karan@example.com").exists())

    def test_past_date_is_rejected(self):
        """Appointment dates in the past are rejected."""
        past_date = timezone.now().date() - timedelta(days=2)
        payload = {
            "patient_name": "Pooja Mehta",
            "email": "pooja@example.com",
            "phone": "9876543210",
            "preferred_date": past_date.strftime("%Y-%m-%d"),
            "preferred_time": "10:00 AM",
            "consent": "on",
        }
        response = self.client.post(self.public_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PublicAppointmentRequest.objects.filter(email="pooja@example.com").exists())
        self.assertContains(response, "Cannot request an appointment for a past date")

    def test_doctor_notification_email_recipient_and_content(self):
        """A valid appointment request sends an email to physio.rehab.guj@gmail.com."""
        future_date = self._get_future_date(4)
        payload = {
            "patient_name": "Amit Trivedi",
            "email": "amit.trivedi@example.com",
            "phone": "9409510501",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "05:00 PM",
            "service_or_reason": "Post-op knee ligament rehabilitation",
            "preferred_contact_method": "whatsapp",
            "consent": "on",
        }

        mail.outbox.clear()
        response = self.client.post(self.public_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # Check outbox
        self.assertTrue(len(mail.outbox) >= 1)
        doctor_email = None
        for m in mail.outbox:
            if "physio.rehab.guj@gmail.com" in m.to:
                doctor_email = m
                break

        self.assertIsNotNone(doctor_email, "Email was not dispatched to physio.rehab.guj@gmail.com")
        self.assertIn("New Public Appointment Request", doctor_email.subject)
        self.assertIn("Amit Trivedi", doctor_email.body)
        self.assertIn("amit.trivedi@example.com", doctor_email.body)
        self.assertIn("9409510501", doctor_email.body)
        self.assertIn("05:00 PM", doctor_email.body)
        self.assertIn("Post-op knee ligament rehabilitation", doctor_email.body)

    def test_email_delivery_failure_preserves_request(self):
        """If email delivery fails, the request is preserved and user receives clear message."""
        future_date = self._get_future_date(2)
        payload = {
            "patient_name": "Rohan Joshi",
            "email": "rohan.joshi@example.com",
            "phone": "9825098250",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "12:00 PM",
            "consent": "on",
        }

        with patch("core.email_utils.send_clinic_email", return_value=False):
            response = self.client.post(self.public_url, payload, follow=True)
            self.assertEqual(response.status_code, 200)

        req = PublicAppointmentRequest.objects.filter(email="rohan.joshi@example.com").first()
        self.assertIsNotNone(req, "Request must be saved even if email delivery fails")
        self.assertEqual(req.email_notification_status, "failed")
        self.assertContains(response, "Thank you for your appointment request")
        self.assertContains(response, "awaiting confirmation")

    def test_honeypot_spam_is_rejected(self):
        """Automated bot filling the honeypot field is rejected."""
        future_date = self._get_future_date(2)
        payload = {
            "patient_name": "Bot Spammer",
            "email": "bot@spam.com",
            "phone": "9999999999",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "10:00 AM",
            "consent": "on",
            "website": "http://spam-site.com",  # Honeypot filled
        }
        response = self.client.post(self.public_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PublicAppointmentRequest.objects.filter(email="bot@spam.com").exists())

    def test_duplicate_submission_handled(self):
        """Submitting identical request within short timeframe prevents duplicate DB rows."""
        future_date = self._get_future_date(3)
        payload = {
            "patient_name": "Geeta Dave",
            "email": "geeta.dave@example.com",
            "phone": "9123456789",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "04:30 PM",
            "consent": "on",
        }

        # First submission
        self.client.post(self.public_url, payload, follow=True)
        self.assertEqual(PublicAppointmentRequest.objects.filter(email="geeta.dave@example.com").count(), 1)

        # Immediate second submission
        self.client.post(self.public_url, payload, follow=True)
        self.assertEqual(PublicAppointmentRequest.objects.filter(email="geeta.dave@example.com").count(), 1)

    def test_public_navbar_links_appear_on_public_pages(self):
        """Public navbar displays Book Appointment link pointing to /book-appointment/."""
        pages = ["/", "/about/", "/services/", "/contact/", "/book-appointment/"]
        for p in pages:
            res = self.client.get(p)
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'href="/book-appointment/"')
            self.assertContains(res, "Book Appointment")

    def test_private_dashboards_remain_protected(self):
        """Unauthenticated visitors cannot access staff, admin, or client dashboard pages."""
        protected_urls = [
            "/admin-dashboard/",
            "/admin-appointments/",
            "/client-dashboard/",
            "/staff-dashboard/",
            "/book/",
        ]
        for url in protected_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/login/", res.url)

    def test_admin_can_view_and_update_public_request_status(self):
        """Clinic Admin can see public request and update status to confirmed."""
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Sanjay Raval",
            email="sanjay@example.com",
            phone="9876501234",
            preferred_date=self._get_future_date(2),
            preferred_time="10:00 AM",
            status="pending",
        )

        admin_user = self.create_clinic_admin(hospital=self.hospital, username="dr_patalia")
        self.client.force_login(admin_user)

        # Access admin appointments
        res = self.client.get(reverse("admin_appointments"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, req.reference_id)
        self.assertContains(res, "Sanjay Raval")

        # Update status
        update_url = reverse("update_public_appointment_request", kwargs={"request_id": req.id, "status": "confirmed"})
        res_update = self.client.get(update_url, follow=True)
        self.assertEqual(res_update.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, "confirmed")
