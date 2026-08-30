from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Profile, PasswordResetOTP


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User"
        )
        self.profile = Profile.objects.get_or_create(user=self.user)[0]

    def test_login_success(self):
        response = self.client.post(reverse("login"), {
            "username": "testuser",
            "password": "testpassword123"
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("client_dashboard"))

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse("login"), {
            "username": "testuser",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username/email or password")

    def test_registration_flow(self):
        response = self.client.post(reverse("register"), {
            "username": "newpatient",
            "email": "newpatient@example.com",
            "first_name": "New",
            "last_name": "Patient",
            "phone_number": "+91 99999 88888",
            "password": "strongpassword123",
            "confirm_password": "strongpassword123"
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newpatient").exists())

    def test_logout(self):
        self.client.login(username="testuser", password="testpassword123")
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("home"))

    def test_otp_generation(self):
        response = self.client.post(reverse("request_otp"), {
            "email": "test@example.com"
        })
        self.assertEqual(response.status_code, 302)
        otp_record = PasswordResetOTP.objects.filter(user=self.user).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp), 6)

