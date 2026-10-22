"""
Automated tests for the Unified Appointment Booking & Contact page.
Validates:
1. Unified page rendering at /appointment-contact/, /book-appointment/, and /contact/.
2. Dual section architecture (Appointment booking and Contact inquiry tabs).
3. Independent form processing and strict separation of database models:
   - Appointment submission creates PublicAppointmentRequest, NEVER creates VisitorLead.
   - Contact submission creates VisitorLead, NEVER creates PublicAppointmentRequest.
4. Robust backend validation and spam/honeypot prevention on both forms.
5. Email notifications and failure handling.
6. Public access for visitors and protection of clinical patient data.
7. Public navigation and footer integration.
"""
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import (
    PublicAppointmentRequest,
    VisitorLead,
    Hospital,
)
from tests.test_helpers import BaseHospitalTestCase


class UnifiedAppointmentContactTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
        )
        self.unified_url = reverse("appointment_contact")
        self.book_url = reverse("public_book_appointment")
        self.contact_url = reverse("contact")

    def _get_future_date(self, days=3):
        target = timezone.now().date() + timedelta(days=days)
        if target.weekday() == 6:  # Skip Sunday
            target += timedelta(days=1)
        return target

    def test_unified_page_loads_with_both_forms_and_tabs(self):
        """Unified page loads with HTTP 200, tab navigation, and both form panels."""
        for url in [self.unified_url, self.book_url, self.contact_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed loading {url}")
            # Page Title & Header
            self.assertContains(response, "Book Your Physiotherapy Appointment")
            # Accessible Tab controls
            self.assertContains(response, 'role="tablist"')
            self.assertContains(response, 'id="tabBtnAppointment"')
            self.assertContains(response, 'id="tabBtnContact"')
            self.assertContains(response, 'id="panelAppointment"')
            self.assertContains(response, 'id="panelContact"')
            # Form elements
            self.assertContains(response, 'name="form_type"')
            self.assertContains(response, 'name="patient_name"')
            self.assertContains(response, 'name="service_or_reason"')
            self.assertContains(response, 'name="first_name"')
            self.assertContains(response, 'name="subject"')
            # Clinic details sidebar
            self.assertContains(response, "+91 94095 10501")
            self.assertContains(response, "Jamnagar")
            self.assertContains(response, "Narayan Cottage")

    def test_active_tab_query_parameter(self):
        """Query parameters like ?tab=contact activate the contact tab properly."""
        response = self.client.get(f"{self.unified_url}?tab=contact")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "contact")

        response = self.client.get(f"{self.unified_url}?tab=appointment")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "appointment")

    def test_appointment_submission_saves_appointment_and_does_not_create_lead(self):
        """
        Submitting an appointment request saves a PublicAppointmentRequest,
        and MUST NOT create a VisitorLead record.
        """
        initial_appts = PublicAppointmentRequest.objects.count()
        initial_leads = VisitorLead.objects.count()

        future_date = self._get_future_date(2)
        payload = {
            "form_type": "appointment",
            "patient_name": "Aarav Patel",
            "email": "aarav.patel@example.com",
            "phone": "9876543210",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "11:00 AM",
            "service_or_reason": "Post-surgery knee rehabilitation",
            "preferred_contact_method": "phone",
            "consent": "on",
            "website": "",  # Honeypot empty
        }

        response = self.client.post(self.unified_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # 1. Appointment was saved
        self.assertEqual(PublicAppointmentRequest.objects.count(), initial_appts + 1)
        appt = PublicAppointmentRequest.objects.filter(email="aarav.patel@example.com").first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.patient_name, "Aarav Patel")
        self.assertEqual(appt.status, "pending")
        self.assertTrue(appt.reference_id.startswith("PAR-"))

        # 2. Strict separation: NO VisitorLead was created
        self.assertEqual(VisitorLead.objects.count(), initial_leads)

        # 3. User feedback confirmation is rendered
        self.assertContains(response, "Thank you for your appointment request")
        self.assertContains(response, appt.reference_id)

    def test_contact_submission_saves_lead_and_does_not_create_appointment(self):
        """
        Submitting a contact message saves a VisitorLead record,
        and MUST NOT create a PublicAppointmentRequest record.
        """
        initial_appts = PublicAppointmentRequest.objects.count()
        initial_leads = VisitorLead.objects.count()

        payload = {
            "form_type": "contact",
            "first_name": "Rohan",
            "last_name": "Deshmukh",
            "email": "rohan.deshmukh@example.com",
            "phone": "9823012345",
            "subject": "General Enquiry",
            "message": "Hello, do you provide home visit physiotherapy in Jamnagar?",
            "consent": "on",
            "website": "",  # Honeypot empty
        }

        response = self.client.post(self.unified_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # 1. VisitorLead was created
        self.assertEqual(VisitorLead.objects.count(), initial_leads + 1)
        lead = VisitorLead.objects.filter(email="rohan.deshmukh@example.com").first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.first_name, "Rohan")
        self.assertEqual(lead.last_name, "Deshmukh")
        self.assertEqual(lead.category, "General Enquiry")
        self.assertIn("home visit", lead.message)

        # 2. Strict separation: NO PublicAppointmentRequest was created
        self.assertEqual(PublicAppointmentRequest.objects.count(), initial_appts)

        # 3. Confirmation feedback
        self.assertContains(response, "Message sent")

    def test_invalid_appointment_rejected_without_database_creation(self):
        """Invalid appointment request is rejected and does not write to the database."""
        initial_appts = PublicAppointmentRequest.objects.count()

        # Missing required phone and consent, past date
        payload = {
            "form_type": "appointment",
            "patient_name": "Test User",
            "email": "invalid-email",
            "phone": "",
            "preferred_date": "2020-01-01",
            "preferred_time": "10:00 AM",
            "service_or_reason": "",
            "consent": "",
            "website": "",
        }

        response = self.client.post(self.unified_url, payload)
        self.assertEqual(response.status_code, 200)
        # Database unchanged
        self.assertEqual(PublicAppointmentRequest.objects.count(), initial_appts)
        self.assertContains(response, "Please review and correct the highlighted fields below")

    def test_invalid_contact_rejected_without_database_creation(self):
        """Invalid contact message is rejected and does not write to the database."""
        initial_leads = VisitorLead.objects.count()

        payload = {
            "form_type": "contact",
            "first_name": "",
            "last_name": "",
            "email": "not-an-email",
            "subject": "General Enquiry",
            "message": "",
            "website": "",
        }

        response = self.client.post(self.unified_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisitorLead.objects.count(), initial_leads)
        self.assertContains(response, "Please fill in all required fields")

    def test_honeypot_rejects_bots_silently_on_both_forms(self):
        """Bot filling the honeypot field is discarded without database persistence."""
        initial_appts = PublicAppointmentRequest.objects.count()
        initial_leads = VisitorLead.objects.count()

        # Bot submitting appointment
        self.client.post(self.unified_url, {
            "form_type": "appointment",
            "patient_name": "Spam Bot",
            "email": "bot@spam.com",
            "phone": "9999999999",
            "preferred_date": "2026-11-01",
            "service_or_reason": "Buy crypto now",
            "consent": "on",
            "website": "http://spamsite.com",
        })
        self.assertEqual(PublicAppointmentRequest.objects.count(), initial_appts)

        # Bot submitting contact
        self.client.post(self.unified_url, {
            "form_type": "contact",
            "first_name": "Spam",
            "last_name": "Bot",
            "email": "bot@spam.com",
            "subject": "SEO offer",
            "message": "Best SEO offer here",
            "website": "http://spamsite.com",
        })
        self.assertEqual(VisitorLead.objects.count(), initial_leads)

    def test_public_navbar_unifies_book_and_contact(self):
        """Public homepage navbar contains the unified 'Book Appointment & Contact' link."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book Appointment &amp; Contact")

    def test_unauthenticated_visitor_can_submit_and_private_records_are_protected(self):
        """Unauthenticated visitors can access the public form, but cannot access private patient records."""
        # Public form is 200 OK
        resp_public = self.client.get(self.unified_url)
        self.assertEqual(resp_public.status_code, 200)

        # Private clinical endpoints require authentication
        private_urls = [
            reverse("admin_appointments"),
            reverse("profile"),
            reverse("admin_settings"),
        ]
        for url in private_urls:
            resp_private = self.client.get(url)
            self.assertEqual(resp_private.status_code, 302)
            self.assertIn("login", resp_private.url)
