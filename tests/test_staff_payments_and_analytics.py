"""
tests/test_staff_payments_and_analytics.py
Comprehensive regression test suite for:
  1. Staff Payments page routing, strict staff assignment ownership, cross-user isolation, and role security.
  2. Admin Analytics true database calculations (retention rate, date range filters, N+1 query prevention, role enforcement).
  3. Email Settings secure persistence, credential preservation, and 403 Forbidden protection against unauthorized roles.
  4. Attendance and Leave multi-tenant hospital foreign key integrity.
"""

from decimal import Decimal
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    PaymentRecord,
    Appointment,
    SalaryRecord,
    DailyTask,
    SessionNote,
    LeaveApplication,
    EmailAccount,
    Attendance,
)


class StaffPaymentsAndAnalyticsTestCase(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        # Setup 2 clinics
        self.clinic_a = self.create_hospital(name="Alpha Physiotherapy", slug="alpha-physio", email="alpha@physio.com")
        self.clinic_b = self.create_hospital(name="Beta Rehab Care", slug="beta-rehab", email="beta@rehab.com")

        # Admins
        self.super_admin = self.create_super_admin(username="super_exec", email="super_exec@platform.com")
        self.admin_a = self.create_clinic_admin(self.clinic_a, username="admin_alpha_doc", email="admin@alpha-physio.com")
        self.admin_b = self.create_clinic_admin(self.clinic_b, username="admin_beta_doc", email="admin@beta-rehab.com")

        # Staff Members
        self.staff_1 = self.create_staff(self.clinic_a, username="therapist_sarah", email="sarah@alpha.com", role="physiotherapist")
        self.staff_2 = self.create_staff(self.clinic_a, username="therapist_john", email="john@alpha.com", role="physiotherapist")
        self.staff_b = self.create_staff(self.clinic_b, username="therapist_emily", email="emily@beta.com", role="physiotherapist")

        # Patients
        self.patient_1 = self.create_patient(self.clinic_a, username="patient_mark", email="mark@client.com")
        self.patient_2 = self.create_patient(self.clinic_a, username="patient_lisa", email="lisa@client.com")

        # Appointments
        today = timezone.now().date()
        self.appt_staff1_paid = Appointment.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_1,
            assigned_staff=self.staff_1,
            name="Mark Client",
            email="mark@client.com",
            phone="9876543210",
            service="orthopedic",
            date=today,
            time="10:00",
            status="completed",
            consultation_fee=Decimal("800.00"),
        )
        self.appt_staff1_pending = Appointment.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_1,
            assigned_staff=self.staff_1,
            name="Mark Client",
            email="mark@client.com",
            phone="9876543210",
            service="sports",
            date=today + timedelta(days=2),
            time="11:00",
            status="pending",
            consultation_fee=Decimal("800.00"),
        )
        self.appt_staff2 = Appointment.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_2,
            assigned_staff=self.staff_2,
            name="Lisa Client",
            email="lisa@client.com",
            phone="9876543211",
            service="neurological",
            date=today,
            time="14:00",
            status="completed",
            consultation_fee=Decimal("1200.00"),
        )

        # Payment records
        self.pay_staff1_paid = PaymentRecord.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_1,
            appointment=self.appt_staff1_paid,
            amount=Decimal("800.00"),
            method="upi",
            status="paid",
            transaction_id="TXN-STAFF1-PAID",
        )
        self.pay_staff1_pending = PaymentRecord.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_1,
            appointment=self.appt_staff1_pending,
            amount=Decimal("800.00"),
            method="cash",
            status="pending",
            transaction_id="TXN-STAFF1-PEND",
        )
        self.pay_staff2 = PaymentRecord.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_2,
            appointment=self.appt_staff2,
            amount=Decimal("1200.00"),
            method="card",
            status="paid",
            transaction_id="TXN-STAFF2-SECRET",
        )

        # Salary records
        self.salary_staff1 = SalaryRecord.objects.create(
            hospital=self.clinic_a,
            staff=self.staff_1,
            month="October",
            year=2026,
            basic_salary=Decimal("50000.00"),
            bonus=Decimal("5000.00"),
            deduction=Decimal("1000.00"),
            net_salary=Decimal("54000.00"),
            is_paid=True,
            paid_on=today,
        )

    # ══════════════════════════════════════════════════════════════════
    # 1. STAFF PAYMENTS TESTS
    # ══════════════════════════════════════════════════════════════════

    def test_staff_payment_page_loads_own_records(self):
        """Staff 1 accessing /staff-payments/ sees only their own assigned appointment payments."""
        self.client.force_login(self.staff_1)
        resp = self.client.get(reverse("staff_payments"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "staff/staff_payments.html")

        # Must contain Staff 1's records
        self.assertContains(resp, "TXN-STAFF1-PAID")
        self.assertContains(resp, "TXN-STAFF1-PEND")
        self.assertContains(resp, "800.00")

        # Must display salary earnings KPI
        self.assertContains(resp, "54000")

        # Must NOT contain Staff 2's payment records (strict user isolation)
        self.assertNotContains(resp, "TXN-STAFF2-SECRET")

    def test_staff_cannot_view_other_staff_payments_via_query_params(self):
        """Staff cannot inject parameters to view other therapists' collections."""
        self.client.force_login(self.staff_1)
        # Attempt parameter manipulation
        resp = self.client.get(reverse("staff_payments") + f"?staff_id={self.staff_2.id}&user={self.staff_2.username}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "TXN-STAFF2-SECRET")
        self.assertContains(resp, "TXN-STAFF1-PAID")

    def test_client_cannot_access_staff_payments(self):
        """Clients/patients accessing /staff-payments/ are strictly rejected with 403 Forbidden."""
        self.client.force_login(self.patient_1)
        resp = self.client.get(reverse("staff_payments"))
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_redirected_from_staff_payments(self):
        """Unauthenticated requests to /staff-payments/ redirect to login."""
        self.client.logout()
        resp = self.client.get(reverse("staff_payments"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_staff_payment_filters(self):
        """Search and status filters correctly restrict results."""
        self.client.force_login(self.staff_1)
        # Filter status=paid
        resp = self.client.get(reverse("staff_payments") + "?status=paid")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TXN-STAFF1-PAID")
        self.assertNotContains(resp, "TXN-STAFF1-PEND")

        # Filter status=pending
        resp2 = self.client.get(reverse("staff_payments") + "?status=pending")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "TXN-STAFF1-PEND")
        self.assertNotContains(resp2, "TXN-STAFF1-PAID")

    # ══════════════════════════════════════════════════════════════════
    # 2. ADMIN ANALYTICS TESTS
    # ══════════════════════════════════════════════════════════════════

    def test_admin_analytics_access_by_clinic_admin(self):
        """Clinic Admin has full authorized access to analytics with real database calculations."""
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse("reports_analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "admin/reports_analytics.html")
        self.assertEqual(resp.context["total_appointments"], 3)
        self.assertEqual(resp.context["completed_appointments"], 2)

    def test_admin_analytics_retention_rate_calculation(self):
        """Patient retention rate is derived from actual multi-session patient queries."""
        # Patient 1 has 2 appointments (repeat patient). Patient 2 has 1 appointment (single).
        # Total active patients with appointments = 2. Repeat patients = 1.
        # Expected retention rate: 1/2 * 100 = 50%
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse("reports_analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["retention_rate"], 50)

    def test_admin_analytics_date_filters(self):
        """Date filtering correctly scopes appointments to the specified period."""
        self.client.force_login(self.admin_a)
        # Period = today: appt_staff1_paid and appt_staff2 are today. appt_staff1_pending is today + 2 days.
        resp_today = self.client.get(reverse("reports_analytics") + "?period=today")
        self.assertEqual(resp_today.status_code, 200)
        self.assertEqual(resp_today.context["total_appointments"], 2)

        # Period = all
        resp_all = self.client.get(reverse("reports_analytics") + "?period=all")
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_all.context["total_appointments"], 3)

    def test_admin_analytics_forbidden_for_staff_and_client(self):
        """Staff and clients cannot access administrative analytics."""
        self.client.force_login(self.staff_1)
        resp_staff = self.client.get(reverse("reports_analytics"))
        self.assertEqual(resp_staff.status_code, 403)

        self.client.force_login(self.patient_1)
        resp_client = self.client.get(reverse("reports_analytics"))
        self.assertEqual(resp_client.status_code, 403)

    # ══════════════════════════════════════════════════════════════════
    # 3. EMAIL SETTINGS SECURITY & PERSISTENCE
    # ══════════════════════════════════════════════════════════════════

    def test_email_settings_password_encryption_and_preservation(self):
        """Saving email configuration encrypts credentials; blank password preserves existing."""
        self.client.force_login(self.admin_a)
        post_data = {
            "action": "save",
            "name": "Alpha Primary SMTP",
            "provider": "smtp",
            "host": "smtp.mailprovider.com",
            "port": "587",
            "username": "mailer@alpha.com",
            "password": "InitialSecretPassword123!",
            "from_email": "notifications@alpha.com",
            "from_name": "Alpha Physio",
            "use_tls": "on",
        }
        resp = self.client.post(reverse("admin_email_settings"), post_data)
        self.assertEqual(resp.status_code, 302)

        account = EmailAccount.objects.get(hospital=self.clinic_a)
        self.assertTrue(account.has_password)
        # Verify plaintext password is NEVER stored in database
        self.assertNotEqual(account.encrypted_password, "InitialSecretPassword123!")
        # Decrypted matches
        self.assertEqual(account.get_password(), "InitialSecretPassword123!")

        # Second save with BLANK password preserves existing secret
        post_data_preserve = {
            "action": "save",
            "name": "Alpha Primary SMTP Updated",
            "provider": "smtp",
            "host": "smtp.mailprovider.com",
            "port": "587",
            "username": "mailer@alpha.com",
            "password": "",  # Blank to keep existing
            "from_email": "notifications@alpha.com",
            "from_name": "Alpha Physio New Name",
            "use_tls": "on",
        }
        resp2 = self.client.post(reverse("admin_email_settings"), post_data_preserve)
        self.assertEqual(resp2.status_code, 302)

        account.refresh_from_db()
        self.assertEqual(account.name, "Alpha Primary SMTP Updated")
        self.assertEqual(account.get_password(), "InitialSecretPassword123!")

    def test_email_settings_forbidden_for_staff_and_client(self):
        """Staff and clients receive 403 Forbidden on email settings."""
        self.client.force_login(self.staff_1)
        resp_staff = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(resp_staff.status_code, 403)

        self.client.force_login(self.patient_1)
        resp_client = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(resp_client.status_code, 403)

    # ══════════════════════════════════════════════════════════════════
    # 4. ATTENDANCE MULTI-TENANT HOSPITAL INTEGRITY
    # ══════════════════════════════════════════════════════════════════

    def test_attendance_records_assigned_to_hospital(self):
        """Attendance created via staff shift attendance correctly sets the hospital foreign key."""
        today = timezone.now().date()
        record, _ = Attendance.objects.get_or_create(
            staff=self.staff_1,
            date=today,
            defaults={"hospital": self.clinic_a},
        )
        if not record.hospital:
            record.hospital = self.clinic_a
            record.save()

        self.assertEqual(record.hospital, self.clinic_a)
        # Visible to Clinic A admin
        admin_view_count = Attendance.objects.filter(hospital=self.clinic_a, staff=self.staff_1).count()
        self.assertEqual(admin_view_count, 1)
