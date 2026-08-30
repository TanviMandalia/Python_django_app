from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class ExportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="export_admin", email="expadmin@test.com", password="pass", is_superuser=True, is_staff=True
        )
        self.client.login(username="export_admin", password="pass")

    def test_export_patients_excel(self):
        response = self.client.get(reverse("export_patients_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_export_patients_pdf(self):
        response = self.client.get(reverse("export_patients_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_export_appointments_excel(self):
        response = self.client.get(reverse("export_appointments_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

