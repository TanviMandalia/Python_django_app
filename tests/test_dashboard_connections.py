"""
tests/test_dashboard_connections.py
Focused automated tests verifying the end-to-end connections between:
- Four Dashboards (Super Admin, Clinic Admin, Staff, Client)
- Public Appointment Booking Workflow
- PostgreSQL ORM joins (select_related)
- Role-based access control and tenant isolation
"""

from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    SubscriptionPlan,
    HospitalSubscription,
    ClinicAdmin,
    StaffProfile,
    Appointment,
    PublicAppointmentRequest,
    PaymentRecord,
)

User = get_user_model()


class DashboardAndBookingConnectionsTest(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.now().date()

        # 1. Setup Plan & Hospital
        self.plan = SubscriptionPlan.objects.create(
            name="Pro Growth Plan",
            code="pro-growth",
            price_monthly=1999.00,
            tier_level=3,
            is_active=True,
        )
        self.hospital = self.create_hospital(
            name="Apex Physio Rehabilitation",
            email="care@apexphysio.com",
            phone="+91 94095 10501",
        )
        self.sub = HospitalSubscription.objects.create(
            hospital=self.hospital,
            plan=self.plan,
            status="active",
            started_at=self.today,
            expires_at=self.today + timedelta(days=30),
        )

        # 2. Super Admin User
        self.super_admin = self.create_super_admin(
            username="platform_owner",
            email="superadmin@physiorehab.com",
        )

        # 3. Clinic Admin User
        self.clinic_admin_user = self.create_clinic_admin(
            hospital=self.hospital,
            username="apex_admin",
            email="admin@apexphysio.com",
        )

        # 4. Staff / Physiotherapist User
        self.staff_user = self.create_staff(
            hospital=self.hospital,
            username="dr_sharma",
            email="sharma@apexphysio.com",
            first_name="Raj",
            last_name="Sharma",
            role="doctor",
        )

        # 5. Client / Patient User
        self.patient_user = self.create_patient(
            username="john_patient",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )

    def test_super_admin_dashboard_connection_and_access(self):
        """Super Admin Dashboard is accessible only to platform superadmins and displays clinic metrics."""
        # Unauthenticated redirects to login
        resp = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(resp.status_code, 302)

        # Clinic admin is rejected/redirected
        self.client.force_login(self.clinic_admin_user)
        resp = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(resp.status_code, 302)

        # Super Admin succeeds
        self.client.force_login(self.super_admin)
        resp = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "super_admin/super_admin_dashboard.html")
        self.assertIn("total_hospitals", resp.context)
        self.assertIn("clinics_near_limit", resp.context)
        self.assertEqual(resp.context["total_hospitals"], 1)

    def test_clinic_admin_dashboard_connection_and_public_request_kpi(self):
        """Clinic Admin Dashboard connects to scoped appointments and displays pending public requests."""
        # Create an internal appointment
        appt = Appointment.objects.create(
            hospital=self.hospital,
            patient=self.patient_user,
            assigned_staff=self.staff_user,
            name="John Doe",
            email="john@example.com",
            phone="9876543210",
            service="orthopedic",
            date=self.today,
            time="10:00 AM",
            status="pending",
        )
        # Create a public appointment request
        pub_req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Public Visitor",
            email="visitor@example.com",
            phone="9123456789",
            preferred_date=self.today + timedelta(days=1),
            preferred_time="11:00 AM",
            status="pending",
        )

        self.client.force_login(self.clinic_admin_user)
        resp = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "admin/admin_dashboard.html")
        self.assertEqual(resp.context["total_appointments"], 1)
        self.assertEqual(resp.context["public_pending_count"], 1)
        self.assertEqual(len(resp.context["recent_public_requests"]), 1)
        self.assertContains(resp, "Online Booking Requests")

    def test_staff_dashboard_connection_and_assigned_schedule(self):
        """Staff Dashboard connects to shift attendance, tasks, and today's assigned appointments."""
        # Create appointment assigned to Dr. Sharma
        appt = Appointment.objects.create(
            hospital=self.hospital,
            patient=self.patient_user,
            assigned_staff=self.staff_user,
            name="John Doe",
            email="john@example.com",
            phone="9876543210",
            service="sports",
            date=self.today,
            time="11:30 AM",
            status="confirmed",
        )

        self.client.force_login(self.staff_user)
        resp = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "staff/staff_dashboard.html")
        self.assertEqual(resp.context["today_appointments_count"], 1)
        self.assertEqual(len(resp.context["today_appointments"]), 1)
        self.assertContains(resp, "My Assigned Clinical Schedule")
        self.assertContains(resp, "John Doe")

    def test_client_dashboard_and_my_appointments_connection(self):
        """Client Dashboard displays patient appointments, payments, and public request visibility."""
        appt = Appointment.objects.create(
            hospital=self.hospital,
            patient=self.patient_user,
            assigned_staff=self.staff_user,
            name="John Doe",
            email="john@example.com",
            phone="9876543210",
            service="neurological",
            date=self.today + timedelta(days=2),
            time="12:00 PM",
            status="confirmed",
        )
        pay = PaymentRecord.objects.create(
            hospital=self.hospital,
            patient=self.patient_user,
            appointment=appt,
            amount=750.00,
            status="paid",
        )
        pub_req = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="John Doe",
            email=self.patient_user.email,
            phone="9876543210",
            preferred_date=self.today + timedelta(days=5),
            preferred_time="04:00 PM",
            status="pending",
        )

        self.client.force_login(self.patient_user)
        resp = self.client.get(reverse("client_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "client/client_dashboard.html")
        self.assertEqual(resp.context["upcoming_count"], 1)
        self.assertEqual(len(resp.context["my_payments"]), 1)

        # Check my_appointments view
        resp_appts = self.client.get(reverse("my_appointments"))
        self.assertEqual(resp_appts.status_code, 200)
        self.assertEqual(len(resp_appts.context["appointments"]), 1)
        self.assertEqual(len(resp_appts.context["my_public_requests"]), 1)
        self.assertContains(resp_appts, pub_req.reference_id)

    def test_public_booking_flow_creates_postgres_record(self):
        """Public visitor booking creates a valid PostgreSQL record and confirms via PRG pattern."""
        post_data = {
            "patient_name": "Anita Patel",
            "email": "anita.patel@example.com",
            "phone": "+91 98251 12345",
            "preferred_date": (self.today + timedelta(days=3)).strftime("%Y-%m-%d"),
            "preferred_time": "10:30 AM",
            "service_or_reason": "Post-surgery knee rehabilitation",
            "preferred_contact_method": "phone",
            "consent": "true",
            "clinic": self.hospital.slug,
        }
        resp = self.client.post(reverse("appointment_contact"), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verify record exists in PostgreSQL
        req_obj = PublicAppointmentRequest.objects.filter(email="anita.patel@example.com").first()
        self.assertIsNotNone(req_obj)
        self.assertEqual(req_obj.status, "pending")
        self.assertTrue(req_obj.reference_id.startswith("PAR-"))
        self.assertEqual(req_obj.hospital, self.hospital)
