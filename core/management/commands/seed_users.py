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


USERS = [
    {
        "username":     "super_admin2",
        "password":     "0X1-UwAGXiSM03nRbdc4bW_6",
        "first_name":   "Super",
        "last_name":    "Admin",
        "email":        "super_admin2@physiorehab.com",
        "is_superuser": True,
        "is_staff":     True,
        "role_code":    "platform_admin",
        "use_hospital": False,
    },
    {
        "username":     "clinic_admin2",
        "password":     "zyYFK1W!dblCfW0!968bOnjP",
        "first_name":   "Clinic",
        "last_name":    "Admin",
        "email":        "clinic_admin2@physiorehab.com",
        "is_superuser": False,
        "is_staff":     True,
        "role_code":    "clinic_admin",
        "use_hospital": True,
    },
    {
        "username":     "physio_staff2",
        "password":     "Leh2!6TdeYh5%IbrMWUUZeUM",
        "first_name":   "Physio",
        "last_name":    "Staff",
        "email":        "physio_staff2@physiorehab.com",
        "is_superuser": False,
        "is_staff":     False,
        "role_code":    "staff",
        "use_hospital": True,
    },
    {
        "username":     "patient_account2",
        "password":     "cT4g6mlXwf5DY66NVKysZvJ_",
        "first_name":   "Patient",
        "last_name":    "Account",
        "email":        "patient_account2@physiorehab.com",
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
            user.set_password(u_data["password"])
            user.first_name   = u_data["first_name"]
            user.last_name    = u_data["last_name"]
            user.email        = u_data["email"]
            user.is_superuser = u_data["is_superuser"]
            user.is_staff     = u_data["is_staff"]
            user.save()
            action = "Created" if u_created else "Updated"
            self.stdout.write(f"  {action} user: {username}")

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
        self.stdout.write(f"  super_admin2     -> Platform Admin  (superuser=True)")
        self.stdout.write(f"  clinic_admin2    -> Clinic Admin")
        self.stdout.write(f"  physio_staff2    -> Staff (Physiotherapist)")
        self.stdout.write(f"  patient_account2 -> Patient")
