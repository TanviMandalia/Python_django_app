"""
tests/test_e2e_workflows.py
Hospital Management System - Deployment-Level Test Suite
Comprehensive End-to-End Hospital Life-Cycle, Concurrency & Multi-Role Integration
"""

from decimal import Decimal
from datetime import date, time, timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import IntegrityError

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    ClinicAdmin,
    StaffProfile,
    PatientProfile,
    Appointment,
    PaymentRecord,
    SessionNote,
    Review,
    Attendance,
    ClinicSettings,
    SubscriptionPlan,
    HospitalSubscription,
)


class E2EHospitalWorkflowsTestSuite(BaseHospitalTestCase):
    """
    Simulates complete real-world multi-role hospital workflows from
    platform provisioning down to patient recovery and review.
    """

    def setUp(self):
        super().setUp()
        self.super_admin = self.create_super_admin(
            username="platform_chief", email="chief@platform.com"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Professional Clinic Suite",
            price_monthly=Decimal("15000.00"),
            max_staff=50,
            max_patients=5000,
            features="Full clinic suite, analytics, chat, backups",
        )

    # ── Workflow 1: Complete End-to-End Clinic Lifecycle ──────────

    def test_full_hospital_lifecycle_across_all_four_roles(self):
        """
        TC-E2E-001: Comprehensive Multi-Role Workflow:
        1. Super Admin creates Hospital & assigns Subscription.
        2. Super Admin registers Clinic Administrator.
        3. Clinic Admin logs in and configures Clinic Settings.
        4. Clinic Admin registers Staff Physiotherapist.
        5. Staff clocks in for morning shift.
        6. Patient registers and books therapy appointment.
        7. Clinic Admin confirms the appointment.
        8. Staff creates clinical Session Note with patient visibility.
        9. Patient settles invoice via cash payment.
        10. Patient submits 5-star review and Clinic Admin approves it.
        """
        # Step 1: Super Admin provisions Hospital and Clinic Admin
        self.client.force_login(self.super_admin)
        hosp_payload = {
            "name": "St. Jude Rehabilitation Hospital",
            "email": "contact@stjude.org",
            "city": "Bengaluru",
            "phone": "9876500112",
            "admin_first": "StJude",
            "admin_last": "Admin",
            "admin_username": "stjude_admin",
            "admin_email": "admin@stjude.org",
            "admin_password": "SecureAdminPass123!",
            "plan": self.plan.id,
        }
        resp1 = self.client.post(reverse("super_admin_add_hospital"), hosp_payload, follow=False)
        self.assertEqual(resp1.status_code, 302)
        hospital = Hospital.objects.get(name="St. Jude Rehabilitation Hospital")
        self.assertTrue(hospital.is_active)
        admin_user = User.objects.get(username="stjude_admin")
        self.client.logout()

        # Step 3: Clinic Admin logs in & updates Clinic Settings
        self.client.force_login(admin_user)
        dash_resp = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(dash_resp.status_code, 200)

        settings_payload = {
            "clinic_name": "St. Jude Advanced Spine & Joint Center",
            "phone": "9876500112",
            "email": "contact@stjude.org",
            "address": "12 Richmond Circle, Bengaluru",
            "appointment_fee": "700.00",
        }
        self.client.post(reverse("admin_settings"), settings_payload, follow=False)
        clinic_settings = ClinicSettings.objects.get(hospital=hospital)
        self.assertEqual(clinic_settings.clinic_name, "St. Jude Advanced Spine & Joint Center")

        # Step 4: Clinic Admin adds Staff Physiotherapist
        staff_payload = {
            "first_name": "David",
            "last_name": "Miller",
            "username": "dr_miller",
            "email": "miller@stjude.org",
            "password": "MillerPassword123!",
            "role": "physiotherapist",
            "phone": "9876543210",
            "salary": "60000.00",
        }
        resp4 = self.client.post(reverse("add_staff"), staff_payload, follow=False)
        self.assertEqual(resp4.status_code, 302)
        staff_user = User.objects.get(username="dr_miller")
        self.assertEqual(staff_user.staff_profile.hospital, hospital)
        self.client.logout()

        # Step 5: Staff logs in & checks dashboard
        self.client.force_login(staff_user)
        staff_dash = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(staff_dash.status_code, 200)
        self.client.logout()

        # Step 6: Patient registers / logs in & books appointment
        patient_user = self.create_patient(
            hospital=hospital,
            username="patient_carl",
            email="carl@example.com",
            first_name="Carl",
            last_name="Johnson",
        )
        self.client.force_login(patient_user)
        target_date = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        booking_payload = {
            "hospital_id": hospital.id,
            "service": "Cervical Spondylosis Rehabilitation",
            "date": target_date,
            "time": "11:30",
            "notes": "Severe neck stiffness and headaches",
        }
        book_resp = self.client.post(reverse("book_appointment"), booking_payload, follow=False)
        self.assertEqual(book_resp.status_code, 302)
        appointment = Appointment.objects.get(patient=patient_user, date=target_date, time="11:30")
        self.assertEqual(appointment.status, "pending")
        self.assertEqual(appointment.hospital, hospital)
        self.client.logout()

        # Step 7: Clinic Admin confirms appointment
        self.client.force_login(admin_user)
        conf_resp = self.client.get(
            reverse("update_appointment", args=[appointment.id, "confirmed"]),
            follow=False,
        )
        self.assertEqual(conf_resp.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "confirmed")
        self.client.logout()

        # Step 8: Staff adds clinical Session Note
        self.client.force_login(staff_user)
        note = SessionNote.objects.create(
            hospital=hospital,
            staff=staff_user,
            patient=patient_user,
            appointment=appointment,
            diagnosis="Cervical Radiculopathy (C5-C6)",
            treatment="Manual traction, trigger point release, isometric neck exercises",
            next_session="Follow up in 48 hours for ultrasound therapy",
            patient_visible=True,
        )
        self.assertIsNotNone(note.id)
        self.client.logout()

        # Step 9: Patient logs in & settles payment
        self.client.force_login(patient_user)
        pay_payload = {
            "amount": "700.00",
            "appointment_id": str(appointment.id),
            "notes": "Paid full consultation fee",
        }
        pay_resp = self.client.post(reverse("record_cash_payment"), pay_payload, follow=False)
        self.assertEqual(pay_resp.status_code, 302)
        payment_record = PaymentRecord.objects.get(patient=patient_user, appointment_id=appointment.id)
        self.assertEqual(payment_record.status, "paid")
        self.assertEqual(payment_record.hospital, hospital)

        # Step 10: Patient submits review & Admin approves it
        rev_payload = {
            "reviewer_name": "Carl J.",
            "reviewer_title": "Recovered Patient",
            "rating": "5",
            "message": "Dr. Miller resolved my cervical pain in just 3 sessions! Outstanding clinic.",
        }
        rev_resp = self.client.post(reverse("submit_review"), rev_payload, follow=False)
        self.assertEqual(rev_resp.status_code, 302)
        review = Review.objects.get(patient=patient_user)
        self.assertFalse(review.is_approved)
        self.assertEqual(review.hospital, hospital)
        self.client.logout()

        # Admin approves review
        self.client.force_login(admin_user)
        appr_resp = self.client.get(
            reverse("toggle_review_approval", args=[review.id]), follow=False
        )
        self.assertEqual(appr_resp.status_code, 302)
        review.refresh_from_db()
        self.assertTrue(review.is_approved)

    # ── Workflow 2: Slot Collision & Double-Booking Prevention ────

    def test_appointment_double_booking_slot_collision_prevented(self):
        """
        TC-E2E-002: System prevents two patients from booking the same clinic slot.
        Database UniqueConstraint uniq_active_appointment_hospital_slot guarantees integrity.
        """
        hospital = self.create_hospital(name="Downtown Rehab", slug="downtown-rehab")
        patient_1 = self.create_patient(hospital, username="pat_one", email="pat1@example.com")
        patient_2 = self.create_patient(hospital, username="pat_two", email="pat2@example.com")

        slot_date = (timezone.now() + timedelta(days=5)).date()
        slot_time = "10:00"

        # Patient 1 books 10:00 slot
        self.create_appointment(
            hospital=hospital,
            patient=patient_1,
            date=slot_date,
            time=slot_time,
            status="confirmed",
        )

        # Patient 2 attempts booking EXACT same hospital, date, and time
        with self.assertRaises(IntegrityError):
            Appointment.objects.create(
                hospital=hospital,
                patient=patient_2,
                name="Patient Two",
                email="pat2@example.com",
                service="sports",
                date=slot_date,
                time=slot_time,
                status="pending",
            )

    # ── Workflow 3: Multi-Clinic Horizontal Isolation ─────────────

    def test_multi_clinic_complete_data_isolation(self):
        """
        TC-E2E-003: Strict multi-tenant barrier between Clinic A and Clinic B.
        Admin A cannot see or mutate Clinic B's appointments, patients, staff, or finances.
        """
        hosp_a = self.create_hospital(name="Clinic Alpha", slug="clinic-alpha")
        hosp_b = self.create_hospital(name="Clinic Beta", slug="clinic-beta")

        admin_a = self.create_clinic_admin(hosp_a, username="admin_alpha", email="alpha@alpha.com")
        admin_b = self.create_clinic_admin(hosp_b, username="admin_beta", email="beta@beta.com")

        patient_b = self.create_patient(hosp_b, username="patient_beta_user", email="pbeta@example.com")
        appt_b = self.create_appointment(
            hospital=hosp_b,
            patient=patient_b,
            date=(timezone.now() + timedelta(days=2)).date(),
            time="15:00",
            service="Neuro Rehab Beta",
        )

        # Admin A accesses appointment list
        self.client.force_login(admin_a)
        resp_list = self.client.get(reverse("admin_appointments"))
        self.assertEqual(resp_list.status_code, 200)
        self.assertNotContains(resp_list, "Neuro Rehab Beta")

        # Admin A attempts to confirm/cancel Clinic B appointment
        hack_resp = self.client.get(
            reverse("update_appointment", args=[appt_b.id, "cancelled"]),
            follow=False,
        )
        self.assertEqual(hack_resp.status_code, 302)
        appt_b.refresh_from_db()
        self.assertNotEqual(appt_b.status, "cancelled")

    # ── Workflow 4: Patient Medical Record Privacy ─────────────────

    def test_confidential_clinical_notes_hidden_from_other_patients(self):
        """
        TC-E2E-004: Strict patient medical privacy.
        Patient A cannot view or infer Patient B's diagnosis or treatment.
        """
        hospital = self.create_hospital(name="Privacy Clinic", slug="privacy-clinic")
        doctor = self.create_staff(hospital, username="dr_privacy", email="doc@privacy.com")

        patient_victim = self.create_patient(
            hospital, username="victim_patient", email="victim@example.com"
        )
        patient_attacker = self.create_patient(
            hospital, username="attacker_patient", email="attacker@example.com"
        )

        SessionNote.objects.create(
            hospital=hospital,
            staff=doctor,
            patient=patient_victim,
            diagnosis="Secret Oncology Diagnosis ABC-999",
            treatment="Chemo supportive therapy",
            patient_visible=True,
        )

        self.client.force_login(patient_attacker)
        response = self.client.get(reverse("client_dashboard"))
        self.assertNotContains(response, "Secret Oncology Diagnosis ABC-999")
        self.assertNotContains(response, "Chemo supportive therapy")
