"""
tests/test_salary_attendance_admin.py
Test suite verifying Multi-Tenant Hospital Isolation & Scoping for Salary and Attendance Administration.
"""

from decimal import Decimal
from django.urls import reverse
from django.utils import timezone

from tests.test_helpers import BaseHospitalTestCase
from core.models import SalaryRecord, Attendance, StaffProfile


class SalaryAttendanceAdminTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        # Clinic A
        self.clinic_a = self.create_hospital(
            name="Clinic Alpha", email="alpha@clinic.com"
        )
        self.admin_a = self.create_clinic_admin(
            self.clinic_a, username="admin_alpha", email="admin_alpha@clinic.com"
        )
        self.staff_a = self.create_staff(
            self.clinic_a,
            username="staff_alpha",
            email="staff_alpha@clinic.com",
            role="physiotherapist",
        )

        # Clinic B
        self.clinic_b = self.create_hospital(
            name="Clinic Beta", email="beta@clinic.com"
        )
        self.admin_b = self.create_clinic_admin(
            self.clinic_b, username="admin_beta", email="admin_beta@clinic.com"
        )
        self.staff_b = self.create_staff(
            self.clinic_b,
            username="staff_beta",
            email="staff_beta@clinic.com",
            role="physiotherapist",
        )

        # Super Admin
        self.super_admin = self.create_super_admin(
            username="super_ops", email="super_ops@platform.local"
        )

        # Salary Records
        self.salary_a = SalaryRecord.objects.create(
            hospital=self.clinic_a,
            staff=self.staff_a,
            month="October",
            year=2026,
            basic_salary=Decimal("50000.00"),
            bonus=Decimal("5000.00"),
            deduction=Decimal("1000.00"),
            net_salary=Decimal("54000.00"),
            is_paid=True,
            paid_on=timezone.now().date(),
        )
        self.salary_b = SalaryRecord.objects.create(
            hospital=self.clinic_b,
            staff=self.staff_b,
            month="October",
            year=2026,
            basic_salary=Decimal("40000.00"),
            bonus=Decimal("2000.00"),
            deduction=Decimal("500.00"),
            net_salary=Decimal("41500.00"),
            is_paid=True,
            paid_on=timezone.now().date(),
        )

        # Attendance Records
        self.attendance_a = Attendance.objects.create(
            hospital=self.clinic_a,
            staff=self.staff_a,
            date=timezone.now().date(),
            total_hours=Decimal("8.00"),
            notes="Regular shift",
        )
        self.attendance_b = Attendance.objects.create(
            hospital=self.clinic_b,
            staff=self.staff_b,
            date=timezone.now().date(),
            total_hours=Decimal("7.50"),
            notes="Clinic B shift",
        )

    # ── 1. Admin Salary List & Scoping ────────────────────────────

    def test_admin_salary_list_scoped_to_clinic(self):
        """Clinic admin sees only their clinic's salary records and staff."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_salary"))
        self.assertEqual(response.status_code, 200)
        records = list(response.context["salary_records"])
        self.assertIn(self.salary_a, records)
        self.assertNotIn(self.salary_b, records)

        staff_list = [sp.user for sp in response.context["staff_list"]]
        self.assertIn(self.staff_a, staff_list)
        self.assertNotIn(self.staff_b, staff_list)

    def test_super_admin_salary_list_sees_all(self):
        """Super admin sees salary records and staff across all clinics."""
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("admin_salary"))
        self.assertEqual(response.status_code, 200)
        records = list(response.context["salary_records"])
        self.assertIn(self.salary_a, records)
        self.assertIn(self.salary_b, records)

    def test_disburse_salary_assigns_hospital(self):
        """POST to admin_salary associates the record with the admin's hospital."""
        self.client.force_login(self.admin_a)
        payload = {
            "staff_id": self.staff_a.id,
            "month": "November",
            "year": 2026,
            "basic_salary": "48000.00",
            "bonus": "3000.00",
            "deduction": "1000.00",
        }
        response = self.client.post(reverse("admin_salary"), data=payload)
        self.assertEqual(response.status_code, 302)

        new_record = SalaryRecord.objects.get(
            staff=self.staff_a, month="November", year=2026
        )
        self.assertEqual(new_record.hospital, self.clinic_a)
        self.assertEqual(new_record.net_salary, Decimal("50000.00"))

    # ── 2. Edit Salary Scoping & Access Control ───────────────────

    def test_edit_salary_own_clinic_record_success(self):
        """Clinic admin can view and update their clinic's salary record."""
        self.client.force_login(self.admin_a)
        # GET form
        response = self.client.get(
            reverse("edit_salary", kwargs={"record_id": self.salary_a.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["record"], self.salary_a)

        # POST update
        payload = {
            "month": "October",
            "year": 2026,
            "basic_salary": "52000.00",
            "bonus": "6000.00",
            "deduction": "1000.00",
        }
        post_response = self.client.post(
            reverse("edit_salary", kwargs={"record_id": self.salary_a.id}), data=payload
        )
        self.assertEqual(post_response.status_code, 302)
        self.salary_a.refresh_from_db()
        self.assertEqual(self.salary_a.basic_salary, Decimal("52000.00"))
        self.assertEqual(self.salary_a.net_salary, Decimal("57000.00"))

    def test_edit_salary_other_clinic_record_blocked(self):
        """Clinic admin is blocked from editing another clinic's salary record."""
        self.client.force_login(self.admin_a)
        response = self.client.get(
            reverse("edit_salary", kwargs={"record_id": self.salary_b.id})
        )
        # Redirects to admin_salary with access denied message instead of raw 404
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin_salary"))

    def test_edit_salary_nonexistent_record_returns_404(self):
        """Non-existent salary record returns 404."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("edit_salary", kwargs={"record_id": 99999}))
        self.assertEqual(response.status_code, 404)

    # ── 3. Delete Salary Scoping ──────────────────────────────────

    def test_delete_salary_own_clinic_record_success(self):
        """Clinic admin can delete their clinic's salary record."""
        self.client.force_login(self.admin_a)
        response = self.client.post(
            reverse("delete_salary", kwargs={"record_id": self.salary_a.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SalaryRecord.objects.filter(id=self.salary_a.id).exists())

    def test_delete_salary_other_clinic_record_blocked(self):
        """Clinic admin is blocked from deleting another clinic's salary record."""
        self.client.force_login(self.admin_a)
        response = self.client.post(
            reverse("delete_salary", kwargs={"record_id": self.salary_b.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin_salary"))
        self.assertTrue(SalaryRecord.objects.filter(id=self.salary_b.id).exists())

    # ── 4. Attendance Scoping & CRUD ──────────────────────────────

    def test_admin_attendance_list_scoped_to_clinic(self):
        """Clinic admin sees only their clinic's attendance records."""
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_attendance"))
        self.assertEqual(response.status_code, 200)
        today_att = list(response.context["today_attendance"])
        self.assertIn(self.attendance_a, today_att)
        self.assertNotIn(self.attendance_b, today_att)

    def test_add_attendance_assigns_hospital(self):
        """Adding attendance sets the clinic hospital."""
        self.client.force_login(self.admin_a)
        payload = {
            "staff_id": self.staff_a.id,
            "date": "2026-10-15",
            "clock_in": "09:00",
            "clock_out": "17:00",
            "total_hours": "8.00",
            "notes": "Full day",
        }
        response = self.client.post(reverse("add_attendance"), data=payload)
        self.assertEqual(response.status_code, 302)
        att = Attendance.objects.get(staff=self.staff_a, date="2026-10-15")
        self.assertEqual(att.hospital, self.clinic_a)

    def test_edit_attendance_other_clinic_blocked(self):
        """Clinic admin cannot edit another clinic's attendance record."""
        self.client.force_login(self.admin_a)
        response = self.client.get(
            reverse("edit_attendance", kwargs={"att_id": self.attendance_b.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin_attendance"))
