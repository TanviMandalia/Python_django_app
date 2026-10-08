"""
Base test case and test data factories for the Hospital Management System test suite.
Provides clean, isolated test fixtures for all four roles:
  1. Super Admin (Platform Administrator)
  2. Clinic Admin (Hospital/Clinic Administrator)
  3. Staff (Physiotherapist/Worker)
  4. Client (Patient)
"""
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone


from core.models import (
    Hospital,
    ClinicAdmin,
    StaffProfile,
    PatientProfile,
    Profile,
    SubscriptionPlan,
    HospitalSubscription,
    Appointment,
    Attendance,
    LeaveApplication,
    SalaryRecord,
    DailyTask,
    SessionNote,
    Review,
    PaymentRecord,
    Notification,
    ClinicSettings,
    ClinicPromo,
    SupportTicket,
    SupportReply,
)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BaseHospitalTestCase(TestCase):
    """Base test class providing standardized factories and test client helpers."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    # ── Factory Helpers ──────────────────────────────────────────

    def create_hospital(self, name="Apex Physio Clinic", email="contact@apexphysio.com", **kwargs):
        data = {
            "name": name,
            "email": email,
            "city": "Mumbai",
            "phone": "9876543210",
            "is_active": True,
        }
        data.update(kwargs)
        return Hospital.objects.create(**data)

    def create_super_admin(self, username="superadmin", email="superadmin@platform.com", password="SuperPassword123!"):
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.is_platform_admin = True
        profile.save()
        return user

    def create_clinic_admin(self, hospital, username="clinic_admin", email="admin@clinic.com", password="AdminPassword123!"):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name="Clinic",
            last_name="Admin",
            is_staff=True,
        )
        ClinicAdmin.objects.create(user=user, hospital=hospital)
        return user

    def create_staff(self, hospital, username="staff_member", email="staff@clinic.com", password="StaffPassword123!", role="physiotherapist", **kwargs):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=kwargs.get("first_name", "Staff"),
            last_name=kwargs.get("last_name", "Doctor"),
            is_staff=True,
        )
        StaffProfile.objects.create(
            user=user,
            hospital=hospital,
            role=role,
            phone=kwargs.get("phone", "9123456780"),
            salary=kwargs.get("salary", Decimal("45000.00")),
        )
        return user

    def create_patient(self, hospital=None, username="patient_jane", email="jane@example.com", password="PatientPassword123!", **kwargs):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=kwargs.get("first_name", "Jane"),
            last_name=kwargs.get("last_name", "Doe"),
        )
        if hospital:
            PatientProfile.objects.create(
                user=user,
                hospital=hospital,
                patient_status="active",
            )
        profile = getattr(user, "profile", None)
        if profile:
            profile.phone_number = kwargs.get("phone", "9876543210")
            profile.blood_group = kwargs.get("blood_group", "O+")
            profile.emergency_contact = kwargs.get("emergency_contact", "9876500000")
            profile.save()
        return user

    @staticmethod
    def get_next_weekday(days_ahead=1):
        d = timezone.now().date() + timedelta(days=days_ahead)
        while d.weekday() >= 5:  # Skip Saturday (5) and Sunday (6)
            d += timedelta(days=1)
        return d

    def create_appointment(self, hospital, patient, **kwargs):
        data = {
            "hospital": hospital,
            "patient": patient,
            "name": patient.get_full_name() or patient.username,
            "email": patient.email,
            "phone": "9876543210",
            "service": "orthopedic",
            "date": self.get_next_weekday(days_ahead=1),
            "time": "10:00",
            "status": "pending",
            "consultation_fee": Decimal("500.00"),
        }
        data.update(kwargs)
        return Appointment.objects.create(**data)

    def create_task(self, hospital, staff, **kwargs):
        assigned_by = kwargs.pop("assigned_by", None) or staff
        data = {
            "hospital": hospital,
            "assigned_to": staff,
            "assigned_by": assigned_by,
            "title": "Sanitize equipment",
            "description": "Clean electrotherapy devices",
            "priority": "high",
            "status": "pending",
            "due_date": timezone.now().date() + timedelta(days=1),
        }
        data.update(kwargs)
        return DailyTask.objects.create(**data)

    def create_leave(self, hospital, staff, **kwargs):
        data = {
            "hospital": hospital,
            "staff": staff,
            "leave_type": "sick",
            "from_date": timezone.now().date() + timedelta(days=5),
            "to_date": timezone.now().date() + timedelta(days=6),
            "reason": "Seasonal viral fever",
            "status": "pending",
        }
        data.update(kwargs)
        return LeaveApplication.objects.create(**data)

    def create_session_note(self, hospital, staff, patient, **kwargs):
        data = {
            "hospital": hospital,
            "staff": staff,
            "patient": patient,
            "diagnosis": "Lumbar strain and disc herniation L4-L5",
            "treatment": "Manual mobilization, ultrasound therapy and core stabilization",
            "next_session": "Follow up next Wednesday at 10 AM",
            "patient_visible": kwargs.get("patient_visible", True),
        }
        data.update(kwargs)
        return SessionNote.objects.create(**data)

    def create_payment(self, hospital, patient, **kwargs):
        data = {
            "hospital": hospital,
            "patient": patient,
            "amount": Decimal("500.00"),
            "method": "upi",
            "status": "pending",
            "transaction_id": "UPI123456789012",
        }
        data.update(kwargs)
        return PaymentRecord.objects.create(**data)

    def create_subscription(self, hospital, plan_name="standard", status="active"):
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name=plan_name,
            defaults={"price_monthly": Decimal("2999.00"), "max_staff": 10, "max_patients": 1000},
        )
        return HospitalSubscription.objects.create(
            hospital=hospital,
            plan=plan,
            status=status,
            started_at=timezone.now().date() - timedelta(days=10),
            expires_at=timezone.now().date() + timedelta(days=20),
        )

    # ── Authentication Helper ────────────────────────────────────

    def login_user(self, user, password="Password123!"):
        """Log in a user via the test client."""
        return self.client.login(username=user.username, password=password)
