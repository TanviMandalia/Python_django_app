import io
import os
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from core.models import Role, UserRole, Hospital

User = get_user_model()


class PasswordRotationCommandTests(TestCase):

    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Rotation Test Hospital",
            slug="rotation-test-hosp",
            city="Mumbai",
            is_active=True,
        )
        self.superadmin_role, _ = Role.objects.get_or_create(code="platform_admin", defaults={"name": "Platform Admin"})
        self.clinicadmin_role, _ = Role.objects.get_or_create(code="clinic_admin", defaults={"name": "Clinic Admin"})
        self.staff_role, _ = Role.objects.get_or_create(code="staff", defaults={"name": "Staff"})
        self.patient_role, _ = Role.objects.get_or_create(code="patient", defaults={"name": "Patient"})

        self.users = {}
        for role_name, role_code, is_super, is_staff in [
            ("test_superadmin", "platform_admin", True, True),
            ("test_clinicadmin", "clinic_admin", False, True),
            ("test_staff", "staff", False, False),
            ("test_patient", "patient", False, False),
        ]:
            u = User.objects.create_user(
                username=role_name,
                email=f"{role_name}@example.com",
                password="InitialSafePassword#2026",
                is_superuser=is_super,
                is_staff=is_staff,
            )
            role_obj = Role.objects.get(code=role_code)
            UserRole.objects.create(
                user=u,
                role=role_obj,
                hospital=self.hospital if role_code != "platform_admin" else None,
            )
            self.users[role_name] = u

    def test_rotate_via_password_argument(self):
        target_user = self.users["test_superadmin"]
        out = io.StringIO()
        call_command(
            "rotate_role_password",
            username=target_user.username,
            password="BrandNewSecurePassword#2026_X",
            stdout=out,
        )
        self.assertIn(f"Successfully rotated password for user '{target_user.username}'", out.getvalue())
        target_user.refresh_from_db()
        self.assertTrue(target_user.check_password("BrandNewSecurePassword#2026_X"))
        self.assertFalse(target_user.check_password("InitialSafePassword#2026"))

    def test_rotate_via_env_var(self):
        target_user = self.users["test_clinicadmin"]
        with patch.dict(os.environ, {"SECURE_ROTATION_TEST_SECRET": "EnvProvidedSecretKey#998877_Valid"}):
            out = io.StringIO()
            call_command(
                "rotate_role_password",
                username=target_user.username,
                env_var="SECURE_ROTATION_TEST_SECRET",
                stdout=out,
            )
            self.assertIn(f"Successfully rotated password for user '{target_user.username}'", out.getvalue())
            target_user.refresh_from_db()
            self.assertTrue(target_user.check_password("EnvProvidedSecretKey#998877_Valid"))

    def test_rotate_via_stdin(self):
        target_user = self.users["test_staff"]
        fake_stdin = io.StringIO("PipedStdinSecretKey#2026_Secure\n")
        with patch("sys.stdin", fake_stdin):
            out = io.StringIO()
            call_command(
                "rotate_role_password",
                username=target_user.username,
                stdin=True,
                stdout=out,
            )
            self.assertIn(f"Successfully rotated password for user '{target_user.username}'", out.getvalue())
            target_user.refresh_from_db()
            self.assertTrue(target_user.check_password("PipedStdinSecretKey#2026_Secure"))

    def test_rotation_rejects_weak_password_when_validation_enabled(self):
        target_user = self.users["test_patient"]
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "rotate_role_password",
                username=target_user.username,
                password="short",  # fails minimum length 8 validator
            )
        self.assertIn("Password validation failed", str(ctx.exception))
        target_user.refresh_from_db()
        self.assertTrue(target_user.check_password("InitialSafePassword#2026"))

    def test_nonexistent_user_raises_command_error(self):
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "rotate_role_password",
                username="non_existent_user_xyz",
                password="SomePassword#12345",
            )
        self.assertIn("does not exist", str(ctx.exception))

    def test_role_preservation_after_rotation(self):
        """Verify user roles and relationships are untouched by password rotation."""
        clinic_user = self.users["test_clinicadmin"]
        call_command(
            "rotate_role_password",
            username=clinic_user.username,
            password="NewClinicAdminPassword#2026_Alpha",
        )
        clinic_user.refresh_from_db()
        user_roles = UserRole.objects.filter(user=clinic_user)
        self.assertEqual(user_roles.count(), 1)
        self.assertEqual(user_roles.first().role.code, "clinic_admin")
        self.assertEqual(user_roles.first().hospital, self.hospital)
