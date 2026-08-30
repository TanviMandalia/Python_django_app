import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (
    Profile, StaffProfile, ClinicSettings, Appointment, Blog, Review,
    Hospital, SubscriptionPlan, HospitalSubscription, ClinicSubscriptionPayment,
    SupportTicket, DailyTask, Attendance, LeaveApplication, SalaryRecord, SessionNote
)


class CompleteViewsAndUrlsRenderingTest(TestCase):
    """
    Comprehensive automated integration test suite verifying that every view,
    URL endpoint, and responsive template renders cleanly with HTTP 200 OK.
    """

    def setUp(self):
        self.client = Client()

        # Clinic settings
        self.clinic_settings = ClinicSettings.objects.create(
            clinic_name="PhysioRehab Clinic",
            phone="9876543210",
            email="clinic@example.com",
            address="123 Health Ave, Medical Hub",
            appointment_fee=500,
            followup_fee=300,
            opening_time=datetime.time(9, 0),
            closing_time=datetime.time(20, 0)
        )

        # 1. Super Admin User
        self.superadmin = User.objects.create_superuser("superadmin_test", "super@test.com", "pass123")
        self.super_profile, _ = Profile.objects.get_or_create(user=self.superadmin)
        self.super_profile.is_platform_admin = True
        self.super_profile.save()

        # 2. Clinic Admin User
        self.admin = User.objects.create_user("admin_test", "admin@test.com", "pass123", is_superuser=True)

        # 3. Doctor User
        self.doctor = User.objects.create_user("doctor_test", "doctor@test.com", "pass123", is_staff=True)
        self.doctor_profile, _ = StaffProfile.objects.get_or_create(
            user=self.doctor,
            defaults={'role': 'physiotherapist', 'salary': 50000}
        )

        # 4. Staff / Receptionist User
        self.staff = User.objects.create_user("staff_test", "staff@test.com", "pass123", is_staff=True)
        self.staff_profile, _ = StaffProfile.objects.get_or_create(
            user=self.staff,
            defaults={'role': 'receptionist', 'salary': 25000}
        )

        # 5. Client / Patient User
        self.patient = User.objects.create_user("patient_test", "patient@test.com", "pass123")
        self.patient_profile, _ = Profile.objects.get_or_create(user=self.patient)
        self.patient_profile.phone_number = "9876543210"
        self.patient_profile.save()

        # Sample data
        self.blog = Blog.objects.create(
            title="Spine Recovery Guide",
            slug="spine-recovery-guide",
            content="Detailed recovery exercises...",
            category="Posture"
        )

        self.appointment = Appointment.objects.create(
            name="John Doe",
            email="john@example.com",
            phone="9876543210",
            service="orthopedic",
            date=timezone.now().date(),
            time="10:00",
            patient=self.patient,
            status="confirmed",
            consultation_fee=500
        )

        self.hospital = Hospital.objects.create(
            name="Apex Specialty Clinic",
            email="apex@clinic.com",
            phone="9988776655",
            city="Mumbai",
            is_active=True
        )

        self.plan = SubscriptionPlan.objects.create(
            name="standard",
            price_monthly=2999,
            is_active=True
        )

        self.sub = HospitalSubscription.objects.create(
            hospital=self.hospital,
            plan=self.plan,
            status="active",
            started_at=timezone.now().date(),
            expires_at=timezone.now().date() + timezone.timedelta(days=30)
        )

    def test_public_pages(self):
        """Verify public landing and informational pages."""
        public_urls = ["home", "about", "services", "contact", "blog_list"]
        for name in public_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed URL: {name}")

        # Blog detail
        response = self.client.get(reverse("blog_detail", kwargs={"slug": self.blog.slug}))
        self.assertEqual(response.status_code, 200)

    def test_auth_pages(self):
        """Verify login, register, request_otp pages."""
        auth_urls = ["login", "register", "request_otp"]
        for name in auth_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Auth URL: {name}")

    def test_client_dashboard_and_pages(self):
        """Verify client / patient pages when authenticated."""
        self.client.login(username="patient_test", password="pass123")
        client_urls = ["client_dashboard", "book_appointment", "my_appointments", "payments", "notifications", "client_chat"]
        for name in client_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Client URL: {name}")

    def test_doctor_pages(self):
        """Verify doctor / physiotherapist clinical pages."""
        self.client.login(username="doctor_test", password="pass123")
        doc_urls = ["progress_tracking", "reports_analytics", "add_session_note"]
        for name in doc_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Doctor URL: {name}")

    def test_staff_pages(self):
        """Verify employee / receptionist pages."""
        self.client.login(username="staff_test", password="pass123")
        staff_urls = ["staff_dashboard", "staff_attendance", "staff_leave", "staff_salary", "staff_tasks", "staff_session_notes"]
        for name in staff_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Staff URL: {name}")

    def test_admin_pages(self):
        """Verify clinic admin dashboard and management consoles."""
        self.client.login(username="admin_test", password="pass123")
        admin_urls = [
            "admin_dashboard", "admin_appointments", "add_appointment",
            "admin_patients", "admin_staff", "add_staff", "admin_leaves",
            "admin_attendance", "add_attendance", "admin_salary", "admin_tasks",
            "add_task", "admin_settings", "admin_promos", "admin_promo_add",
            "admin_reviews", "admin_add_review", "admin_blog_list", "admin_blog_add",
            "admin_session_notes", "admin_add_session_note", "admin_payments", "admin_chat"
        ]
        for name in admin_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Admin URL: {name}")

    def test_super_admin_pages(self):
        """Verify super admin SaaS platform management pages."""
        self.client.login(username="superadmin_test", password="pass123")
        super_urls = [
            "super_admin_dashboard", "super_admin_hospitals",
            "super_admin_subscriptions", "super_admin_analytics",
            "super_admin_all_payments", "super_admin_support"
        ]
        for name in super_urls:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Failed Super Admin URL: {name}")

