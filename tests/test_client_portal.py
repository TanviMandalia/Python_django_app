"""
tests/test_client_portal.py
Hospital Management System - Deployment-Level Test Suite
Role 4: CLIENT / PATIENT Portal, Booking, Invoicing, Privacy, and Profile
"""

from decimal import Decimal
from datetime import date, time, timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    Appointment,
    PaymentRecord,
    SessionNote,
    Review,
    Notification,
    Message,
    Profile,
)


class ClientPortalTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Care Physio Center", email="portal@carephysio.com"
        )
        self.clinic_admin = self.create_clinic_admin(
            self.hospital, username="clinic_director", email="director@carephysio.com"
        )
        self.staff_doctor = self.create_staff(
            self.hospital, username="dr_watson", email="watson@carephysio.com"
        )
        self.patient_a = self.create_patient(
            self.hospital,
            username="patient_alice",
            email="alice@example.com",
            first_name="Alice",
            last_name="Green",
        )
        self.patient_b = self.create_patient(
            self.hospital,
            username="patient_bob",
            email="bob@example.com",
            first_name="Bob",
            last_name="Brown",
        )

        self.client.force_login(self.patient_a)

    # ── 1. Dashboard & Access Control ─────────────────────────────

    def test_client_dashboard_loads(self):
        """TC-CP-001: Authenticated patient accesses their dashboard."""
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_client_dashboard_denied(self):
        """TC-CP-002: Unauthenticated user is redirected to login."""
        self.client.logout()
        response = self.client.get(reverse("client_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_client_denied_admin_dashboard(self):
        """TC-CP-003: Patient is strictly denied access to clinic admin dashboard."""
        response = self.client.get(reverse("admin_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

    def test_client_denied_super_admin_dashboard(self):
        """TC-CP-004: Patient is strictly denied platform super admin dashboard."""
        response = self.client.get(reverse("super_admin_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)

    # ── 2. Appointment Booking & Scoping ──────────────────────────

    def test_client_book_appointment_success(self):
        """TC-CP-005: Patient books appointment with clinic."""
        target_date = self.get_next_weekday(days_ahead=1).strftime("%Y-%m-%d")
        payload = {
            "hospital_id": self.hospital.id,
            "service": "Physiotherapy Consultation",
            "date": target_date,
            "time": "11:00",
            "notes": "Severe lower back discomfort",
        }
        response = self.client.post(reverse("book_appointment"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("my_appointments"))

        appt = Appointment.objects.filter(
            patient=self.patient_a, date=target_date, time="11:00"
        ).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.status, "pending")
        self.assertEqual(appt.hospital, self.hospital)

    def test_client_view_my_appointments(self):
        """TC-CP-006: Patient views only their personal appointment schedule."""
        # Patient A appointment
        appt_a = self.create_appointment(
            hospital=self.hospital,
            patient=self.patient_a,
            date=(timezone.now() + timedelta(days=1)).date(),
            time="10:00",
            service="Knee Rehab Session",
        )
        # Patient B appointment
        appt_b = self.create_appointment(
            hospital=self.hospital,
            patient=self.patient_b,
            date=(timezone.now() + timedelta(days=1)).date(),
            time="14:00",
            service="Confidential Cervical Traction",
        )

        response = self.client.get(reverse("my_appointments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Knee Rehab Session")
        self.assertNotContains(response, "Confidential Cervical Traction")

    # ── 3. Payments & Invoicing Isolation ─────────────────────────

    def test_client_cannot_record_cash_payment(self):
        """TC-CP-007: Patient cannot record an in-person cash payment directly (must be 403 Forbidden)."""
        payload = {
            "amount": "650.00",
            "notes": "Paid at reception counter",
        }
        response = self.client.post(reverse("record_cash_payment"), payload, follow=False)
        self.assertEqual(response.status_code, 403)

        # Ensure no payment record was created by patient
        record = PaymentRecord.objects.filter(
            patient=self.patient_a, method="cash"
        ).first()
        self.assertIsNone(record)

    def test_client_cannot_record_upi_payment(self):
        """TC-CP-008: Patient cannot directly enter a UPI payment record (must be 403 Forbidden)."""
        payload = {
            "amount": "800.00",
            "transaction_id": "UPI-REF-9988776655",
        }
        response = self.client.post(reverse("record_upi_payment"), payload, follow=False)
        self.assertEqual(response.status_code, 403)

        record = PaymentRecord.objects.filter(
            patient=self.patient_a, transaction_id="UPI-REF-9988776655"
        ).first()
        self.assertIsNone(record)

    def test_client_cannot_see_other_patient_payments(self):
        """TC-CP-009: Patient A cannot see Patient B's financial receipts."""
        # Patient A Payment
        PaymentRecord.objects.create(
            hospital=self.hospital,
            patient=self.patient_a,
            amount=Decimal("500.00"),
            method="cash",
            status="paid",
            transaction_id="TXN-ALICE-123",
        )
        # Patient B Payment
        PaymentRecord.objects.create(
            hospital=self.hospital,
            patient=self.patient_b,
            amount=Decimal("9500.00"),
            method="cash",
            status="paid",
            transaction_id="TXN-BOB-SECRET-456",
        )

        response = self.client.get(reverse("payments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TXN-ALICE-123")
        self.assertNotContains(response, "TXN-BOB-SECRET-456")

    # ── 4. Clinical Notes & Medical Privacy ────────────────────────

    def test_client_session_notes_privacy_isolated(self):
        """TC-CP-010: Patient A never accesses Patient B's clinical notes."""
        # Note for patient B
        SessionNote.objects.create(
            hospital=self.hospital,
            staff=self.staff_doctor,
            patient=self.patient_b,
            diagnosis="Patient B Highly Confidential Diagnosis",
            treatment="Patient B Treatment Protocol",
            patient_visible=True,
        )

        # Checking patient A dashboard/views does not expose Patient B's medical notes
        response = self.client.get(reverse("client_dashboard"))
        self.assertNotContains(response, "Patient B Highly Confidential Diagnosis")

    # ── 5. Profile Management ─────────────────────────────────────

    def test_client_profile_view_and_update(self):
        """TC-CP-011: Patient updates contact, emergency contact, and blood group."""
        payload = {
            "first_name": "Alice",
            "last_name": "Greenwood",
            "email": "alice.updated@example.com",
            "phone_number": "9876500000",
            "gender": "Female",
            "date_of_birth": "1994-06-15",
            "blood_group": "A+",
            "emergency_contact": "9998881111",
            "address": "742 Evergreen Terrace, Springfield",
            "medical_notes": "Mild allergy to latex gloves",
        }
        response = self.client.post(reverse("edit_profile"), payload, follow=False)
        self.assertEqual(response.status_code, 302)

        self.patient_a.refresh_from_db()
        self.assertEqual(self.patient_a.last_name, "Greenwood")
        self.assertEqual(self.patient_a.email, "alice.updated@example.com")
        self.assertEqual(self.patient_a.profile.blood_group, "A+")
        self.assertEqual(self.patient_a.profile.emergency_contact, "9998881111")

    # ── 6. Reviews & Feedback ─────────────────────────────────────

    def test_client_submit_review(self):
        """TC-CP-012: Patient submits feedback review requiring admin moderation."""
        payload = {
            "reviewer_name": "Alice G.",
            "reviewer_title": "Post-Op Patient",
            "rating": "5",
            "message": "Dr. Watson was exceptionally attentive and my shoulder mobility has fully returned!",
        }
        response = self.client.post(reverse("submit_review"), payload, follow=False)
        self.assertEqual(response.status_code, 302)

        review = Review.objects.filter(
            patient=self.patient_a, message__icontains="shoulder mobility"
        ).first()
        self.assertIsNotNone(review)
        self.assertFalse(review.is_approved)  # Must remain unapproved until admin moderates
        self.assertEqual(review.rating, 5)

    # ── 7. Messaging & Notifications ──────────────────────────────

    def test_client_chat_with_clinic(self):
        """TC-CP-013: Patient sends a direct question to clinic team."""
        payload = {"content": "Can I do resistance band exercises before my Friday session?"}
        response = self.client.post(reverse("client_chat"), payload, follow=False)
        self.assertEqual(response.status_code, 302)

        msg = Message.objects.filter(
            sender=self.patient_a, content__icontains="resistance band"
        ).first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.receiver, self.clinic_admin)

    def test_client_notifications_mark_all_read(self):
        """TC-CP-014: Patient marks all unread notifications as read."""
        Notification.objects.create(
            recipient=self.patient_a,
            message="Your therapy session is scheduled for tomorrow at 10 AM.",
            is_read=False,
        )
        Notification.objects.create(
            recipient=self.patient_a,
            message="Invoice #INV-101 has been generated.",
            is_read=False,
        )

        response = self.client.get(reverse("mark_all_read"), follow=False)
        self.assertEqual(response.status_code, 302)
        unread_count = Notification.objects.filter(recipient=self.patient_a, is_read=False).count()
        self.assertEqual(unread_count, 0)
