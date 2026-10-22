"""
End-to-end integration tests connecting Reviews and Appointment Bookings
across Frontend, Backend, PostgreSQL models, and Admin moderation interfaces.
"""
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Review, Appointment, PublicAppointmentRequest, Hospital
from tests.test_helpers import BaseHospitalTestCase

User = get_user_model()


class ReviewsEndToEndIntegrationTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
        )
        self.admin_user = self.create_clinic_admin(hospital=self.hospital, username="clinic_admin_user")
        self.patient_user = self.create_patient(hospital=self.hospital, username="patient_test_user")

        # Second clinic for multi-tenancy verification
        self.hospital_b = self.create_hospital(
            name="Apex Orthocare",
            email="apex@example.com",
        )
        self.admin_user_b = self.create_clinic_admin(hospital=self.hospital_b, username="admin_b_user")

        self.public_review_url = reverse("public_review")
        self.admin_reviews_url = reverse("admin_reviews")

    def test_public_visitor_can_load_review_page(self):
        """Public visitor can load /review/ without authentication."""
        res = self.client.get(self.public_review_url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Patient Reviews")
        self.assertContains(res, "Dr. Dhvani Patalia")

    def test_valid_review_submission_creates_pending_record(self):
        """Valid submission saves permanently to PostgreSQL with is_approved=False."""
        payload = {
            "reviewer_name": "Rajesh Varma",
            "rating": 5,
            "message": "Outstanding rehabilitation after knee arthroscopy. I regained mobility in 3 weeks!",
            "consent_to_publish": "on",
            "website": "",  # honeypot
        }
        res = self.client.post(self.public_review_url, payload, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Thank you for sharing your experience")

        # Verify DB record
        review = Review.objects.filter(reviewer_name="Rajesh Varma").first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)
        self.assertFalse(review.is_approved)  # Must be pending moderation
        self.assertTrue(review.consent_to_publish)

    def test_invalid_ratings_and_missing_feedback_are_rejected(self):
        """Ratings outside 1-5 or empty feedback are rejected by server-side validation."""
        payload_bad_rating = {
            "reviewer_name": "Test User",
            "rating": 6,  # Invalid rating > 5
            "message": "Great service!",
            "consent_to_publish": "on",
        }
        res = self.client.post(self.public_review_url, payload_bad_rating)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Review.objects.filter(reviewer_name="Test User").exists())

        payload_empty_msg = {
            "reviewer_name": "Test User 2",
            "rating": 5,
            "message": "",  # Empty message
            "consent_to_publish": "on",
        }
        res2 = self.client.post(self.public_review_url, payload_empty_msg)
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(Review.objects.filter(reviewer_name="Test User 2").exists())

    def test_pending_review_does_not_appear_publicly_until_approved(self):
        """Pending review appears on admin page but NOT on public review or home pages."""
        review = Review.objects.create(
            hospital=self.hospital,
            reviewer_name="Ananya Patel",
            rating=5,
            message="UniqueSecretReviewTextAnanya",
            is_approved=False,
            consent_to_publish=True,
        )

        # 1. Check public review page
        res_pub = self.client.get(self.public_review_url)
        self.assertNotContains(res_pub, "UniqueSecretReviewTextAnanya")

        # 2. Check public home page
        res_home = self.client.get(reverse("home"))
        self.assertNotContains(res_home, "UniqueSecretReviewTextAnanya")

        # 3. Check admin reviews page (admin logged in)
        self.client.force_login(self.admin_user)
        res_admin = self.client.get(self.admin_reviews_url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, "UniqueSecretReviewTextAnanya")
        self.assertContains(res_admin, "Pending")

        # 4. Admin approves review
        toggle_url = reverse("toggle_review_approval", kwargs={"review_id": review.id})
        res_toggle = self.client.post(toggle_url, follow=True)
        self.assertEqual(res_toggle.status_code, 200)

        review.refresh_from_db()
        self.assertTrue(review.is_approved)

        # 5. Public review page and home page now display the approved review
        self.client.logout()
        res_pub_approved = self.client.get(self.public_review_url)
        self.assertContains(res_pub_approved, "UniqueSecretReviewTextAnanya")

        res_home_approved = self.client.get(reverse("home"))
        self.assertContains(res_home_approved, "UniqueSecretReviewTextAnanya")

    def test_unauthorized_user_cannot_moderate_reviews(self):
        """Unauthenticated visitor or regular patient cannot approve or delete reviews."""
        review = Review.objects.create(
            hospital=self.hospital,
            reviewer_name="Sneha",
            rating=5,
            message="Needs moderation test",
            is_approved=False,
        )
        toggle_url = reverse("toggle_review_approval", kwargs={"review_id": review.id})

        # Unauthenticated attempt
        res = self.client.post(toggle_url)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)
        review.refresh_from_db()
        self.assertFalse(review.is_approved)

        # Authenticated as regular patient attempt
        self.client.force_login(self.patient_user)
        res_patient = self.client.post(toggle_url)
        self.assertEqual(res_patient.status_code, 302)
        self.assertIn("/client-dashboard/", res_patient.url)
        review.refresh_from_db()
        self.assertFalse(review.is_approved)

    def test_cross_hospital_review_isolation(self):
        """Clinic Admin cannot approve or delete reviews belonging to another hospital."""
        review_b = Review.objects.create(
            hospital=self.hospital_b,
            reviewer_name="Patient of Hospital B",
            rating=5,
            message="Hospital B content",
            is_approved=False,
        )
        self.client.force_login(self.admin_user)  # Admin of hospital A
        toggle_url = reverse("toggle_review_approval", kwargs={"review_id": review_b.id})
        res = self.client.post(toggle_url, follow=True)
        self.assertContains(res, "Unauthorized: Review belongs to another clinic")
        review_b.refresh_from_db()
        self.assertFalse(review_b.is_approved)

    def test_admin_review_filtering_and_metrics(self):
        """Admin reviews page supports filtering by status and displays accurate metrics."""
        Review.objects.create(hospital=self.hospital, reviewer_name="Rev1", rating=5, message="M1", is_approved=True)
        Review.objects.create(hospital=self.hospital, reviewer_name="Rev2", rating=4, message="M2", is_approved=False)

        self.client.force_login(self.admin_user)
        res = self.client.get(self.admin_reviews_url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["total"], 2)
        self.assertEqual(res.context["approved"], 1)
        self.assertEqual(res.context["pending"], 1)

        # Filter pending only
        res_pending = self.client.get(f"{self.admin_reviews_url}?status=pending")
        self.assertEqual(len(res_pending.context["reviews"]), 1)
        self.assertEqual(res_pending.context["reviews"][0].reviewer_name, "Rev2")


class AppointmentsEndToEndIntegrationTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
        )
        self.admin_user = self.create_clinic_admin(hospital=self.hospital, username="doctor_patalia_admin")
        self.patient_user = self.create_patient(hospital=self.hospital, username="patient_harsh")

        self.public_booking_url = reverse("public_book_appointment")
        self.admin_appts_url = reverse("admin_appointments")

    def _get_future_date(self, days=3):
        target = timezone.now().date() + timedelta(days=days)
        if target.weekday() == 6:  # Skip Sunday
            target += timedelta(days=1)
        return target

    def test_public_visitor_can_submit_booking_and_appear_in_admin(self):
        """
        End-to-end booking flow:
        Visitor submits public booking -> Saved to PostgreSQL -> Visible on Admin appointments page.
        """
        target_date = self._get_future_date(3)
        payload = {
            "patient_name": "Pooja Trivedi",
            "email": "pooja.trivedi@example.com",
            "phone": "9825123456",
            "preferred_date": target_date.strftime("%Y-%m-%d"),
            "preferred_time": "11:00 AM",
            "service_or_reason": "Post fracture stiffness and shoulder mobilization",
            "preferred_contact_method": "phone",
            "consent": "on",
            "website": "",
        }

        # 1. Visitor submits form
        res = self.client.post(self.public_booking_url, payload, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Thank you for your appointment request")

        # 2. Verify record in PostgreSQL
        req = PublicAppointmentRequest.objects.filter(email="pooja.trivedi@example.com").first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, "pending")
        self.assertTrue(req.reference_id.startswith("PAR-"))

        # 3. Doctor / Clinic Admin views /admin-appointments/
        self.client.force_login(self.admin_user)
        res_admin = self.client.get(self.admin_appts_url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, req.reference_id)
        self.assertContains(res_admin, "Pooja Trivedi")
        self.assertContains(res_admin, "11:00 AM")

        # 4. Metrics cards verify presence of pending request
        self.assertGreaterEqual(res_admin.context["public_pending_count"], 1)

    def test_admin_confirming_request_syncs_to_master_appointment_schedule(self):
        """
        When Doctor/Admin confirms a public booking request, an official Appointment record
        is created and appears in the master clinical schedule and reports.
        """
        target_date = self._get_future_date(4)
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Amit Dave",
            email="amit.dave@example.com",
            phone="9876543210",
            preferred_date=target_date,
            preferred_time="10:30 AM",
            service_or_reason="Lower back pain and postural rehab",
            status="pending",
        )

        self.client.force_login(self.admin_user)
        confirm_url = reverse("update_public_appointment_request", kwargs={"request_id": req.id, "status": "confirmed"})
        res = self.client.get(confirm_url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"Public request {req.reference_id} marked as Confirmed")

        # Verify PublicAppointmentRequest updated
        req.refresh_from_db()
        self.assertEqual(req.status, "confirmed")

        # Verify synchronized Appointment record created in PostgreSQL
        appt = Appointment.objects.filter(
            hospital=self.hospital,
            email="amit.dave@example.com",
            date=target_date,
        ).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.name, "Amit Dave")
        self.assertEqual(appt.status, "confirmed")
        self.assertIn(req.reference_id, appt.notes)

    def test_unauthorized_user_cannot_modify_appointment_requests(self):
        """Unauthenticated visitors and regular patients cannot change booking status."""
        req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Security Test Patient",
            email="sec@example.com",
            phone="9876543210",
            preferred_date=self._get_future_date(2),
            preferred_time="10:00 AM",
            status="pending",
        )
        url = reverse("update_public_appointment_request", kwargs={"request_id": req.id, "status": "confirmed"})

        # Unauthenticated
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

        # Regular Patient
        self.client.force_login(self.patient_user)
        res2 = self.client.get(url)
        self.assertEqual(res2.status_code, 302)
        self.assertIn("/client-dashboard/", res2.url)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

    def test_cross_hospital_appointment_isolation(self):
        """Clinic Admin cannot view or modify appointments of another clinic."""
        hospital_b = self.create_hospital(
            name="Apex Orthocare",
            email="apex@example.com",
        )
        req_b = PublicAppointmentRequest.objects.create(
            hospital=hospital_b,
            patient_name="Patient B Only",
            email="pb@example.com",
            phone="9876500000",
            preferred_date=self._get_future_date(2),
            preferred_time="10:00 AM",
            status="pending",
        )

        self.client.force_login(self.admin_user)  # Admin of hospital A
        res_admin = self.client.get(self.admin_appts_url)
        self.assertNotContains(res_admin, req_b.reference_id)
        self.assertNotContains(res_admin, "Patient B Only")

        # Attempt to modify Hospital B request
        url = reverse("update_public_appointment_request", kwargs={"request_id": req_b.id, "status": "confirmed"})
        res_hack = self.client.get(url, follow=True)
        self.assertContains(res_hack, "Unauthorized: You cannot modify requests for another clinic")
        req_b.refresh_from_db()
        self.assertEqual(req_b.status, "pending")
