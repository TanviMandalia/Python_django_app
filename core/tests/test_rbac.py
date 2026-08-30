from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import StaffProfile, Profile


class RBACTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Patient user
        self.patient = User.objects.create_user(
            username="patient_user", email="patient@test.com", password="pass123"
        )

        # Staff user (Receptionist)
        self.staff_member = User.objects.create_user(
            username="staff_user", email="staff@test.com", password="pass123", is_staff=True
        )
        StaffProfile.objects.create(user=self.staff_member, role="receptionist")

        # Doctor user (Physiotherapist)
        self.doctor = User.objects.create_user(
            username="doctor_user", email="doctor@test.com", password="pass123", is_staff=True
        )
        StaffProfile.objects.create(user=self.doctor, role="physiotherapist")

        # Admin user
        self.admin = User.objects.create_user(
            username="admin_user", email="admin@test.com", password="pass123", is_superuser=True, is_staff=True
        )

        # Super Admin
        self.super_admin = User.objects.create_user(
            username="super_user", email="super@test.com", password="pass123", is_superuser=True, is_staff=True
        )
        prof, _ = Profile.objects.get_or_create(user=self.super_admin)
        prof.is_platform_admin = True
        prof.save()

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/login/" in response.url)

    def test_patient_denied_admin_dashboard(self):
        self.client.login(username="patient_user", password="pass123")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("client_dashboard"))

    def test_staff_denied_admin_settings(self):
        self.client.login(username="staff_user", password="pass123")
        response = self.client.get(reverse("admin_settings"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("client_dashboard"))

    def test_admin_can_access_admin_dashboard(self):
        self.client.login(username="admin_user", password="pass123")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_doctor_can_access_clinical_progress(self):
        self.client.login(username="doctor_user", password="pass123")
        response = self.client.get(reverse("progress_tracking"))
        self.assertEqual(response.status_code, 200)

    def test_super_admin_can_access_super_admin_dashboard(self):
        self.client.login(username="super_user", password="pass123")
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 200)

