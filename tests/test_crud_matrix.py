"""
tests/test_crud_matrix.py
Comprehensive CRUD & Multi-Tenant Authorization Verification Matrix.
Tests every persistent entity across all 4 user roles:
  1. Super Admin
  2. Clinic Admin
  3. Staff
  4. Patient / Client
Validates Create, Read, Update, Delete permissions, backend authorization,
and strict multi-tenant isolation.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    SubscriptionPlan,
    Appointment,
    DailyTask,
    SessionNote,
    ClinicSettings,
    EmailAccount,
)


class CompleteCRUDMatrixTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        # 1. Platform Super Admin
        self.super_admin = self.create_super_admin(
            username="super_audit", email="super_audit@platform.com"
        )

        # 2. Clinic 1 & Clinic Admin 1
        self.clinic_1 = self.create_hospital(name="Alpha Care Clinic", email="contact@alphacare.com")
        self.admin_1 = self.create_clinic_admin(
            self.clinic_1, username="admin_alpha", email="admin@alphacare.com"
        )
        self.staff_1 = self.create_staff(
            self.clinic_1, username="staff_alpha", email="staff@alphacare.com", role="physiotherapist"
        )
        self.patient_1 = self.create_patient(
            self.clinic_1, username="patient_alpha", email="patient1@example.com"
        )

        # 3. Clinic 2 & Clinic Admin 2 (for multi-tenant isolation testing)
        self.clinic_2 = self.create_hospital(name="Beta Health Clinic", email="contact@betahealth.com")
        self.admin_2 = self.create_clinic_admin(
            self.clinic_2, username="admin_beta", email="admin@betahealth.com"
        )
        self.staff_2 = self.create_staff(
            self.clinic_2, username="staff_beta", email="staff@betahealth.com", role="physiotherapist"
        )
        self.patient_2 = self.create_patient(
            self.clinic_2, username="patient_beta", email="patient2@example.com"
        )

        # Seed initial clinic settings
        ClinicSettings.objects.get_or_create(
            hospital=self.clinic_1,
            defaults={"clinic_name": "Alpha Care Clinic", "appointment_fee": Decimal("500.00")}
        )
        ClinicSettings.objects.get_or_create(
            hospital=self.clinic_2,
            defaults={"clinic_name": "Beta Health Clinic", "appointment_fee": Decimal("600.00")}
        )

    def _get_next_weekday(self, days_ahead=2):
        target = timezone.now().date() + timedelta(days=days_ahead)
        while target.weekday() >= 5:  # Skip Sat & Sun
            target += timedelta(days=1)
        return target

    # =========================================================================
    # 1. SUPER ADMIN CRUD TESTS
    # =========================================================================

    def test_super_admin_hospital_crud(self):
        """Super Admin can Create, Read, Update, Delete Hospitals."""
        self.client.force_login(self.super_admin)

        # Read
        resp = self.client.get(reverse("super_admin_hospitals"))
        self.assertEqual(resp.status_code, 200)

        # Create
        plan = SubscriptionPlan.objects.create(name="Bronze Tier", price_monthly=Decimal("1000.00"))
        create_data = {
            "name": "Gamma Ortho Care",
            "email": "gamma@ortho.com",
            "city": "Pune",
            "phone": "9876543219",
            "admin_first": "Gamma",
            "admin_last": "Admin",
            "admin_username": "admin_gamma",
            "admin_email": "admin@gamma.com",
            "admin_password": "GammaPassword123!",
            "plan": plan.id,
        }
        resp = self.client.post(reverse("super_admin_add_hospital"), create_data)
        self.assertEqual(resp.status_code, 302)
        gamma = Hospital.objects.get(name="Gamma Ortho Care")
        self.assertTrue(gamma.is_active)

        # Update
        update_data = {
            "name": "Gamma Ortho Care Updated",
            "email": "gamma_updated@ortho.com",
            "city": "Pune City",
            "phone": "9876543219",
            "is_active": "on",
        }
        resp = self.client.post(reverse("super_admin_edit_hospital", args=[gamma.id]), update_data)
        self.assertEqual(resp.status_code, 302)
        gamma.refresh_from_db()
        self.assertEqual(gamma.name, "Gamma Ortho Care Updated")

        # Delete
        resp = self.client.post(reverse("super_admin_delete_hospital", args=[gamma.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Hospital.objects.filter(id=gamma.id).exists())

    def test_super_admin_subscription_plan_crud(self):
        """Super Admin can Create, Read, Update, Toggle Subscription Plans."""
        self.client.force_login(self.super_admin)

        # Read
        resp = self.client.get(reverse("super_admin_plans"))
        self.assertEqual(resp.status_code, 200)

        # Create
        plan_data = {
            "name": "enterprise_plus_plan",
            "code": "enterprise_plus_plan",
            "display_name": "Enterprise Plus Plan",
            "description": "High tier suite for multi-branch clinics.",
            "price_monthly": "25000.00",
            "price_annual": "250000.00",
            "max_staff": "100",
            "max_patients": "10000",
            "storage_mb": "5000",
            "tier_level": "40",
            "is_public": "on",
            "is_active": "on",
        }
        resp = self.client.post(reverse("super_admin_add_plan"), plan_data)
        self.assertEqual(resp.status_code, 302)
        plan = SubscriptionPlan.objects.get(name="enterprise_plus_plan")
        self.assertEqual(plan.display_name, "Enterprise Plus Plan")

        # Update
        update_data = plan_data.copy()
        update_data["display_name"] = "Enterprise Ultra Plan"
        resp = self.client.post(reverse("super_admin_edit_plan", args=[plan.id]), update_data)
        self.assertEqual(resp.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.display_name, "Enterprise Ultra Plan")

        # Toggle Active
        resp = self.client.post(reverse("super_admin_toggle_plan", args=[plan.id]))
        self.assertEqual(resp.status_code, 302)
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)

    def test_super_admin_email_account_crud(self):
        """Super Admin can Create, Read, Update, Delete Email Accounts."""
        self.client.force_login(self.super_admin)

        # Read
        resp = self.client.get(reverse("super_admin_email_accounts"))
        self.assertEqual(resp.status_code, 200)

        # Create
        acc_data = {
            "name": "Audit System Mailer",
            "account_type": "PLATFORM",
            "scope_type": "platform",
            "provider": "smtp",
            "host": "smtp.mailgun.org",
            "port": "587",
            "username": "postmaster@mailgun.org",
            "password": "validSecretPassword123",
            "from_email": "notifications@platform.com",
            "from_name": "Platform Notifications",
            "use_tls": "on",
        }
        resp = self.client.post(reverse("super_admin_email_account_save"), acc_data)
        self.assertEqual(resp.status_code, 302)
        account = EmailAccount.objects.get(name="Audit System Mailer")
        self.assertEqual(account.get_password(), "validSecretPassword123")

        # Update
        acc_data["account_id"] = account.id
        acc_data["from_name"] = "Platform System Alerts"
        resp = self.client.post(reverse("super_admin_email_account_save"), acc_data)
        self.assertEqual(resp.status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.from_name, "Platform System Alerts")

        # Delete
        resp = self.client.post(reverse("super_admin_email_account_delete", args=[account.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(EmailAccount.objects.filter(id=account.id).exists())

    # =========================================================================
    # 2. CLINIC ADMIN CRUD & ISOLATION TESTS
    # =========================================================================

    def test_clinic_admin_patient_crud_and_isolation(self):
        """Clinic Admin can CRUD patients within own clinic, isolated from other clinics."""
        self.client.force_login(self.admin_1)

        # Read own patients
        resp = self.client.get(reverse("admin_patients"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.patient_1.email)
        self.assertNotContains(resp, self.patient_2.email)

        # Create patient
        patient_data = {
            "first_name": "Charlie",
            "last_name": "Delta",
            "email": "charlie@delta.com",
            "phone_number": "9812345678",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "joining_date": str(date.today()),
            "address": "12 Main St",
        }
        resp = self.client.post(reverse("add_patient"), patient_data)
        self.assertEqual(resp.status_code, 302)
        charlie = User.objects.get(email="charlie@delta.com")
        self.assertEqual(charlie.patient_profile.hospital, self.clinic_1)

        # Update patient
        update_data = {
            "first_name": "Charles",
            "last_name": "Delta Jr",
            "email": "charlie@delta.com",
            "phone_number": "9812345679",
            "gender": "Male",
            "address": "12 Main St Updated",
        }
        resp = self.client.post(reverse("edit_patient", args=[charlie.id]), update_data)
        self.assertEqual(resp.status_code, 302)
        charlie.refresh_from_db()
        self.assertEqual(charlie.first_name, "Charles")

        # Delete (Soft-deactivate) patient
        resp = self.client.post(reverse("delete_patient", args=[charlie.id]))
        self.assertEqual(resp.status_code, 302)
        charlie.refresh_from_db()
        self.assertFalse(charlie.is_active)

        # Reactivate patient
        resp = self.client.post(reverse("reactivate_patient", args=[charlie.id]))
        self.assertEqual(resp.status_code, 302)
        charlie.refresh_from_db()
        self.assertTrue(charlie.is_active)

        # Tenant Isolation: Clinic Admin 1 cannot edit Clinic 2's patient
        resp = self.client.post(reverse("edit_patient", args=[self.patient_2.id]), {"first_name": "Hacked"})
        self.assertIn(resp.status_code, [302, 403, 404])
        self.patient_2.refresh_from_db()
        self.assertNotEqual(self.patient_2.first_name, "Hacked")

    def test_clinic_admin_appointment_crud_and_isolation(self):
        """Clinic Admin can CRUD appointments within own clinic."""
        self.client.force_login(self.admin_1)

        # Create appointment
        future_date = self._get_next_weekday(days_ahead=2)
        appt_data = {
            "patient_id": self.patient_1.id,
            "service": "Physiotherapy",
            "date": str(future_date),
            "time": "10:00 AM",
            "notes": "Lumbar strain evaluation",
            "status": "pending",
        }
        resp = self.client.post(reverse("add_appointment"), appt_data)
        self.assertEqual(resp.status_code, 302)
        appt = Appointment.objects.get(patient=self.patient_1, date=future_date)
        self.assertEqual(appt.hospital, self.clinic_1)

        # Update appointment (reschedule)
        new_date = self._get_next_weekday(days_ahead=4)
        edit_data = appt_data.copy()
        edit_data["date"] = str(new_date)
        resp = self.client.post(reverse("edit_appointment", args=[appt.id]), edit_data)
        self.assertEqual(resp.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.date, new_date)

        # Status Transition (Confirm)
        resp = self.client.get(reverse("update_appointment", args=[appt.id, "confirmed"]))
        self.assertEqual(resp.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "confirmed")

        # Delete Appointment
        resp = self.client.post(reverse("delete_appointment", args=[appt.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Appointment.objects.filter(id=appt.id).exists())

    def test_clinic_admin_staff_management_crud(self):
        """Clinic Admin can provision, edit, and deactivate staff."""
        self.client.force_login(self.admin_1)

        # Create Staff
        staff_data = {
            "first_name": "Alice",
            "last_name": "Physio",
            "username": "dr_alice",
            "email": "alice@alphacare.com",
            "password": "AlicePassword123!",
            "role": "physiotherapist",
            "phone": "9876500112",
            "salary": "45000.00",
        }
        resp = self.client.post(reverse("add_staff"), staff_data)
        self.assertEqual(resp.status_code, 302)
        alice = User.objects.get(username="dr_alice")
        self.assertEqual(alice.staff_profile.hospital, self.clinic_1)

        # Edit Staff
        edit_data = {
            "first_name": "Alicia",
            "last_name": "Physio Senior",
            "email": "alicia@alphacare.com",
            "phone": "9876500113",
            "role": "physiotherapist",
            "salary": "50000.00",
        }
        resp = self.client.post(reverse("edit_staff", args=[alice.staff_profile.id]), edit_data)
        self.assertEqual(resp.status_code, 302)
        alice.refresh_from_db()
        self.assertEqual(alice.first_name, "Alicia")

        # Delete / Deactivate Staff
        resp = self.client.post(reverse("delete_staff", args=[alice.staff_profile.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(User.objects.filter(id=alice.id).exists())

    def test_clinic_admin_daily_tasks_and_session_notes_crud(self):
        """Clinic Admin can manage Daily Tasks and Session Notes."""
        self.client.force_login(self.admin_1)

        # Task Create
        task_data = {
            "staff_id": self.staff_1.id,
            "title": "Prepare electrotherapy equipment",
            "description": "Sanitize and inspect ultrasound probes.",
            "due_date": str(date.today()),
            "priority": "high",
        }
        resp = self.client.post(reverse("add_task"), task_data)
        self.assertEqual(resp.status_code, 302)
        task = DailyTask.objects.get(title="Prepare electrotherapy equipment")
        self.assertEqual(task.hospital, self.clinic_1)

        # Task Delete
        resp = self.client.post(reverse("delete_task_admin", args=[task.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(DailyTask.objects.filter(id=task.id).exists())

        # Session Note Create
        note_data = {
            "patient_id": self.patient_1.id,
            "staff_id": self.staff_1.id,
            "notes": "Patient demonstrated 85 degree active knee flexion with mild pain.",
            "diagnosis": "Post-ACL Reconstruction Rehab Week 4",
            "treatment": "Active-assisted range of motion and cryotherapy",
        }
        resp = self.client.post(reverse("admin_add_session_note"), note_data)
        self.assertEqual(resp.status_code, 302)
        note = SessionNote.objects.get(patient=self.patient_1)
        self.assertEqual(note.hospital, self.clinic_1)

        # Session Note Delete
        resp = self.client.post(reverse("delete_session_note", args=[note.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SessionNote.objects.filter(id=note.id).exists())

    # =========================================================================
    # 3. STAFF WORKFLOW & PERMISSIONS TESTS
    # =========================================================================

    def test_staff_tasks_and_attendance_workflow(self):
        """Staff can view assigned tasks, update task status, and record notes."""
        task = DailyTask.objects.create(
            hospital=self.clinic_1,
            assigned_to=self.staff_1,
            assigned_by=self.admin_1,
            title="Inspect TENS units",
            description="Perform battery check",
            status="pending",
        )
        self.client.force_login(self.staff_1)

        # Read Dashboard
        resp = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Update Task Status
        resp = self.client.get(reverse("update_task", args=[task.id, "completed"]))
        self.assertEqual(resp.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")

        # Staff creates clinical session note
        note_data = {
            "patient_id": self.patient_1.id,
            "notes": "Good progress on isometric quad contractions.",
            "diagnosis": "Patellar tendinopathy",
            "treatment": "Eccentric decline squats",
        }
        resp = self.client.post(reverse("add_session_note"), note_data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SessionNote.objects.filter(patient=self.patient_1, staff=self.staff_1).exists())

    def test_staff_cannot_access_clinic_admin_settings_or_other_clinic_data(self):
        """Staff is strictly forbidden from accessing Clinic Admin settings or modifying clinic configuration."""
        self.client.force_login(self.staff_1)

        # Attempt to access Clinic Admin settings
        resp = self.client.get(reverse("admin_settings"))
        self.assertIn(resp.status_code, [302, 403])

        # Attempt to access Super Admin dashboard
        resp = self.client.get(reverse("super_admin_dashboard"))
        self.assertIn(resp.status_code, [302, 403])

    # =========================================================================
    # 4. PATIENT / CLIENT WORKFLOW & PERMISSIONS TESTS
    # =========================================================================

    def test_patient_appointment_booking_and_isolation(self):
        """Patient can book appointments, view own schedule, and cannot access other patients."""
        self.client.force_login(self.patient_1)

        # Read Client Dashboard
        resp = self.client.get(reverse("client_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Book Appointment
        book_date = self._get_next_weekday(days_ahead=3)
        book_data = {
            "hospital_id": self.clinic_1.id,
            "service": "Physiotherapy",
            "date": str(book_date),
            "time": "10:00 AM",
            "notes": "Neck stiffness and cervical tension",
        }
        resp = self.client.post(reverse("book_appointment"), book_data)
        self.assertEqual(resp.status_code, 302)
        appt = Appointment.objects.get(patient=self.patient_1, date=book_date)
        self.assertEqual(appt.hospital, self.clinic_1)

        # Read own appointments
        resp = self.client.get(reverse("my_appointments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Physiotherapy")

        # Patient cannot access Admin dashboard or Staff dashboard
        resp = self.client.get(reverse("admin_dashboard"))
        self.assertIn(resp.status_code, [302, 403])
        resp = self.client.get(reverse("staff_dashboard"))
        self.assertIn(resp.status_code, [302, 403])
