"""
tests/test_staff_operations.py
Hospital Management System - Deployment-Level Test Suite
Role 3: STAFF (Physiotherapists, Nurses, Clinic Staff) Operations & Scoped Access
"""

from decimal import Decimal
from datetime import date, time, timedelta, datetime
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    StaffProfile,
    Attendance,
    DailyTask,
    LeaveApplication,
    SalaryRecord,
    SessionNote,
    Message,
)


class StaffOperationsTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(
            name="Care Physio Center", email="staff@carephysio.com"
        )
        self.clinic_admin = self.create_clinic_admin(
            self.hospital, username="clinic_head", email="head@carephysio.com"
        )
        self.staff_doctor = self.create_staff(
            self.hospital,
            username="dr_emily",
            email="emily@carephysio.com",
            first_name="Emily",
            last_name="Watson",
            role="physiotherapist",
        )
        self.other_staff = self.create_staff(
            self.hospital,
            username="nurse_bob",
            email="bob@carephysio.com",
            first_name="Bob",
            last_name="Jones",
            role="assistant",
        )
        self.patient = self.create_patient(
            self.hospital, username="patient_alex", email="alex@example.com"
        )

        self.client.force_login(self.staff_doctor)

    # ── 1. Dashboard Access & Authorization ────────────────────────

    def test_staff_dashboard_access(self):
        """TC-ST-001: Staff member accesses staff dashboard with metrics."""
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff")

    def test_client_denied_staff_dashboard(self):
        """TC-ST-002: Regular patient is redirected from staff dashboard."""
        self.client.force_login(self.patient)
        response = self.client.get(reverse("staff_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("client_dashboard"))

    def test_unauthenticated_denied_staff_dashboard(self):
        """TC-ST-003: Unauthenticated request is redirected to login."""
        self.client.logout()
        response = self.client.get(reverse("staff_dashboard"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    # ── 2. Attendance & Shift Clock-In/Out ─────────────────────────

    def test_staff_morning_clock_in_outside_window(self):
        """TC-ST-004: Morning clock-in outside window returns warning/error."""
        # 3:00 AM is outside morning shift (10:00 AM - 1:00 PM)
        mock_early = timezone.now().replace(hour=3, minute=0, second=0)
        with patch("django.utils.timezone.localtime", return_value=mock_early):
            response = self.client.post(
                reverse("staff_attendance"),
                {"action": "morning_clock_in"},
                follow=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertFalse(
                Attendance.objects.filter(
                    staff=self.staff_doctor,
                    date=timezone.now().date(),
                    clock_in__isnull=False,
                ).exists()
            )

    def test_staff_morning_clock_in_inside_window(self):
        """TC-ST-005: Morning clock-in inside 10 AM - 1 PM records attendance."""
        mock_morning = timezone.now().replace(hour=10, minute=5, second=0)
        with patch("django.utils.timezone.localtime", return_value=mock_morning):
            response = self.client.post(
                reverse("staff_attendance"),
                {"action": "morning_clock_in"},
                follow=False,
            )
            self.assertEqual(response.status_code, 302)
            record = Attendance.objects.filter(
                staff=self.staff_doctor, date=timezone.now().date()
            ).first()
            self.assertIsNotNone(record)
            self.assertIsNotNone(record.clock_in)

    def test_staff_duplicate_morning_clock_in_prevented(self):
        """TC-ST-006: Duplicate morning clock-in is rejected."""
        today = timezone.now().date()
        Attendance.objects.create(
            staff=self.staff_doctor,
            date=today,
            clock_in=time(10, 5),
        )
        mock_morning = timezone.now().replace(hour=10, minute=15, second=0)
        with patch("django.utils.timezone.localtime", return_value=mock_morning):
            response = self.client.post(
                reverse("staff_attendance"),
                {"action": "morning_clock_in"},
                follow=False,
            )
            self.assertEqual(response.status_code, 302)
            # Clock-in time must remain original 10:05
            record = Attendance.objects.get(staff=self.staff_doctor, date=today)
            self.assertEqual(record.clock_in, time(10, 5))

    def test_staff_morning_clock_out(self):
        """TC-ST-007: Staff clocks out from active morning shift."""
        today = timezone.now().date()
        record = Attendance.objects.create(
            staff=self.staff_doctor,
            date=today,
            clock_in=time(10, 0),
        )
        mock_clockout = timezone.now().replace(hour=13, minute=0, second=0)
        with patch("django.utils.timezone.localtime", return_value=mock_clockout):
            response = self.client.post(
                reverse("staff_attendance"),
                {"action": "morning_clock_out"},
                follow=False,
            )
            self.assertEqual(response.status_code, 302)
            record.refresh_from_db()
            self.assertIsNotNone(record.morning_clock_out)
            self.assertGreater(record.morning_hours, Decimal("0.00"))

    def test_staff_evening_clock_in(self):
        """TC-ST-008: Staff clocks in during evening shift window (4 PM - 8 PM)."""
        mock_evening = timezone.now().replace(hour=16, minute=10, second=0)
        with patch("django.utils.timezone.localtime", return_value=mock_evening):
            response = self.client.post(
                reverse("staff_attendance"),
                {"action": "evening_clock_in"},
                follow=False,
            )
            self.assertEqual(response.status_code, 302)
            record = Attendance.objects.filter(
                staff=self.staff_doctor, date=timezone.now().date()
            ).first()
            self.assertIsNotNone(record)
            self.assertIsNotNone(record.evening_clock_in)

    def test_staff_attendance_history_view(self):
        """TC-ST-009: Staff views their attendance history log."""
        today = timezone.now().date()
        Attendance.objects.create(
            staff=self.staff_doctor,
            date=today - timedelta(days=1),
            clock_in=time(10, 0),
            morning_clock_out=time(13, 0),
            morning_hours=Decimal("3.00"),
            total_hours=Decimal("3.00"),
        )
        response = self.client.get(reverse("staff_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance")

    # ── 3. Daily Task Management ──────────────────────────────────

    def test_staff_tasks_listing(self):
        """TC-ST-010: Staff views assigned tasks list."""
        DailyTask.objects.create(
            assigned_to=self.staff_doctor,
            assigned_by=self.clinic_admin,
            title="Sanitize Ultrasound Probe",
            description="Use antiseptic wipes after every patient",
            priority="high",
            status="pending",
            due_date=timezone.now().date(),
        )
        response = self.client.get(reverse("staff_tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sanitize Ultrasound Probe")

    def test_staff_update_task_in_progress(self):
        """TC-ST-011: Staff marks assigned task as in_progress."""
        task = DailyTask.objects.create(
            assigned_to=self.staff_doctor,
            assigned_by=self.clinic_admin,
            title="Review Patient Intake Notes",
            priority="medium",
            status="pending",
            due_date=timezone.now().date(),
        )
        response = self.client.get(
            reverse("update_task", args=[task.id, "in_progress"]), follow=False
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")

    def test_staff_update_task_completed(self):
        """TC-ST-012: Staff marks assigned task as completed."""
        task = DailyTask.objects.create(
            assigned_to=self.staff_doctor,
            assigned_by=self.clinic_admin,
            title="Calibrate Traction Unit",
            priority="high",
            status="in_progress",
            due_date=timezone.now().date(),
        )
        response = self.client.get(
            reverse("update_task", args=[task.id, "completed"]), follow=False
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")
        self.assertIsNotNone(task.completed_at)

    def test_staff_cannot_update_other_staff_task(self):
        """TC-ST-013: Staff A cannot modify tasks assigned to Staff B."""
        task_b = DailyTask.objects.create(
            assigned_to=self.other_staff,
            assigned_by=self.clinic_admin,
            title="Nurse Inventory Restock",
            status="pending",
            due_date=timezone.now().date(),
        )
        response = self.client.get(
            reverse("update_task", args=[task_b.id, "completed"]), follow=False
        )
        self.assertEqual(response.status_code, 404)
        task_b.refresh_from_db()
        self.assertEqual(task_b.status, "pending")

    # ── 4. Leave Applications & Salary Records ────────────────────

    def test_staff_apply_leave(self):
        """TC-ST-014: Staff submits a leave application."""
        from_d = (timezone.now() + timedelta(days=5)).date()
        to_d = (timezone.now() + timedelta(days=6)).date()
        payload = {
            "leave_type": "casual",
            "from_date": from_d.strftime("%Y-%m-%d"),
            "to_date": to_d.strftime("%Y-%m-%d"),
            "reason": "Family wedding event attendance",
        }
        response = self.client.post(reverse("staff_leave"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            LeaveApplication.objects.filter(
                staff=self.staff_doctor, leave_type="casual", reason__icontains="wedding"
            ).exists()
        )

    def test_staff_salary_slip_view(self):
        """TC-ST-015: Staff views salary history and earnings."""
        SalaryRecord.objects.create(
            hospital=self.hospital,
            staff=self.staff_doctor,
            month="October",
            year=2026,
            basic_salary=Decimal("45000.00"),
            bonus=Decimal("5000.00"),
            deduction=Decimal("2000.00"),
            net_salary=Decimal("48000.00"),
            is_paid=True,
            paid_on=timezone.now().date(),
        )
        response = self.client.get(reverse("staff_salary"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "48000")

    # ── 5. Session Notes & Clinical Documentation ─────────────────

    def test_staff_create_session_note(self):
        """TC-ST-016: Staff creates clinical session note for a patient."""
        payload = {
            "patient_id": self.patient.id,
            "diagnosis": "Lumbar Spondylosis with Radiculopathy",
            "treatment": "Spinal decompression, core stabilization, moist heat therapy",
            "next_session": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        }
        response = self.client.post(reverse("add_session_note"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SessionNote.objects.filter(
                staff=self.staff_doctor,
                patient=self.patient,
                diagnosis__icontains="Lumbar Spondylosis",
            ).exists()
        )

    def test_staff_chat_with_admin(self):
        """TC-ST-017: Staff sends message to clinic admin."""
        payload = {"content": "Hello Admin, please approve supplies request."}
        response = self.client.post(reverse("client_chat"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Message.objects.filter(
                sender=self.staff_doctor,
                receiver=self.clinic_admin,
                content__icontains="supplies request",
            ).exists()
        )
