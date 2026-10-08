"""
Management command: seed_users
Creates a default hospital (if missing) and inserts the 4 demo accounts with
correct roles, UserRole, and supplementary profiles.

Usage:
    uv run python manage.py seed_users --settings=myproject.settings.dev
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.models import (
    Hospital,
    Role,
    UserRole,
    Profile,
    ClinicAdmin,
    StaffProfile,
    PatientProfile,
)


import os

USERS = [
    {
        "username":     "super_admin_core",
        "env_var":      "SEED_SUPERADMIN_PASSWORD",
        "first_name":   "Super",
        "last_name":    "Admin",
        "email":        "super_admin@physiorehab.com",
        "is_superuser": True,
        "is_staff":     True,
        "role_code":    "platform_admin",
        "use_hospital": False,
    },
    {
        "username":     "clinic_admin_main",
        "env_var":      "SEED_CLINICADMIN_PASSWORD",
        "first_name":   "Clinic",
        "last_name":    "Admin",
        "email":        "clinic_admin@physiorehab.com",
        "is_superuser": False,
        "is_staff":     True,
        "role_code":    "clinic_admin",
        "use_hospital": True,
    },
    {
        "username":     "physio_staff_pro",
        "env_var":      "SEED_STAFF_PASSWORD",
        "first_name":   "Physio",
        "last_name":    "Staff",
        "email":        "physio_staff@physiorehab.com",
        "is_superuser": False,
        "is_staff":     False,
        "role_code":    "staff",
        "use_hospital": True,
    },
    {
        "username":     "patient_user_primary",
        "env_var":      "SEED_PATIENT_PASSWORD",
        "first_name":   "Patient",
        "last_name":    "Account",
        "email":        "patient_user@physiorehab.com",
        "is_superuser": False,
        "is_staff":     False,
        "role_code":    "patient",
        "use_hospital": True,
    },
]


class Command(BaseCommand):
    help = "Seed demo users with roles and profiles into the database."

    def handle(self, *args, **options):
        # ── 1. Ensure a default hospital exists ─────────────────────────────
        hospital, h_created = Hospital.objects.get_or_create(
            slug="physiorehab-clinic",
            defaults={
                "name":      "PhysioRehab Clinic",
                "email":     "admin@physiorehab.com",
                "phone":     "9999999999",
                "city":      "Mumbai",
                "is_active": True,
            },
        )
        label = "Created" if h_created else "Found"
        self.stdout.write(f"{label} hospital: {hospital.name} (id={hospital.pk})")

        # ── 2. Load role objects ─────────────────────────────────────────────
        roles = {r.code: r for r in Role.objects.all()}
        if not roles:
            self.stderr.write("No Role rows found — run migrations first.")
            return

        # ── 3. Create / update each user ────────────────────────────────────
        for u_data in USERS:
            username  = u_data["username"]
            role_code = u_data["role_code"]
            hosp      = hospital if u_data["use_hospital"] else None

            # Django User
            user, u_created = User.objects.get_or_create(username=username)
            env_pwd = os.getenv(u_data["env_var"])
            if env_pwd:
                user.set_password(env_pwd)
                pwd_status = f"password configured via {u_data['env_var']}"
            elif u_created:
                user.set_unusable_password()
                pwd_status = f"unusable password set (set {u_data['env_var']} to configure)"
            else:
                pwd_status = "existing password preserved"

            user.first_name   = u_data["first_name"]
            user.last_name    = u_data["last_name"]
            user.email        = u_data["email"]
            user.is_superuser = u_data["is_superuser"]
            user.is_staff     = u_data["is_staff"]
            user.save()
            action = "Created" if u_created else "Updated"
            self.stdout.write(f"  {action} user: {username} ({pwd_status})")

            # UserRole
            role_obj = roles[role_code]
            user_role, _ = UserRole.objects.get_or_create(
                user=user,
                defaults={"role": role_obj, "hospital": hosp},
            )
            user_role.role     = role_obj
            user_role.hospital = hosp
            user_role.save()
            self.stdout.write(f"    -> role={role_code}  hospital={hosp}")

            # Base Profile (auto-created by signal, but ensure it exists)
            Profile.objects.get_or_create(user=user)

            # Role-specific extras
            if role_code == "platform_admin":
                Profile.objects.filter(user=user).update(is_platform_admin=True)

            elif role_code == "clinic_admin":
                ClinicAdmin.objects.get_or_create(
                    user=user,
                    defaults={"hospital": hosp},
                )

            elif role_code == "staff":
                StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "hospital":     hosp,
                        "role":         "physiotherapist",
                        "phone":        "",
                        "salary":       0,
                        "is_active":    True,
                    },
                )

            elif role_code == "patient":
                PatientProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "hospital":       hosp,
                        "patient_status": "active",
                    },
                )

        # ── 4. Summary ───────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\nAll users seeded successfully!"))
        self.stdout.write("-" * 55)
        self.stdout.write(f"  Hospital         : {hospital.name}")
        self.stdout.write(f"  super_admin_core     -> Platform Admin  (superuser=True)")
        self.stdout.write(f"  clinic_admin_main    -> Clinic Admin")
        self.stdout.write(f"  physio_staff_pro     -> Staff (Physiotherapist)")
        self.stdout.write(f"  patient_user_primary -> Patient")

