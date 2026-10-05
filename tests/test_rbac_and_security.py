"""
Comprehensive Role-Based Access Control (RBAC), Multi-Tenancy Isolation,
and Security Vulnerability Test Suite.
Covers:
  - Vertical Privilege Escalation prevention
  - Horizontal Privilege Escalation prevention (Multi-Clinic Tenant Isolation)
  - Unauthenticated access restrictions
  - Patient data privacy & confidentiality
  - SQL Injection & XSS input safety
"""
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Appointment,
    LeaveApplication,
    DailyTask,
    SessionNote,
    Review,
    PaymentRecord,
)


class RoleBasedAccessControlAndSecurityTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        # Tenant A (Apollo Hospital)
        self.hospital_a = self.create_hospital(name="Apollo Metro", email="contact@apollo.com")
        self.admin_a = self.create_clinic_admin(
            self.hospital_a, username="admin_apollo", email="admin@apollo.com"
        )
        self.staff_a = self.create_staff(
            self.hospital_a, username="staff_apollo", email="staff@apollo.com"
        )
        self.patient_a = self.create_patient(
            self.hospital_a, username="patient_apollo", email="patient_a@apollo.com",
            first_name="Alice", last_name="Apollo"
        )

        # Tenant B (Fortis Hospital)
        self.hospital_b = self.create_hospital(name="Fortis Care", email="contact@fortis.com")
        self.admin_b = self.create_clinic_admin(
            self.hospital_b, username="admin_fortis", email="admin@fortis.com"
        )
        self.staff_b = self.create_staff(
            self.hospital_b, username="staff_fortis", email="staff@fortis.com"
        )
        self.patient_b = self.create_patient(
            self.hospital_b, username="patient_fortis", email="patient_b@fortis.com",
            first_name="Bob", last_name="Fortis"
        )

        # Super Admin
        self.super_admin = self.create_super_admin(
            username="platform_chief", email="chief@platform.com"
        )

    # ── 1. Unauthenticated Route Restrictions ─────────────────────

    def test_unauthenticated_super_admin_redirects_login(self):
        """TC-SEC-001: Unauthenticated request to super_admin_dashboard redirects to login."""
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_unauthenticated_clinic_admin_redirects_login(self):
        """TC-SEC-002: Unauthenticated request to admin_dashboard redirects to login."""
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_unauthenticated_staff_redirects_login(self):
        """TC-SEC-003: Unauthenticated request to staff_dashboard redirects to login."""
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_unauthenticated_client_redirects_login(self):
        """TC-SEC-004: Unauthenticated request to client_dashboard redirects to login."""
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    # ── 2. Vertical Privilege Escalation ──────────────────────────

    def test_client_cannot_access_super_admin_dashboard(self):
        """TC-SEC-005: Client attempting to access Super Admin dashboard is denied."""
        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("super_admin_dashboard"))
        # Must redirect away (to home or login) rather than rendering super admin template
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("super_admin_dashboard"))

    def test_client_cannot_access_clinic_admin_dashboard(self):
        """TC-SEC-006: Client attempting to access Clinic Admin dashboard is denied."""
        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("admin_dashboard"))
        # Must redirect to client_dashboard or home
        self.assertEqual(response.status_code, 302)

    def test_client_cannot_access_staff_dashboard(self):
        """TC-SEC-007: Client attempting to access Staff dashboard is denied."""
        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_staff_cannot_access_super_admin_dashboard(self):
        """TC-SEC-008: Staff attempting to access Super Admin dashboard is denied."""
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_staff_cannot_access_admin_settings(self):
        """TC-SEC-009: Staff attempting to access Clinic Admin settings is denied."""
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse("admin_settings"))
        # Staff is redirected away or denied
        self.assertEqual(response.status_code, 302)

    def test_clinic_admin_cannot_access_super_admin_dashboard(self):
        """TC-SEC-010: Clinic Admin attempting to access Super Admin dashboard is denied."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("super_admin_dashboard"))

    def test_clinic_admin_cannot_access_super_admin_hospitals(self):
        """TC-SEC-011: Clinic Admin attempting to access Super Admin Hospitals list is denied."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("super_admin_hospitals"))
        self.assertEqual(response.status_code, 302)

    # ── 3. Horizontal Privilege Escalation & Cross-Tenant Isolation ─

    def test_clinic_admin_cannot_see_other_clinic_patients(self):
        """TC-SEC-012: Clinic Admin A cannot see Clinic B patients in admin_patients."""
        # Create appointment in Hospital A for patient_a, and Hospital B for patient_b
        self.create_appointment(self.hospital_a, self.patient_a, time="10:00")
        self.create_appointment(self.hospital_b, self.patient_b, time="10:00")

        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_patients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "patient_a@apollo.com")
        self.assertNotContains(response, "patient_b@fortis.com")

    def test_clinic_admin_cannot_modify_other_clinic_appointment(self):
        """TC-SEC-013: Clinic Admin A cannot update status of Clinic B's appointment."""
        appt_b = self.create_appointment(
            self.hospital_b, self.patient_b, status="pending", time="10:00"
        )
        self.client.force_login(self.admin_a)
        # Attempt to confirm Hospital B appointment
        response = self.client.get(
            reverse("update_appointment", args=[appt_b.id, "confirmed"])
        )
        appt_b.refresh_from_db()
        # Appointment should NOT be confirmed by Admin A
        self.assertNotEqual(appt_b.status, "confirmed")

    def test_clinic_admin_cannot_see_other_clinic_staff(self):
        """TC-SEC-014: Clinic Admin A cannot see Clinic B's staff in admin_staff."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_staff"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff@apollo.com")
        self.assertNotContains(response, "staff@fortis.com")

    def test_clinic_admin_cannot_modify_other_clinic_leave(self):
        """TC-SEC-015: Clinic Admin A cannot approve/reject Clinic B's staff leave."""
        leave_b = self.create_leave(self.hospital_b, self.staff_b, status="pending")
        self.client.force_login(self.admin_a)
        # Attempt to approve Hospital B's staff leave
        response = self.client.get(
            reverse("update_leave", args=[leave_b.id, "approved"])
        )
        leave_b.refresh_from_db()
        self.assertNotEqual(leave_b.status, "approved")

    # ── 4. Patient Privacy & Data Confidentiality ──────────────────

    def test_patient_cannot_see_other_patient_appointments(self):
        """TC-SEC-016: Patient A cannot see Patient B's appointment in my_appointments."""
        appt_a = self.create_appointment(
            self.hospital_a, self.patient_a, service="orthopedic", time="10:00"
        )
        appt_b = self.create_appointment(
            self.hospital_a, self.patient_b, service="neurological", time="10:30"
        )

        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("my_appointments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orthopedic")
        self.assertNotContains(response, "Neurological")

    def test_patient_cannot_view_internal_session_notes(self):
        """TC-SEC-017: Patient cannot view session notes flagged with patient_visible=False."""
        hidden_note = self.create_session_note(
            self.hospital_a,
            self.staff_a,
            self.patient_a,
            diagnosis="Secret Doctor Diagnosis Internal Only",
            patient_visible=False,
        )
        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("client_dashboard"))
        self.assertNotContains(response, "Secret Doctor Diagnosis Internal Only")

    # ── 5. Input Safety: SQL Injection & XSS Payloads ─────────────

    def test_patient_search_sql_injection_safe(self):
        """TC-SEC-018: Malicious SQL-like input in search field does not crash database or leak data."""
        self.create_appointment(self.hospital_a, self.patient_a, name="Normal Patient")
        self.client.force_login(self.admin_a)

        sql_payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE core_appointment; --",
            "\" OR \"\"=\"",
        ]
        for payload in sql_payloads:
            response = self.client.get(reverse("admin_patients"), {"search": payload})
            # Server must return HTTP 200 without DB 500 error
            self.assertEqual(response.status_code, 200)
            self.assertTrue(Appointment.objects.exists())

    def test_xss_payload_in_review_is_escaped(self):
        """TC-SEC-019: Review containing XSS script payload is safely escaped and does not execute."""
        self.client.force_login(self.patient_a)
        xss_script = '<script>alert("xss")</script>'
        response = self.client.post(reverse("submit_review"), {
            "reviewer_name": "Jane Doe",
            "reviewer_title": "Patient",
            "rating": "5",
            "message": xss_script,
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify record was stored safely
        review = Review.objects.filter(patient=self.patient_a).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.message, xss_script)

        # When rendered in admin_reviews, verify raw script execution is avoided
        self.client.force_login(self.admin_a)
        admin_resp = self.client.get(reverse("admin_reviews"))
        self.assertContains(admin_resp, "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;")
