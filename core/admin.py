from django.contrib import admin
from .models import (
    Hospital, SubscriptionPlan, HospitalSubscription, SupportTicket, SupportReply,
    Appointment, StaffProfile, Attendance, LeaveApplication, SalaryRecord,
    SessionNote, DailyTask, Message, UserActivity, Profile, PasswordResetOTP,
    Notification, ClinicSettings, ClinicAdmin, Blog, Review, PaymentRecord,
    ClinicSubscriptionPayment, ClinicPromo
)


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'phone', 'email', 'is_active', 'created_at')
    search_fields = ('name', 'city', 'email')
    list_filter = ('is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_monthly', 'max_staff', 'max_patients', 'is_active')
    list_filter = ('is_active',)


@admin.register(HospitalSubscription)
class HospitalSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('hospital', 'plan', 'status', 'started_at', 'expires_at')
    list_filter = ('status', 'started_at', 'expires_at')
    search_fields = ('hospital__name',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'service', 'date', 'time', 'status', 'consultation_fee', 'created_at')
    list_filter = ('status', 'service', 'date')
    search_fields = ('name', 'email', 'phone')
    ordering = ('-date', '-time')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'hospital', 'phone', 'salary', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'clock_in', 'morning_clock_out', 'evening_clock_in', 'clock_out', 'total_hours')
    list_filter = ('date',)
    search_fields = ('staff__username',)


@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ('staff', 'leave_type', 'from_date', 'to_date', 'status', 'applied_on')
    list_filter = ('status', 'leave_type')
    search_fields = ('staff__username',)


@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = ('staff', 'month', 'year', 'basic_salary', 'bonus', 'deduction', 'net_salary', 'is_paid')
    list_filter = ('year', 'month', 'is_paid')
    search_fields = ('staff__username',)


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ('patient', 'staff', 'date', 'diagnosis', 'created_at')
    list_filter = ('date',)
    search_fields = ('patient__username', 'staff__username', 'diagnosis')


@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'assigned_by', 'priority', 'status', 'due_date')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'assigned_to__username')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'gender', 'blood_group', 'is_platform_admin')
    search_fields = ('user__username', 'phone_number')
    list_filter = ('gender', 'is_platform_admin')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'message')


@admin.register(ClinicSettings)
class ClinicSettingsAdmin(admin.ModelAdmin):
    list_display = ('clinic_name', 'phone', 'email', 'appointment_fee', 'enable_chat', 'enable_payments')


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer_name', 'rating', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved')
    search_fields = ('reviewer_name', 'message')


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'amount', 'method', 'status', 'created_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('patient__username', 'transaction_id', 'razorpay_payment_id')


@admin.register(ClinicSubscriptionPayment)
class ClinicSubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('hospital', 'plan', 'amount', 'method', 'status', 'created_at')
    list_filter = ('method', 'status')
    search_fields = ('hospital__name', 'transaction_id')


@admin.register(ClinicPromo)
class ClinicPromoAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'hospital', 'submitted_by', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'message')