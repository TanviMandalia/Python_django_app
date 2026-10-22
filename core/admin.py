from django.contrib import admin
from .models import Blog, PublicAppointmentRequest

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'created_at')
    prepopulated_fields = {"slug": ("title",)}  # 🔥 auto fill in admin
    search_fields = ('title',)


@admin.register(PublicAppointmentRequest)
class PublicAppointmentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference_id',
        'patient_name',
        'phone',
        'email',
        'preferred_date',
        'preferred_time',
        'status',
        'email_notification_status',
        'created_at',
    )
    list_filter = ('status', 'email_notification_status', 'preferred_contact_method', 'preferred_date')
    search_fields = ('reference_id', 'patient_name', 'email', 'phone', 'service_or_reason')
    readonly_fields = ('reference_id', 'created_at', 'updated_at', 'ip_address', 'user_agent')
    ordering = ('-created_at',)
    actions = ('retry_failed_notifications',)

    @admin.action(description="Retry email notifications for selected appointment requests")
    def retry_failed_notifications(self, request, queryset):
        from .email_utils import send_public_appointment_request_notification
        success_count = 0
        fail_count = 0
        for req_obj in queryset:
            try:
                sent = send_public_appointment_request_notification(req_obj)
                if sent:
                    req_obj.email_notification_status = "sent"
                    req_obj.notification_error = ""
                    req_obj.save(update_fields=["email_notification_status", "notification_error"])
                    success_count += 1
                else:
                    req_obj.email_notification_status = "failed"
                    req_obj.notification_error = "Notification attempt returned failure"
                    req_obj.save(update_fields=["email_notification_status", "notification_error"])
                    fail_count += 1
            except Exception as exc:
                req_obj.email_notification_status = "failed"
                req_obj.notification_error = f"{exc.__class__.__name__}: {str(exc)[:200]}"
                req_obj.save(update_fields=["email_notification_status", "notification_error"])
                fail_count += 1

        self.message_user(
            request,
            f"Notification retry results: {success_count} sent successfully, {fail_count} failed."
        )

    