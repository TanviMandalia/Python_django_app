from datetime import time

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import random
from django.utils.text import slugify


# DASHBOARD APPOINTMENT
# (Attendance model itself is defined further below, with all shift fields
# properly declared inside the class — see class Attendance.)


class Hospital(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("trial", "Trial"),
        ("suspended", "Suspended"),
        ("expired", "Expired"),
        ("archived", "Archived"),
    ]
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=False, null=False)
    logo = models.ImageField(upload_to="hospital_logos/", null=True, blank=True)
    logo_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hospital_logos",
    )
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    suspension_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # payment_key_id and payment_key_secret intentionally removed (Razorpay removed).

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            counter = 1
            while Hospital.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


# ─── SAAS SUBSCRIPTION & FEATURE ENTITLEMENT ARCHITECTURE ──────


class FeatureCategory(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="fas fa-cubes")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Feature Categories"

    def __str__(self):
        return self.name


class Feature(models.Model):
    GLOBAL_STATUS_CHOICES = [
        ("available", "Available"),
        ("maintenance", "Maintenance"),
        ("disabled", "Disabled (Global Kill Switch)"),
    ]
    category = models.ForeignKey(
        FeatureCategory, on_delete=models.CASCADE, related_name="features"
    )
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_paid = models.BooleanField(default=False, help_text="True if considered a premium/paid feature")
    has_usage_limit = models.BooleanField(default=False)
    default_limit = models.IntegerField(default=0, help_text="0 means unlimited or not applicable")
    limit_unit = models.CharField(max_length=50, blank=True, help_text="e.g. records, per month, MB")
    global_status = models.CharField(
        max_length=20, choices=GLOBAL_STATUS_CHOICES, default="available"
    )
    maintenance_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("standard", "Standard"),
        ("professional", "Professional"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_annual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trial_days = models.PositiveIntegerField(default=14)
    max_staff = models.IntegerField(default=5, help_text="Maximum allowed staff accounts (0 = unlimited)")
    max_patients = models.IntegerField(default=500, help_text="Maximum allowed patient records (0 = unlimited)")
    max_appointments_monthly = models.IntegerField(default=100, help_text="Maximum appointments per month (0 = unlimited)")
    storage_mb = models.IntegerField(default=500, help_text="File & document storage in MB (0 = unlimited)")
    tier_level = models.PositiveIntegerField(default=1, help_text="1=Free, 2=Basic, 3=Professional, 4=Enterprise")
    features = models.TextField(blank=True, help_text="Legacy text summary of plan features")
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Visible on public pricing / signup pages")

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        if not self.display_name:
            self.display_name = self.name.title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.name.title()

    class Meta:
        ordering = ["tier_level", "price_monthly"]


class PlanFeature(models.Model):
    ACCESS_CHOICES = [
        ("full", "Full Access"),
        ("limited", "Limited Access"),
        ("read_only", "Read Only"),
        ("disabled", "Disabled"),
    ]
    LIMIT_PERIOD_CHOICES = [
        ("lifetime", "Lifetime / Absolute"),
        ("monthly", "Monthly Rolling"),
        ("annual", "Annual"),
    ]
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="plan_features"
    )
    feature = models.ForeignKey(
        Feature, on_delete=models.CASCADE, related_name="plan_features"
    )
    access_type = models.CharField(max_length=20, choices=ACCESS_CHOICES, default="full")
    usage_limit = models.IntegerField(default=0, help_text="0 means unlimited")
    limit_period = models.CharField(
        max_length=20, choices=LIMIT_PERIOD_CHOICES, default="lifetime"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "feature"], name="uniq_plan_feature"
            )
        ]
        ordering = ["feature__category__order", "feature__name"]

    def __str__(self):
        return f"{self.plan.name} → {self.feature.code}: {self.access_type}"


class HospitalSubscription(models.Model):
    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("grace_period", "Grace Period"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
    ]
    INTERVAL_CHOICES = [
        ("monthly", "Monthly"),
        ("annual", "Annual"),
    ]
    hospital = models.OneToOneField(
        "Hospital", on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    started_at = models.DateField(default=timezone.now)
    expires_at = models.DateField(null=True, blank=True)
    trial_ends_at = models.DateField(null=True, blank=True)
    grace_period_ends_at = models.DateField(null=True, blank=True)
    billing_interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default="monthly")
    auto_renew = models.BooleanField(default=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.localdate() > self.expires_at
        return False

    @property
    def is_trial_active(self):
        if self.status == "trial":
            if self.trial_ends_at:
                return timezone.now().date() <= self.trial_ends_at
            if self.expires_at:
                return timezone.now().date() <= self.expires_at
            return True
        return False

    @property
    def trial_days_left(self):
        if not self.is_trial_active:
            return 0
        end = self.trial_ends_at or self.expires_at
        if end:
            delta = (end - timezone.now().date()).days
            return max(0, delta)
        return 0

    @property
    def is_in_grace_period(self):
        if self.status == "grace_period" and self.grace_period_ends_at:
            return timezone.now().date() <= self.grace_period_ends_at
        return False

    def __str__(self):
        return f"{self.hospital.name} — {self.plan} [{self.status}]"


class ClinicFeatureOverride(models.Model):
    OVERRIDE_CHOICES = [
        ("grant", "Grant (Complimentary / Promo)"),
        ("disable", "Disable / Block"),
        ("custom_limit", "Custom Usage Limit"),
    ]
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="feature_overrides"
    )
    feature = models.ForeignKey(
        Feature, on_delete=models.CASCADE, related_name="clinic_overrides"
    )
    override_type = models.CharField(max_length=20, choices=OVERRIDE_CHOICES, default="grant")
    custom_limit = models.IntegerField(null=True, blank=True, help_text="Custom limit value when override_type is custom_limit")
    reason = models.CharField(max_length=255, blank=True)
    expires_at = models.DateField(null=True, blank=True, help_text="Optional expiration date for temporary promo access")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_feature_overrides"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hospital", "feature"], name="uniq_hospital_feature_override"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.hospital.name} → {self.feature.code} override: {self.override_type}"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.localdate() > self.expires_at
        return False


class SubscriptionHistory(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="subscription_history"
    )
    previous_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    new_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, blank=True)
    change_type = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="subscription_changes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.hospital.name}: {self.change_type} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.CASCADE,
        related_name="support_tickets",
        null=True,
        blank=True,
    )
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} [{self.status}]"


class SupportReply(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.CASCADE, null=True, blank=True,
        related_name="support_replies",
    )
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="replies"
    )
    replier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply on {self.ticket.subject}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    SERVICE_CHOICES = [
        ("orthopedic", "Orthopedic Therapy"),
        ("neurological", "Neurological Rehab"),
        ("sports", "Sports Rehabilitation"),
        ("pediatric", "Pediatric Therapy"),
        ("womens", "Women's Health"),
        ("home_visit", "Home Visit"),
    ]

    TIME_CHOICES = [
        # Canonical 24h codes
        ("10:00", "10:00 AM"),
        ("10:30", "10:30 AM"),
        ("11:00", "11:00 AM"),
        ("11:30", "11:30 AM"),
        ("12:00", "12:00 PM"),
        ("12:30", "12:30 PM"),
        ("16:00", "04:00 PM"),
        ("16:30", "04:30 PM"),
        ("17:00", "05:00 PM"),
        ("17:30", "05:30 PM"),
        ("18:00", "06:00 PM"),
        ("18:30", "06:30 PM"),
        ("19:00", "07:00 PM"),
        ("19:30", "07:30 PM"),
        # Canonical 12h display codes
        ("10:00 AM", "10:00 AM"),
        ("10:30 AM", "10:30 AM"),
        ("11:00 AM", "11:00 AM"),
        ("11:30 AM", "11:30 AM"),
        ("12:00 PM", "12:00 PM"),
        ("12:30 PM", "12:30 PM"),
        ("04:00 PM", "04:00 PM"),
        ("04:30 PM", "04:30 PM"),
        ("05:00 PM", "05:00 PM"),
        ("05:30 PM", "05:30 PM"),
        ("06:00 PM", "06:00 PM"),
        ("06:30 PM", "06:30 PM"),
        ("07:00 PM", "07:00 PM"),
        ("07:30 PM", "07:30 PM"),
        # Common variations
        ("04:00", "04:00 PM"),
        ("04:30", "04:30 PM"),
        ("05:00", "05:00 PM"),
        ("05:30", "05:30 PM"),
        ("06:00", "06:00 PM"),
        ("06:30", "06:30 PM"),
        ("07:00", "07:00 PM"),
        ("07:30", "07:30 PM"),
        ("4:00 PM", "04:00 PM"),
        ("4:30 PM", "04:30 PM"),
        ("5:00 PM", "05:00 PM"),
        ("5:30 PM", "05:30 PM"),
        ("6:00 PM", "06:00 PM"),
        ("6:30 PM", "06:30 PM"),
        ("7:00 PM", "07:00 PM"),
        ("7:30 PM", "07:30 PM"),
    ]

    # Clinic this appointment belongs to
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )

    # Registered user (optional)
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
        null=True,
        blank=True,
    )
    assigned_staff = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_appointments",
    )
    clinic_service = models.ForeignKey(
        "ClinicService", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="appointments",
    )

    # Public booking fields
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)

    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)

    date = models.DateField()

    time = models.CharField(max_length=10, choices=TIME_CHOICES)

    notes = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    consultation_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Consultation / treatment fee in ₹",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.service} - {self.date}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hospital", "patient", "date", "time"],
                condition=Q(status__in=["pending", "confirmed"]),
                name="uniq_active_appointment_patient_slot",
            ),
            models.UniqueConstraint(
                fields=["hospital", "date", "time"],
                condition=Q(status__in=["pending", "confirmed"]),
                name="uniq_active_appointment_hospital_slot",
            ),
        ]
        ordering = ["-created_at"]


class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ("physiotherapist", "Physiotherapist"),
        ("receptionist", "Receptionist"),
        ("assistant", "Assistant/Helper"),
    ]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="staff_profile"
    )
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    joining_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"


class Attendance(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="attendance_records",
    )
    staff = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField(default=timezone.now)

    # ── Morning shift ──
    clock_in = models.TimeField(null=True, blank=True)
    morning_clock_out = models.TimeField(null=True, blank=True)
    morning_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # ── Evening shift ──
    evening_clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    evening_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # ── Legacy/optional lunch break fields (kept for backward compatibility) ──
    lunch_start = models.TimeField(null=True, blank=True)
    lunch_end = models.TimeField(null=True, blank=True)

    total_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.staff.username} - {self.date}"

    class Meta:
        unique_together = ["staff", "date"]
        ordering = ["-date"]


class LeaveApplication(models.Model):
    LEAVE_TYPES = [
        ("sick", "Sick Leave"),
        ("casual", "Casual Leave"),
        ("emergency", "Emergency Leave"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="leave_applications",
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_leave_applications",
    )
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaves")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    applied_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.username} - {self.leave_type} - {self.status}"

    class Meta:
        ordering = ["-applied_on"]


class SalaryRecord(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="salary_records",
    )
    staff = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="salary_records"
    )
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)
    paid_on = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.staff.username} - {self.month} {self.year}"

    class Meta:
        ordering = ["-year", "-month"]


class SessionNote(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="session_notes",
    )
    staff = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="session_notes"
    )
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="patient_notes"
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateField(default=timezone.now)
    diagnosis = models.TextField()
    treatment = models.TextField()
    next_session = models.TextField(blank=True)
    patient_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.username} - {self.date}"

    class Meta:
        ordering = ["-created_at"]


class DailyTask(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="daily_tasks",
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tasks"
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assigned_tasks"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"

    class Meta:
        ordering = ["-created_at"]


class Message(models.Model):
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"

    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_READ, "Read"),
    ]

    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User, related_name="sent_messages", on_delete=models.CASCADE
    )

    receiver = models.ForeignKey(
        User, related_name="received_messages", on_delete=models.CASCADE
    )

    content = models.TextField(blank=True)

    attachment = models.FileField(
        upload_to="chat_attachments/", null=True, blank=True
    )
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.PositiveIntegerField(null=True, blank=True)
    attachment_type = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_read = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["sender", "receiver", "created_at"]),
            models.Index(fields=["receiver", "is_read"]),
            models.Index(fields=["hospital", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Account
    last_seen = models.DateTimeField(null=True, blank=True)
    is_platform_admin = models.BooleanField(default=False)

    # Personal Info
    phone_number = models.CharField(max_length=15, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")],
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    joining_date = models.DateField(default=timezone.now, null=True, blank=True)

    # Medical Info
    blood_group = models.CharField(max_length=5, blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    medical_notes = models.TextField(blank=True)
    address = models.TextField(blank=True)

    # Profile Photo
    profile_photo = models.ImageField(
        upload_to="profile_photos/", blank=True, null=True
    )
    avatar_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="profile_avatars",
    )

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return (timezone.now() - self.created_at).seconds > 300  # 5 minutes


class Notification(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    link = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification → {self.recipient.username}: {self.message[:40]}"


class ClinicSettings(models.Model):
    hospital = models.OneToOneField(
        "Hospital", on_delete=models.CASCADE, null=True, blank=True,
        related_name="settings",
    )
    clinic_name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=300, blank=True)

    logo = models.ImageField(upload_to="clinic_logo/", blank=True, null=True)
    logo_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="clinic_logos",
    )

    phone = models.CharField(max_length=20)
    email = models.EmailField()

    address = models.TextField()

    appointment_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500)

    followup_fee = models.DecimalField(max_digits=10, decimal_places=2, default=300)

    session_duration = models.IntegerField(default=45)

    opening_time = models.TimeField(default=time(9, 0))
    closing_time = models.TimeField(default=time(17, 0))

    instagram = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)

    enable_chat = models.BooleanField(default=True)
    enable_payments = models.BooleanField(default=False)
    enable_otp_reset = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.clinic_name


class ClinicAdmin(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="clinic_admin_profile"
    )
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.CASCADE, related_name="admins"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} → {self.hospital.name}"


class Blog(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Orthopaedic", "Orthopaedic"),
        ("Neurological", "Neurological"),
        ("Sports", "Sports Rehab"),
        ("Pediatric", "Pediatric"),
        ("Posture", "Posture & Spine"),
        ("Recovery", "Patient Recovery"),
    ]
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blogs",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    excerpt = models.TextField(
        blank=True, help_text="Short summary shown on listing page"
    )
    content = models.TextField()
    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, default="General"
    )
    image = models.ImageField(upload_to="blogs/", null=True, blank=True)
    cover_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="blog_covers",
    )
    before_image = models.ImageField(
        upload_to="blogs/before_after/", null=True, blank=True
    )
    before_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="blog_before_images",
    )
    after_image = models.ImageField(
        upload_to="blogs/before_after/", null=True, blank=True
    )
    after_asset = models.ForeignKey(
        "MediaAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="blog_after_images",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class TreatmentCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    icon_class = models.CharField(max_length=60, default="fas fa-stethoscope", blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Treatment Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Treatment(models.Model):
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treatments",
    )
    category = models.ForeignKey(
        TreatmentCategory,
        on_delete=models.CASCADE,
        related_name="treatments",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    short_description = models.CharField(max_length=350)
    full_description = models.TextField()
    symptoms = models.TextField(
        blank=True,
        help_text="Key symptoms treated, separated by commas or newlines",
    )
    techniques = models.TextField(
        blank=True,
        help_text="Therapy techniques applied, separated by commas or newlines",
    )
    duration = models.CharField(max_length=60, default="45 - 60 Mins", blank=True)
    icon_class = models.CharField(max_length=60, default="fas fa-user-md", blank=True)
    image = models.ImageField(upload_to="treatments/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # SEO Metadata
    seo_title = models.CharField(max_length=160, blank=True)
    seo_meta_description = models.CharField(max_length=320, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["is_active", "order"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.seo_title:
            self.seo_title = f"{self.name} in Jamnagar | Dr. Dhvani Patalia Physio Rehab"
        if not self.seo_meta_description and self.short_description:
            self.seo_meta_description = self.short_description[:300]
        super().save(*args, **kwargs)

    def get_symptoms_list(self):
        if not self.symptoms:
            return []
        return [s.strip() for s in self.symptoms.replace("\n", ",").split(",") if s.strip()]

    def get_techniques_list(self):
        if not self.techniques:
            return []
        return [t.strip() for t in self.techniques.replace("\n", ",").split(",") if t.strip()]


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    hospital = models.ForeignKey(
        "Hospital",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    patient = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews"
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    reviewer_name = models.CharField(max_length=100)
    reviewer_title = models.CharField(max_length=100, blank=True)
    reviewer_photo_url = models.URLField(max_length=500, blank=True, null=True)
    rating = models.PositiveIntegerField(choices=RATING_CHOICES, default=5)
    message = models.TextField()
    is_approved = models.BooleanField(default=False)
    source = models.CharField(max_length=50, default="Verified Patient", blank=True)
    external_review_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    relative_time = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=True)
    added_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_approved", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reviewer_name} — {self.rating}★"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.delete("public_homepage_approved_reviews_v1")
        cache.delete("google_reviews_summary_data")

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.delete("public_homepage_approved_reviews_v1")
        cache.delete("google_reviews_summary_data")


class PaymentRecord(models.Model):
    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("upi", "UPI / QR Code"),
        ("netbanking", "Net Banking"),
        ("online", "Online / Card"),
        ("wallet", "Wallet"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.PROTECT, null=True, blank=True,
        related_name="patient_payments",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_records",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    razorpay_order_id = models.CharField(max_length=200, blank=True)
    razorpay_payment_id = models.CharField(max_length=200, blank=True)
    razorpay_signature = models.CharField(max_length=400, blank=True)
    transaction_id = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_record_amount_positive"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.patient} — ₹{self.amount} via {self.method} [{self.status}]"


class ClinicSubscriptionPayment(models.Model):
    METHOD_CHOICES = [
        ("upi", "UPI / QR Code"),
        ("cash", "Cash"),
        ("netbanking", "Net Banking / NEFT"),
        ("online", "Online / Card"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("paid", "Paid / Active"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.CASCADE, related_name="subscription_payments"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="upi")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transaction_id = models.CharField(max_length=200, blank=True)
    duration_months = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.hospital.name} — {self.plan} — {self.status}"


class ClinicPromo(models.Model):
    hospital = models.ForeignKey(
        "Hospital", on_delete=models.CASCADE, null=True, blank=True,
        related_name="promos",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.end_date and today > self.end_date:
            return False
        return today >= self.start_date


class Role(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=80)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="role_assignment"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True,
        related_name="user_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.role_id and self.role.code == "platform_admin" and self.hospital_id:
            raise ValidationError("Platform administrators cannot belong to a clinic.")
        if self.role_id and self.role.code != "platform_admin" and not self.hospital_id:
            raise ValidationError("Clinic users must be associated with a clinic.")


class PatientProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="patient_profile"
    )
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True,
        related_name="patient_profiles",
    )
    patient_status = models.CharField(max_length=20, default="active")
    joining_date = models.DateField(default=timezone.now, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class MediaAsset(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True,
        related_name="media_assets",
    )
    cloudinary_public_id = models.CharField(max_length=255, unique=True)
    secure_url = models.URLField(max_length=1000)
    resource_type = models.CharField(max_length=30, default="image")
    file_format = models.CharField(max_length=20, blank=True)
    bytes = models.PositiveBigIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="uploaded_media_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)


class ClinicService(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=45)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hospital", "name"], name="uniq_clinic_service_name"
            )
        ]


class StaffAvailability(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="staff_availability"
    )
    staff = models.ForeignKey(
        StaffProfile, on_delete=models.CASCADE, related_name="availability"
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)


class TreatmentPlan(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="treatment_plans"
    )
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.PROTECT, related_name="treatment_plans"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_treatment_plans"
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Exercise(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="exercises"
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)


class PatientExerciseAssignment(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="exercise_assignments"
    )
    treatment_plan = models.ForeignKey(
        TreatmentPlan, on_delete=models.CASCADE, related_name="exercise_assignments"
    )
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.PROTECT, related_name="exercise_assignments"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="assignments"
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="exercise_assignments_created"
    )
    frequency = models.CharField(max_length=100, blank=True)
    sets = models.PositiveSmallIntegerField(null=True, blank=True)
    repetitions = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")


class ExerciseLog(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="exercise_logs"
    )
    assignment = models.ForeignKey(
        PatientExerciseAssignment, on_delete=models.CASCADE, related_name="logs"
    )
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.PROTECT, related_name="exercise_logs"
    )
    completed_at = models.DateTimeField(default=timezone.now)
    sets_completed = models.PositiveSmallIntegerField(null=True, blank=True)
    repetitions_completed = models.PositiveSmallIntegerField(null=True, blank=True)
    pain_level = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)


class PaymentEvent(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="payment_events"
    )
    provider = models.CharField(max_length=30, default="manual")
    provider_event_id = models.CharField(max_length=255, unique=True)
    payment_record = models.ForeignKey(
        PaymentRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_status = models.CharField(max_length=20, default="received")


class AuditEvent(models.Model):
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)


class EmailAccount(models.Model):
    SCOPE_CHOICES = [
        ("platform", "Platform-Wide"),
        ("hospital", "Clinic-Specific"),
        ("user", "Doctor / User-Specific"),
    ]
    ACCOUNT_TYPE_CHOICES = [
        ("PLATFORM", "Platform System Account"),
        ("CLINIC", "Clinic Account"),
        ("DOCTOR", "Doctor / Specialist Account"),
        ("SUPPORT", "Support & Helpdesk Account"),
        ("NOTIFICATION", "Patient Notification Account"),
        ("SYSTEM", "System Transactional Account"),
    ]
    PROVIDER_CHOICES = [
        ("smtp", "Custom SMTP Server"),
        ("gmail", "Google Workspace / Gmail SMTP"),
        ("office365", "Microsoft 365 / Outlook"),
        ("api", "Transactional Email API"),
    ]

    name = models.CharField(max_length=150, help_text="Human-readable label for this account")
    account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPE_CHOICES, default="CLINIC")
    scope_type = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="hospital")
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, null=True, blank=True, related_name="email_accounts"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="email_accounts"
    )

    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default="smtp")
    host = models.CharField(max_length=255, default="smtp.gmail.com")
    port = models.PositiveIntegerField(default=587)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)

    username = models.CharField(max_length=255, help_text="SMTP / Mailbox login username")
    encrypted_password = models.TextField(help_text="Encrypted credentials at rest (Fernet AES-128-CBC + HMAC)")

    from_email = models.EmailField(help_text="Authoritative From: address")
    from_name = models.CharField(max_length=150, blank=True, help_text="Authoritative From: display name")
    reply_to = models.EmailField(blank=True, help_text="Optional default Reply-To: address")

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default sender for this tenant scope")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()}) <{self.from_email}>"

    def set_password(self, raw_password):
        from .crypto import encrypt_credential
        clean_pwd = (raw_password or "").strip()
        # For Gmail / Workspace accounts (16-char App Passwords), safely strip display spaces
        if clean_pwd and (
            getattr(self, "provider", "") == "gmail"
            or "gmail.com" in (getattr(self, "host", "") or "").lower()
            or len(clean_pwd.replace(" ", "")) == 16
        ):
            clean_pwd = clean_pwd.replace(" ", "")
        self.encrypted_password = encrypt_credential(clean_pwd)

    def get_password(self):
        from .crypto import decrypt_credential
        pwd = decrypt_credential(self.encrypted_password) or ""
        clean_pwd = pwd.strip()
        if clean_pwd and (
            getattr(self, "provider", "") == "gmail"
            or "gmail.com" in (getattr(self, "host", "") or "").lower()
            or len(clean_pwd.replace(" ", "")) == 16
        ):
            clean_pwd = clean_pwd.replace(" ", "")
        return clean_pwd

    @property
    def has_password(self):
        return bool(self.encrypted_password and str(self.encrypted_password).strip())

    def get_connection(self, fail_silently=False, timeout=15, force_smtp=False):
        import os
        from django.conf import settings
        from django.core.mail import get_connection

        backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
        # In unit tests, honor locmem unless force_smtp is explicitly requested
        if not force_smtp and "locmem" in backend:
            return get_connection(backend=backend)

        # In environments with Resend configured as EMAIL_BACKEND (e.g. Render Free blocking outbound SMTP ports),
        # route delivery through Resend HTTPS REST API unless force_smtp is explicitly requested
        if not force_smtp and ("ResendEmailBackend" in backend or getattr(self, "provider", "") == "api"):
            return get_connection(backend="core.email_backend.ResendEmailBackend", fail_silently=fail_silently)

        # In development console backend, honor console unless force_smtp is explicitly requested
        if not force_smtp and "console" in backend:
            return get_connection(backend=backend, fail_silently=fail_silently)

        # Enforce encryption mutual exclusivity
        effective_tls = self.use_tls
        effective_ssl = self.use_ssl
        if self.port == 587:
            effective_tls = True
            effective_ssl = False
        elif self.port == 465:
            effective_ssl = True
            effective_tls = False
        elif effective_tls and effective_ssl:
            effective_ssl = False

        return get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.get_password(),
            use_tls=effective_tls,
            use_ssl=effective_ssl,
            timeout=timeout,
            fail_silently=fail_silently,
        )


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("accepted", "Accepted by Provider"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("bounced", "Bounced"),
        ("failed", "Failed"),
        ("retrying", "Retrying"),
    ]
    DIRECTION_CHOICES = [
        ("outgoing", "Outgoing"),
        ("incoming", "Incoming"),
    ]
    account = models.ForeignKey(
        EmailAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="email_logs",
    )
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, default="outgoing"
    )
    sender_email = models.CharField(max_length=254, blank=True)
    hospital = models.ForeignKey(
        Hospital, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="email_logs",
    )
    email_type = models.CharField(max_length=60, default="transactional")
    recipient_email = models.CharField(max_length=254)
    subject = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")
    error_category = models.CharField(max_length=100, blank=True)
    error_details = models.TextField(blank=True, help_text="Sanitized technical failure details")
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    thread_id = models.CharField(max_length=255, blank=True, db_index=True)
    is_otp = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["is_otp", "expires_at"]),
            models.Index(fields=["hospital", "status"]),
            models.Index(fields=["email_type", "sent_at"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.email_type} -> {self.recipient_email}"


class InboundEmail(models.Model):
    STATUS_CHOICES = [
        ("received", "Received"),
        ("processed", "Processed"),
        ("duplicate", "Duplicate"),
        ("rejected", "Rejected"),
        ("failed", "Failed"),
    ]
    hospital = models.ForeignKey(
        Hospital, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inbound_emails",
    )
    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    in_reply_to = models.CharField(max_length=255, blank=True, db_index=True)
    references = models.TextField(blank=True)
    thread_id = models.CharField(max_length=255, blank=True, db_index=True)
    sender = models.EmailField()
    recipient = models.EmailField()
    subject = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    raw_headers = models.JSONField(default=dict, blank=True)
    attachments_info = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="received")
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"[{self.status}] {self.sender} -> {self.recipient}: {self.subject[:30]}"


# ═════════════════════════════════════════════════════════════════════════════
# SECURE WEBSITE VISITOR ANALYTICS & LEAD MANAGEMENT (SUPER ADMIN EXCLUSIVE)
# ═════════════════════════════════════════════════════════════════════════════

class VisitorSession(models.Model):
    """
    Privacy-conscious anonymous session for marketing/public website analytics.
    Uses an ephemeral cryptographically random session token (no IP or invasive fingerprinting).
    """
    DEVICE_CHOICES = [
        ("desktop", "Desktop"),
        ("mobile", "Mobile"),
        ("tablet", "Tablet"),
        ("bot", "Bot / Crawler"),
        ("unknown", "Unknown"),
    ]
    REFERRER_CHOICES = [
        ("direct", "Direct"),
        ("search", "Organic Search"),
        ("social", "Social Media"),
        ("referral", "Referral Website"),
        ("campaign", "Marketing Campaign"),
        ("other", "Other"),
    ]

    session_key = models.CharField(max_length=64, unique=True, db_index=True)
    visitor_id = models.CharField(max_length=64, blank=True, db_index=True, help_text="Pseudonymous visitor identifier")
    ip_address = models.CharField(max_length=45, blank=True, db_index=True, help_text="Validated client IP address (IPv4/IPv6)")
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_activity = models.DateTimeField(default=timezone.now, db_index=True)
    device_category = models.CharField(max_length=20, choices=DEVICE_CHOICES, default="unknown", db_index=True)
    browser_family = models.CharField(max_length=50, blank=True)
    os_family = models.CharField(max_length=50, blank=True)
    referrer_category = models.CharField(max_length=20, choices=REFERRER_CHOICES, default="direct", db_index=True)
    referrer_domain = models.CharField(max_length=200, blank=True)
    referrer_url = models.CharField(max_length=500, blank=True, help_text="Sanitized referrer without sensitive query parameters")
    entry_page = models.CharField(max_length=200, default="/", db_index=True)
    exit_page = models.CharField(max_length=200, default="/")
    total_page_views = models.PositiveIntegerField(default=1)
    total_active_seconds = models.PositiveIntegerField(default=0, help_text="Estimated active engaged time (paused when tab hidden)")
    has_converted = models.BooleanField(default=False, db_index=True, help_text="True if visitor voluntarily submitted enquiry")
    consent_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")],
        default="pending",
        db_index=True,
    )
    consent_given = models.BooleanField(default=False, help_text="True if visitor accepted analytics tracking")
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    consent_policy_version = models.CharField(max_length=20, default="1.0", blank=True)

    class Meta:
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["started_at", "device_category"]),
            models.Index(fields=["started_at", "referrer_category"]),
            models.Index(fields=["started_at", "has_converted"]),
            models.Index(fields=["started_at", "consent_status"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["visitor_id"]),
        ]

    def __str__(self):
        ip_label = f" [{self.ip_address}]" if self.ip_address else ""
        return f"VisitorSession {self.session_key[:8]}{ip_label} ({self.device_category}, {self.total_page_views} views)"


class PageViewEvent(models.Model):
    """
    Individual public page views and section engagements.
    Aggregates active reading time without storing PII.
    """
    session = models.ForeignKey(VisitorSession, on_delete=models.CASCADE, related_name="page_views")
    path = models.CharField(max_length=200, db_index=True)
    page_title = models.CharField(max_length=200, blank=True)
    section_name = models.CharField(max_length=100, blank=True, help_text="Named section anchor/identifier e.g. #services, #contact")
    referrer = models.CharField(max_length=500, blank=True, help_text="Sanitized referring page URL")
    active_seconds = models.PositiveIntegerField(default=0, help_text="Active seconds on this specific page/section")
    view_count = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["path", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.path} ({self.active_seconds}s) - {self.timestamp:%Y-%m-%d %H:%M}"


class VisitorConsentRecord(models.Model):
    """
    Auditable consent decision trail (accepted, declined, withdrawn) for privacy compliance.
    Separate from analytics aggregation.
    """
    ACTION_CHOICES = [
        ("accepted", "Accepted Analytics"),
        ("declined", "Declined Analytics"),
        ("withdrawn", "Withdrawn Analytics"),
    ]
    session_key = models.CharField(max_length=64, db_index=True)
    visitor_id = models.CharField(max_length=64, blank=True, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    policy_version = models.CharField(max_length=20, default="1.0")
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["visitor_id", "timestamp"]),
        ]

    @property
    def decision(self):
        return self.action

    def __str__(self):
        return f"Consent {self.action} ({self.session_key[:8]}) at {self.timestamp:%Y-%m-%d %H:%M}"


class VisitorLead(models.Model):
    """
    Voluntarily submitted public marketing enquiries.
    Stored securely with follow-up tracking for Super Admin.
    """
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("closed", "Closed"),
        ("spam", "Spam / Discarded"),
    ]
    CATEGORY_CHOICES = [
        ("General Enquiry", "General Enquiry"),
        ("Book Appointment", "Book Appointment"),
        ("Service Information", "Service Information"),
        ("Home Visit Request", "Home Visit Request"),
        ("SaaS Partnership", "SaaS / Clinic Partnership"),
        ("Other", "Other"),
    ]

    session = models.ForeignKey(VisitorSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="General Enquiry", db_index=True)
    message = models.TextField()
    source_page = models.CharField(max_length=200, default="/contact/", blank=True)
    marketing_consent = models.BooleanField(default=False, help_text="Optional consent for marketing communications")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    admin_notes = models.TextField(blank=True, help_text="Super Admin follow-up notes")
    contacted_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Lead: {self.first_name} {self.last_name} <{self.email}> [{self.status}]"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class AnalyticsAuditLog(models.Model):
    """
    Security audit trail for Super Admin access to visitor records, lead details, settings, and exports.
    """
    ACTION_CHOICES = [
        ("view_overview", "Viewed Analytics Overview"),
        ("view_sessions", "Viewed Visitor Sessions"),
        ("view_leads", "Viewed Leads List"),
        ("view_lead_detail", "Viewed Lead Detail"),
        ("update_lead", "Updated Lead Status/Notes"),
        ("export_leads", "Exported Leads CSV"),
        ("update_settings", "Updated Privacy & Retention Settings"),
        ("purge_data", "Purged Expired Analytics Data"),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    details = models.TextField(blank=True)
    ip_address = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Audit {self.action} by {self.user} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class AnalyticsSetting(models.Model):
    """
    Configurable retention and privacy policies for the SaaS platform.
    Singleton pattern.
    """
    retention_days = models.PositiveIntegerField(default=90, help_text="Days to retain anonymous sessions and pageviews (default 90)")
    require_consent = models.BooleanField(default=True, help_text="Require explicit consent banner before recording analytics")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_settings(cls):
        setting, _ = cls.objects.get_or_create(id=1, defaults={"retention_days": 90, "require_consent": True})
        return setting

    def __str__(self):
        return f"AnalyticsSettings (Retention: {self.retention_days} days, Require Consent: {self.require_consent})"
