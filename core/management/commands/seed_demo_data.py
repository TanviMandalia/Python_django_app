from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import time as dtime, timedelta
from core.models import (
    Hospital, SubscriptionPlan, HospitalSubscription, ClinicSettings,
    StaffProfile, Profile, Appointment, Attendance, DailyTask,
    LeaveApplication, SessionNote, Review, ClinicPromo, Blog, PaymentRecord
)


class Command(BaseCommand):
    help = "Seeds demo data for PhysioRehab clinic with accounts for all 4 roles + Super Admin"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(">>> Starting database demo seed..."))

        # 1. Hospital & Clinic Settings
        hospital, _ = Hospital.objects.get_or_create(
            name="Dr. Dhvani Patalia PhysioRehab",
            defaults={
                "slug": "dr-dhvani-patalia-physiorehab",
                "city": "Jamnagar",
                "address": "Bedi Gate, Jamnagar, Gujarat - 361001",
                "phone": "+91 94095 10501",
                "email": "contact@physiorehab.com",
                "is_active": True,
            }
        )

        clinic_settings, _ = ClinicSettings.objects.get_or_create(
            clinic_name="Dr. Dhvani Patalia — PhysioRehab",
            defaults={
                "tagline": "Advanced Physiotherapy, Sports Rehabilitation & Pain Relief Care",
                "phone": "+91 94095 10501",
                "email": "contact@physiorehab.com",
                "address": "Bedi Gate, Jamnagar, Gujarat",
                "appointment_fee": 500.00,
                "followup_fee": 300.00,
                "session_duration": 45,
                "opening_time": dtime(10, 0),
                "closing_time": dtime(20, 0),
                "enable_chat": True,
                "enable_payments": True,
                "enable_otp_reset": True,
            }
        )

        # 2. Subscription Plans & Hospital Subscription
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="premium",
            defaults={
                "price_monthly": 1999.00,
                "max_staff": 15,
                "max_patients": 2000,
                "features": "All 4 Dashboards, Razorpay Payments, Multi-shift Attendance, Reports, Chat",
                "is_active": True
            }
        )
        HospitalSubscription.objects.get_or_create(
            hospital=hospital,
            defaults={
                "plan": plan,
                "status": "active",
                "started_at": timezone.now().date(),
                "expires_at": timezone.now().date() + timedelta(days=365),
            }
        )

        # 3. Create Role Accounts
        # Super Admin
        super_admin, _ = User.objects.get_or_create(
            username="superadmin",
            defaults={"email": "superadmin@physiorehab.com", "first_name": "Platform", "last_name": "Admin", "is_superuser": True, "is_staff": True}
        )
        super_admin.set_password("superadmin123")
        super_admin.save()
        prof_super, _ = Profile.objects.get_or_create(user=super_admin)
        prof_super.is_platform_admin = True
        prof_super.save()

        # Clinic Admin
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@physiorehab.com", "first_name": "Clinic", "last_name": "Administrator", "is_superuser": True, "is_staff": True}
        )
        admin_user.set_password("admin123")
        admin_user.save()
        prof_admin, _ = Profile.objects.get_or_create(user=admin_user)
        prof_admin.phone_number = "+91 94095 10501"
        prof_admin.save()

        # Doctor / Physiotherapist
        doctor_user, _ = User.objects.get_or_create(
            username="doctor_dhvani",
            defaults={"email": "doctor@physiorehab.com", "first_name": "Dhvani", "last_name": "Patalia", "is_staff": True}
        )
        doctor_user.set_password("doctor123")
        doctor_user.save()
        StaffProfile.objects.get_or_create(
            user=doctor_user,
            defaults={"hospital": hospital, "role": "physiotherapist", "phone": "+91 94095 10501", "salary": 75000.00, "is_active": True}
        )

        # Staff / Employee (Receptionist / Assistant)
        staff_user, _ = User.objects.get_or_create(
            username="staff_rahul",
            defaults={"email": "staff@physiorehab.com", "first_name": "Rahul", "last_name": "Sharma", "is_staff": True}
        )
        staff_user.set_password("staff123")
        staff_user.save()
        StaffProfile.objects.get_or_create(
            user=staff_user,
            defaults={"hospital": hospital, "role": "receptionist", "phone": "+91 98765 43210", "salary": 25000.00, "is_active": True}
        )

        # Client / Patient
        patient_user, _ = User.objects.get_or_create(
            username="patient_priya",
            defaults={"email": "patient@physiorehab.com", "first_name": "Priya", "last_name": "Patel"}
        )
        patient_user.set_password("client123")
        patient_user.save()
        prof_patient, _ = Profile.objects.get_or_create(user=patient_user)
        prof_patient.phone_number = "+91 91234 56789"
        prof_patient.blood_group = "B+"
        prof_patient.gender = "Female"
        prof_patient.address = "102, Green Park Avenue, Jamnagar"
        prof_patient.save()

        # 4. Sample Appointments
        today = timezone.now().date()
        Appointment.objects.get_or_create(
            name="Priya Patel",
            email="patient@physiorehab.com",
            phone="+91 91234 56789",
            date=today,
            time="10:00",
            defaults={
                "hospital": hospital,
                "patient": patient_user,
                "service": "orthopedic",
                "status": "confirmed",
                "consultation_fee": 500.00,
                "notes": "Lower back pain, lumbar strain."
            }
        )
        Appointment.objects.get_or_create(
            name="Amit Verma",
            email="amit@example.com",
            phone="+91 98111 22334",
            date=today,
            time="11:30",
            defaults={
                "hospital": hospital,
                "service": "sports",
                "status": "pending",
                "consultation_fee": 500.00,
                "notes": "Right ankle ligament sprain during cricket match."
            }
        )

        # 5. Sample Attendance for Staff
        Attendance.objects.get_or_create(
            staff=staff_user,
            date=today,
            defaults={
                "clock_in": dtime(10, 2),
                "morning_clock_out": dtime(13, 0),
                "morning_hours": 2.97,
                "evening_clock_in": dtime(16, 0),
                "clock_out": dtime(20, 0),
                "evening_hours": 4.00,
                "total_hours": 6.97
            }
        )

        # 6. Sample Daily Tasks
        DailyTask.objects.get_or_create(
            title="Sanitize IFT and Ultrasound therapy machines",
            assigned_to=staff_user,
            assigned_by=admin_user,
            defaults={
                "description": "Daily sterilization routine of treatment room electrotherapy probes.",
                "priority": "high",
                "status": "in_progress",
                "due_date": today
            }
        )

        # 7. Sample Clinical Session Note
        SessionNote.objects.get_or_create(
            patient=patient_user,
            staff=doctor_user,
            date=today,
            defaults={
                "diagnosis": "L4-L5 Lumbar Disc Bulge with Sciatica pain radiating to right leg.",
                "treatment": "Lumbar intermittent traction 15 mins, IFT 10 mins, Core activation and pelvic tilts.",
                "next_session": "Follow-up session in 2 days for McKenzie extension exercises."
            }
        )

        # 8. Sample Reviews & Promos & Blogs
        Review.objects.get_or_create(
            reviewer_name="Priya Patel",
            defaults={
                "hospital": hospital,
                "patient": patient_user,
                "reviewer_title": "Verified Patient",
                "rating": 5,
                "message": "Dr. Dhvani is exceptionally skilled. Within 5 sessions my chronic back stiffness was reduced by 80%!",
                "is_approved": True,
            }
        )

        ClinicPromo.objects.get_or_create(
            title="Free Posture & Spine Alignment Checkup",
            defaults={
                "message": "Get a complimentary spine posture evaluation with every initial consultation this month.",
                "is_active": True,
                "start_date": today,
                "end_date": today + timedelta(days=30),
            }
        )

        Blog.objects.get_or_create(
            title="5 Simple Stretches to Relieve Desk Job Lower Back Pain",
            defaults={
                "slug": "5-simple-stretches-lower-back-pain",
                "category": "Posture",
                "excerpt": "Combat prolonged sitting stiffness with these physical therapist-approved daily stretches.",
                "content": "Sedentary desk jobs place continuous stress on the lumbar spine. Incorporating cat-cow stretches, seated spinal twists, hamstring elongations, and pelvic bridges every 2 hours can dramatically reduce disc pressure and improve blood flow.",
            }
        )

        self.stdout.write(self.style.SUCCESS("[OK] Demo seed data generated successfully!"))
        self.stdout.write(self.style.SUCCESS("""
===================================================================
Default Test Logins:
  - Super Admin : username: superadmin     | password: superadmin123
  - Clinic Admin: username: admin          | password: admin123
  - Doctor (PT) : username: doctor_dhvani  | password: doctor123
  - Staff Member: username: staff_rahul    | password: staff123
  - Patient     : username: patient_priya  | password: client123
===================================================================
        """))

