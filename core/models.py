from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import random
from django.utils.text import slugify


# DASHBOARD APPOINTMENT

morning_clock_out = models.TimeField(null=True, blank=True)
morning_hours     = models.DecimalField(max_digits=5, decimal_places=2, default=0)
evening_clock_in  = models.TimeField(null=True, blank=True)
evening_hours     = models.DecimalField(max_digits=5, decimal_places=2, default=0)

class Appointment(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    SERVICE_CHOICES = [
        ('orthopedic', 'Orthopedic Therapy'),
        ('neurological', 'Neurological Rehab'),
        ('sports', 'Sports Rehabilitation'),
        ('pediatric', 'Pediatric Therapy'),
        ('womens', "Women's Health"),
        ('home_visit', 'Home Visit'),
    ]

    TIME_CHOICES = [
        ('09:00', '9:00 AM'),
        ('10:00', '10:00 AM'),
        ('11:00', '11:00 AM'),
        ('12:00', '12:00 PM'),
        ('14:00', '2:00 PM'),
        ('15:00', '3:00 PM'),
        ('16:00', '4:00 PM'),
        ('17:00', '5:00 PM'),
    ]

    # Registered user (optional)
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='appointments',
        null=True,
        blank=True
    )

    # Public booking fields
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)

    service = models.CharField(
        max_length=50,
        choices=SERVICE_CHOICES
    )

    date = models.DateField()

    time = models.CharField(
        max_length=10,
        choices=TIME_CHOICES
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.name} - {self.service} - {self.date}"

    class Meta:
        ordering = ['-created_at']


class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('physiotherapist', 'Physiotherapist'),
        ('receptionist', 'Receptionist'),
        ('assistant', 'Assistant/Helper'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    joining_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"


class Attendance(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    lunch_start = models.TimeField(null=True, blank=True)
    lunch_end = models.TimeField(null=True, blank=True)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.staff.username} - {self.date}"

    class Meta:
        unique_together = ['staff', 'date']
        ordering = ['-date']


class LeaveApplication(models.Model):
    LEAVE_TYPES = [
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('emergency', 'Emergency Leave'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    applied_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.username} - {self.leave_type} - {self.status}"

    class Meta:
        ordering = ['-applied_on']


class SalaryRecord(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_records')
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
        ordering = ['-year', '-month']


class SessionNote(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_notes')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_notes')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    diagnosis = models.TextField()
    treatment = models.TextField()
    next_session = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.username} - {self.date}"

    class Meta:
        ordering = ['-created_at']


class DailyTask(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"

    class Meta:
        ordering = ['-created_at']

class Message(models.Model):

    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"

    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_READ, "Read"),
    ]

    sender = models.ForeignKey(
        User,
        related_name='sent_messages',
        on_delete=models.CASCADE
    )

    receiver = models.ForeignKey(
        User,
        related_name='received_messages',
        on_delete=models.CASCADE
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    is_read = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SENT
    )

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"

class UserActivity(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="activity"
    )

    last_seen = models.DateTimeField(default=timezone.now)

    is_typing = models.BooleanField(default=False)

    typing_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='typing_receivers'
    )

    def __str__(self):
        return self.user.username
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Account
    last_seen = models.DateTimeField(null=True, blank=True)

    # Personal Info
    phone_number = models.CharField(max_length=15, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('Other', 'Other')
        ],
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)

    # Medical Info
    blood_group = models.CharField(max_length=5, blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    medical_notes = models.TextField(blank=True)
    address = models.TextField(blank=True)

    # Profile Photo
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True
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
    recipient  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    link       = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification → {self.recipient.username}: {self.message[:40]}"
    

class ClinicSettings(models.Model):
    clinic_name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=300, blank=True)

    logo = models.ImageField(
        upload_to='clinic_logo/',
        blank=True,
        null=True
    )

    phone = models.CharField(max_length=20)
    email = models.EmailField()

    address = models.TextField()

    appointment_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500
    )

    followup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=300
    )

    session_duration = models.IntegerField(default=45)

    opening_time = models.TimeField()
    closing_time = models.TimeField()

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
    

class Blog(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='blogs/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
        
        
