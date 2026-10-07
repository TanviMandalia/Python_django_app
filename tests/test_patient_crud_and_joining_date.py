"""
Comprehensive automated tests for Patient CRUD operations, joining date persistence
without timezone shift, and multi-tenant RBAC security.
"""
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.models import User

from core.models import PatientProfile, Profile, StaffProfile, Hospital
from tests.test_helpers import BaseHospitalTestCase


class PatientCRUDAndJoiningDateTests(BaseHospitalTestCase):
    """Verifies complete patient CRUD, joining date accuracy, and security isolation."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Dr. Dhvani Patalia Physio Rehab")
        self.clinic_admin = self.create_clinic_admin(self.hospital, username="dhvani_admin")
        self.super_admin = self.create_super_admin(username="platform_admin")
        self.client_user = self.create_patient(self.hospital, username="patient_rajesh")

        self.other_hospital = self.create_hospital(name="Other Clinic", email="other@clinic.com")
        self.other_admin = self.create_clinic_admin(self.other_hospital, username="other_admin")

    def test_add_patient_creates_user_and_profiles(self):
        """Admin can register a new patient with joining date and demographic data."""
        self.client.force_login(self.clinic_admin)
        post_data = {
            "first_name": "Aarav",
            "last_name": "Patel",
            "email": "aarav.patel@example.com",
            "phone_number": "9409510501",
            "gender": "Male",
            "date_of_birth": "1992-04-15",
            "joining_date": "2026-06-14",
            "blood_group": "B+",
            "emergency_contact": "9876543210",
            "address": "Navrangpura, Ahmedabad",
            "medical_notes": "Cervical radiculopathy, chronic neck stiffness",
        }
        res = self.client.post("/admin-patients/add/", post_data)
        self.assertEqual(res.status_code, 302)  # Redirects to admin_patients

        # Verify created User & Profiles
        patient = User.objects.get(email="aarav.patel@example.com")
        self.assertEqual(patient.first_name, "Aarav")
        self.assertEqual(patient.last_name, "Patel")

        profile = patient.profile
        self.assertEqual(profile.gender, "Male")
        self.assertEqual(profile.date_of_birth, date(1992, 4, 15))
        self.assertEqual(profile.joining_date, date(2026, 6, 14))
        self.assertEqual(profile.blood_group, "B+")
        self.assertEqual(profile.address, "Navrangpura, Ahmedabad")

        patient_profile = patient.patient_profile
        self.assertEqual(patient_profile.hospital, self.hospital)
        self.assertEqual(patient_profile.joining_date, date(2026, 6, 14))

    def test_joining_date_edit_bug_fix_and_exact_persistence(self):
        """
        Regression test: Verify changing joining date to '2026-06-14' persists exactly
        as date(2026, 6, 14) in database, without timezone shift to 2026-06-13 or 2026-06-15.
        """
        self.client.force_login(self.clinic_admin)
        patient = self.client_user

        # Initial profile
        patient.profile.joining_date = date(2025, 1, 1)
        patient.profile.save()
        patient.patient_profile.joining_date = date(2025, 1, 1)
        patient.patient_profile.save()

        # Update joining date to 2026-06-14 via edit view
        post_data = {
            "first_name": "Rajesh",
            "last_name": "Kumar",
            "email": patient.email,
            "phone_number": "9409510501",
            "gender": "Male",
            "date_of_birth": "1988-11-20",
            "joining_date": "2026-06-14",
            "blood_group": "O+",
            "emergency_contact": "9409510501",
            "address": "Satellite, Ahmedabad",
            "medical_notes": "Postural correction and manual therapy",
        }
        res = self.client.post(f"/admin-patients/edit/{patient.id}/", post_data)
        self.assertEqual(res.status_code, 302)

        # Refresh from database
        patient.profile.refresh_from_db()
        patient.patient_profile.refresh_from_db()

        # Exact date check - regression verification
        self.assertEqual(patient.profile.joining_date, date(2026, 6, 14))
        self.assertEqual(patient.patient_profile.joining_date, date(2026, 6, 14))
        self.assertEqual(patient.profile.date_of_birth, date(1988, 11, 20))

    def test_clear_optional_joining_date(self):
        """Verify explicitly clearing joining date is safely handled."""
        self.client.force_login(self.clinic_admin)
        patient = self.client_user

        post_data = {
            "first_name": "Rajesh",
            "last_name": "Kumar",
            "email": patient.email,
            "phone_number": "9409510501",
            "joining_date": "",  # Empty
        }
        res = self.client.post(f"/admin-patients/edit/{patient.id}/", post_data)
        self.assertEqual(res.status_code, 302)

        patient.profile.refresh_from_db()
        patient.patient_profile.refresh_from_db()
        self.assertIsNone(patient.profile.joining_date)
        self.assertIsNone(patient.patient_profile.joining_date)

    def test_patient_deactivation_and_reactivation(self):
        """Admin can deactivate (soft-delete) and reactivate patient."""
        self.client.force_login(self.clinic_admin)
        patient = self.client_user
        self.assertTrue(patient.is_active)

        # Deactivate
        res_del = self.client.post(f"/admin-patients/delete/{patient.id}/")
        self.assertEqual(res_del.status_code, 302)
        patient.refresh_from_db()
        self.assertFalse(patient.is_active)

        # Reactivate
        res_act = self.client.get(f"/admin-patients/reactivate/{patient.id}/")
        self.assertEqual(res_act.status_code, 302)
        patient.refresh_from_db()
        self.assertTrue(patient.is_active)

    def test_edit_staff_joining_date_and_address(self):
        """Verify staff profile edit persists joining_date, address, and salary."""
        self.client.force_login(self.clinic_admin)
        staff_user = self.create_staff(self.hospital, username="assistant_pt")
        staff_prof = staff_user.staff_profile

        post_data = {
            "first_name": "Kavita",
            "last_name": "Mehta",
            "email": "kavita@clinic.com",
            "phone": "9409510501",
            "role": "physiotherapist",
            "shift": "morning",
            "base_salary": "40000",
            "address": "Drive-In Road, Ahmedabad",
            "joining_date": "2026-06-14",
        }
        res = self.client.post(f"/admin-staff/edit/{staff_prof.id}/", post_data)
        self.assertEqual(res.status_code, 302)

        staff_prof.refresh_from_db()
        self.assertEqual(staff_prof.joining_date, date(2026, 6, 14))
        self.assertEqual(staff_prof.address, "Drive-In Road, Ahmedabad")
        self.assertEqual(int(staff_prof.salary), 40000)

    def test_patient_crud_rbac_and_cross_tenant_isolation(self):
        """Verify client cannot access admin CRUD and Admin B cannot edit Admin A's patient."""
        # 1. Client attempts admin patient access -> redirected
        self.client.force_login(self.client_user)
        res_client = self.client.get("/admin-patients/")
        self.assertEqual(res_client.status_code, 302)
        self.assertIn("client-dashboard", res_client.url)

        res_client_add = self.client.get("/admin-patients/add/")
        self.assertEqual(res_client_add.status_code, 302)

        # 2. Cross-tenant isolation: Other clinic admin attempts to edit hospital A's patient
        self.client.force_login(self.other_admin)
        res_idor = self.client.get(f"/admin-patients/edit/{self.client_user.id}/")
        # Should be blocked and redirected with error
        self.assertEqual(res_idor.status_code, 302)
        self.assertIn("admin-patients", res_idor.url)
