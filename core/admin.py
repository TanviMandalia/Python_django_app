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

    