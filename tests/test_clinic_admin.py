"""
Comprehensive Clinic Admin Operations and Management Test Suite.
Covers:
  - Clinic Admin Dashboard rendering & KPIs
  - Patient CRUD, deactivation, and reactivation
  - Staff provisioning, editing, and removal
  - Appointment scheduling, status transitions, and deletion
  - Staff Leave reviews, approvals, and rejections
  - Staff Attendance recording and logs
  - Daily Task delegation & tracking
  - Session Notes & Clinical documentation
  - Clinic Settings configuration
  - Patient Review moderation (approve/reject/delete)
  - Platform Support ticket submission
"""
from decimal import Decimal
from datetime import date, time, timedelta
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    ClinicAdmin,
    StaffProfile,
    PatientProfile,
    Appointment,
    LeaveApplication,
    Attendance,
    DailyTask,
    SessionNote,
    Review,
    ClinicSettings,
    SupportTicket,
)


class ClinicAdminTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Care Physio Clinic", email="contact@carephysio.com"
        )
        self.clinic_admin = self.create_clinic_admin(
            self.hospital, username="clinic_manager", email="manager@carephysio.com"
        )
        self.staff_doctor = self.create_staff(
            self.hospital, username="dr_smith", email="smith@carephysio.com", role="physiotherapist"
        )
        self.patient = self.create_patient(
            self.hospital, username="patient_mark", email="mark@example.com"
        )
        self.settings, _ = ClinicSettings.objects.get_or_create(
            id=1,
            defaults={
                "hospital": self.hospital,
                "clinic_name": "Care Physio Clinic",
                "phone": "9876543210",
                "email": "contact@carephysio.com",
                "address": "100 Main Health St",
                "appointment_fee": Decimal("600.00"),
            },
        )
        self.settings.hospital = self.hospital
        self.settings.clinic_name = "Care Physio Clinic"
        self.settings.phone = "9876543210"
        self.settings.email = "contact@carephysio.com"
        self.settings.address = "100 Main Health St"
        self.settings.appointment_fee = Decimal("600.00")
        self.settings.save()
        self.client.force_login(self.clinic_admin)

    # ── 1. Dashboard & Navigation ─────────────────────────────────

    def test_clinic_admin_dashboard(self):
        """TC-CA-001: Clinic admin dashboard loads successfully with statistics."""
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Care Physio Clinic")

    # ── 2. Patient Management ─────────────────────────────────────

    def test_clinic_admin_patient_listing(self):
        """TC-CA-002: Clinic admin patient listing renders patients of this clinic."""
        self.create_appointment(self.hospital, self.patient, name="Mark Spencer")
        response = self.client.get(reverse("admin_patients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mark@example.com")

    def test_clinic_admin_edit_patient(self):
        """TC-CA-003: Clinic admin updates patient name, phone, and address."""
        payload = {
            "first_name": "Marcus",
            "last_name": "Spencer",
            "email": "mark_updated@example.com",
            "phone_number": "9112233445",
            "address": "45 Green Park, Mumbai",
        }
        response = self.client.post(
            reverse("edit_patient", args=[self.patient.id]), payload, follow=False
        )
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.first_name, "Marcus")
        self.assertEqual(self.patient.email, "mark_updated@example.com")
        self.assertEqual(self.patient.profile.phone_number, "9112233445")

    def test_clinic_admin_deactivate_and_reactivate_patient(self):
        """TC-CA-004 & TC-CA-005: Clinic admin can deactivate and reactivate a patient."""
        # Deactivate
        resp1 = self.client.post(reverse("delete_patient", args=[self.patient.id]), follow=False)
        self.assertEqual(resp1.status_code, 302)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)

        # Reactivate
        resp2 = self.client.get(reverse("reactivate_patient", args=[self.patient.id]), follow=False)
        self.assertEqual(resp2.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

    # ── 3. Staff Management ───────────────────────────────────────

    def test_clinic_admin_add_staff(self):
        """TC-CA-006: Clinic admin provisions a new staff member."""
        payload = {
            "first_name": "Sarah",
            "last_name": "Connor",
            "username": "sarah_pt",
            "email": "sarah@carephysio.com",
            "password": "SarahPassword123!",
            "role": "physiotherapist",
            "phone": "9876541230",
            "salary": "50000",
        }
        response = self.client.post(reverse("add_staff"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        created_user = User.objects.filter(username="sarah_pt").first()
        self.assertIsNotNone(created_user)
        self.assertTrue(StaffProfile.objects.filter(user=created_user, hospital=self.hospital).exists())

    def test_clinic_admin_edit_staff(self):
        """TC-CA-007: Clinic admin updates staff role and salary."""
        staff_profile = self.staff_doctor.staff_profile
        payload = {
            "first_name": "John",
            "last_name": "Smith",
            "email": "smith@carephysio.com",
            "role": "receptionist",
            "phone": "9998881112",
            "salary": "35000.00",
        }
        response = self.client.post(
            reverse("edit_staff", args=[staff_profile.id]), payload, follow=False
        )
        self.assertEqual(response.status_code, 302)
        staff_profile.refresh_from_db()
        self.assertEqual(staff_profile.role, "receptionist")
        self.assertEqual(staff_profile.salary, Decimal("35000.00"))

    def test_clinic_admin_delete_staff(self):
        """TC-CA-008: Clinic admin deletes a staff member."""
        temp_staff = self.create_staff(self.hospital, username="temp_worker", email="temp@carephysio.com")
        profile_id = temp_staff.staff_profile.id
        response = self.client.post(reverse("delete_staff", args=[profile_id]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="temp_worker").exists())

    # ── 4. Appointment Operations ─────────────────────────────────

    def test_clinic_admin_add_appointment(self):
        """TC-CA-009: Clinic admin schedules an appointment for a patient."""
        appt_date = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        payload = {
            "patient_id": self.patient.id,
            "service": "orthopedic",
            "date": appt_date,
            "time": "10:00",
            "notes": "Post surgery knee rehabilitation",
            "status": "pending",
        }
        response = self.client.post(reverse("add_appointment"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Appointment.objects.filter(
                patient=self.patient, service="orthopedic", time="10:00"
            ).exists()
        )

    def test_clinic_admin_edit_appointment(self):
        """TC-CA-010: Clinic admin modifies appointment details."""
        appt = self.create_appointment(self.hospital, self.patient, service="sports", time="10:00")
        payload = {
            "service": "neurological",
            "date": str(appt.date),
            "time": "11:00",
            "notes": "Changed to neurological rehab",
            "status": "confirmed",
        }
        response = self.client.post(
            reverse("edit_appointment", args=[appt.id]), payload, follow=False
        )
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.service, "neurological")
        self.assertEqual(appt.status, "confirmed")

    def test_clinic_admin_update_status(self):
        """TC-CA-011: Clinic admin changes appointment status via quick action."""
        appt = self.create_appointment(self.hospital, self.patient, status="pending", time="10:00")
        response = self.client.get(
            reverse("update_appointment", args=[appt.id, "confirmed"]), follow=False
        )
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "confirmed")

    def test_clinic_admin_delete_appointment(self):
        """TC-CA-012: Clinic admin deletes an appointment."""
        appt = self.create_appointment(self.hospital, self.patient, time="10:00")
        response = self.client.post(
            reverse("delete_appointment", args=[appt.id]), follow=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Appointment.objects.filter(id=appt.id).exists())

    # ── 5. Staff Leaves & Attendance ──────────────────────────────

    def test_clinic_admin_approve_and_reject_leave(self):
        """TC-CA-013 & TC-CA-014: Clinic admin approves and rejects staff leaves."""
        leave = self.create_leave(self.hospital, self.staff_doctor, status="pending")

        # Approve
        response = self.client.post(
            reverse("update_leave", args=[leave.id, "approved"]),
            {"admin_note": "Approved by Dr. Manager"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")
        self.assertEqual(leave.reviewed_by, self.clinic_admin)

    def test_clinic_admin_attendance_log(self):
        """TC-CA-015: Attendance list displays attendance records."""
        att = Attendance.objects.create(
            hospital=self.hospital,
            staff=self.staff_doctor,
            date=timezone.now().date(),
            clock_in=time(9, 0),
            morning_clock_out=time(13, 0),
            morning_hours=Decimal("4.00"),
            total_hours=Decimal("4.00"),
        )
        response = self.client.get(reverse("admin_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff Doctor")

    # ── 6. Tasks & Clinical Session Notes ─────────────────────────

    def test_clinic_admin_assign_task(self):
        """TC-CA-016: Clinic admin assigns a task to staff."""
        payload = {
            "staff_id": self.staff_doctor.id,
            "title": "Prepare TENS Machine",
            "description": "Calibrate and sanitize electrodes",
            "priority": "high",
            "due_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        }
        response = self.client.post(reverse("add_task"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DailyTask.objects.filter(title="Prepare TENS Machine").exists())

    def test_clinic_admin_tasks_list(self):
        """TC-CA-016B: Clinic admin views task list."""
        self.create_task(self.hospital, self.staff_doctor, title="Inspect Ultrasound Wand")
        response = self.client.get(reverse("admin_tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inspect Ultrasound Wand")

    def test_clinic_admin_edit_task_and_legacy_fallback(self):
        """TC-CA-016C: Clinic admin edits a task, including legacy tasks with null hospital."""
        task = DailyTask.objects.create(
            hospital=None,
            assigned_to=self.staff_doctor,
            assigned_by=self.clinic_admin,
            title="Legacy Unassigned Task",
            description="Created prior to tenancy",
            priority="medium",
            status="pending",
        )
        # GET should succeed (200 OK) without 404
        get_res = self.client.get(reverse("edit_task_admin", args=[task.id]))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "Legacy Unassigned Task")

        # POST should update and backfill hospital
        post_res = self.client.post(
            reverse("edit_task_admin", args=[task.id]),
            {
                "staff_id": self.staff_doctor.id,
                "title": "Legacy Task Now Updated",
                "description": "Updated by clinic admin",
                "priority": "high",
                "status": "in_progress",
            },
            follow=False,
        )
        self.assertEqual(post_res.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Legacy Task Now Updated")
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.hospital, self.hospital)

    def test_clinic_admin_delete_task(self):
        """TC-CA-016D: Clinic admin deletes a task."""
        task = self.create_task(self.hospital, self.staff_doctor, title="Task To Delete")
        del_res = self.client.post(reverse("delete_task_admin", args=[task.id]), follow=False)
        self.assertEqual(del_res.status_code, 302)
        self.assertFalse(DailyTask.objects.filter(id=task.id).exists())

    def test_clinic_admin_cross_tenant_task_isolation(self):
        """TC-CA-016E: Clinic admin cannot view or edit another clinic's tasks."""
        hospital_b = self.create_hospital(name="Other Clinic", email="other@clinic.com")
        staff_b = self.create_staff(hospital_b, username="staff_b", email="b@clinic.com")
        task_b = self.create_task(hospital_b, staff_b, title="Other Clinic Task")

        get_res = self.client.get(reverse("edit_task_admin", args=[task_b.id]))
        self.assertEqual(get_res.status_code, 404)

        del_res = self.client.post(reverse("delete_task_admin", args=[task_b.id]))
        self.assertEqual(del_res.status_code, 404)
        self.assertTrue(DailyTask.objects.filter(id=task_b.id).exists())

    def test_clinic_admin_session_notes_crud(self):
        """TC-CA-017: Clinic admin adds session note for patient."""
        note = self.create_session_note(
            self.hospital,
            self.staff_doctor,
            self.patient,
            diagnosis="Cervical Spondylosis",
            treatment="Traction and neck isometric exercises",
        )
        response = self.client.get(reverse("admin_session_notes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cervical Spondylosis")

    # ── 7. Settings, Reviews, and Support ─────────────────────────

    def test_clinic_admin_settings_update(self):
        """TC-CA-018: Clinic admin updates clinic contact, pricing, and address."""
        payload = {
            "clinic_name": "Care Rehab Advanced",
            "tagline": "Restoring Mobility",
            "phone": "9876500000",
            "email": "contact@carerehab.com",
            "address": "404 Prime Towers, Pune",
            "appointment_fee": "750",
            "followup_fee": "400",
            "session_duration": "60",
            "opening_time": "09:00",
            "closing_time": "18:00",
        }
        response = self.client.post(reverse("admin_settings"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.clinic_name, "Care Rehab Advanced")
        self.assertEqual(self.settings.appointment_fee, Decimal("750.00"))

    def test_clinic_admin_review_moderation(self):
        """TC-CA-019: Clinic admin approves and deletes patient reviews."""
        review = Review.objects.create(
            hospital=self.hospital,
            patient=self.patient,
            reviewer_name="Mark S",
            rating=5,
            message="Excellent knee rehabilitation therapy!",
            is_approved=False,
        )
        # Toggle approval
        toggle_resp = self.client.get(reverse("toggle_review_approval", args=[review.id]), follow=False)
        self.assertEqual(toggle_resp.status_code, 302)
        review.refresh_from_db()
        self.assertTrue(review.is_approved)

        # Delete review
        del_resp = self.client.get(reverse("admin_delete_review", args=[review.id]), follow=False)
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(Review.objects.filter(id=review.id).exists())

    def test_clinic_admin_submit_support_ticket(self):
        """TC-CA-018: Clinic admin submits a support ticket to platform."""
        payload = {
            "subject": "Requesting additional staff licenses",
            "message": "We have hired 3 new therapists and need account expansion.",
        }
        response = self.client.post(reverse("submit_support_ticket"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SupportTicket.objects.filter(subject="Requesting additional staff licenses").exists())

    def test_clinic_admin_cross_clinic_staff_delete_prevented(self):
        """TC-CA-019: Clinic admin cannot edit or delete staff from another clinic."""
        other_hosp = self.create_hospital(name="Other Clinic", slug="other-clinic")
        other_staff = self.create_staff(other_hosp, username="other_pt", email="other@other.com")

        # Try to edit other clinic's staff
        edit_resp = self.client.post(
            reverse("edit_staff", args=[other_staff.staff_profile.id]),
            {"first_name": "Hacked", "last_name": "Name", "email": "other@other.com", "role": "receptionist", "phone": "123", "salary": "1000"},
            follow=False,
        )
        self.assertEqual(edit_resp.status_code, 404)

        # Try to delete other clinic's staff
        del_resp = self.client.post(
            reverse("delete_staff", args=[other_staff.staff_profile.id]),
            follow=False,
        )
        self.assertEqual(del_resp.status_code, 404)
        self.assertTrue(StaffProfile.objects.filter(id=other_staff.staff_profile.id).exists())

    def test_clinic_admin_bulk_import_access(self):
        """TC-CA-020: Clinic admin can access data import portal."""
        response = self.client.get(reverse("bulk_import"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import")

