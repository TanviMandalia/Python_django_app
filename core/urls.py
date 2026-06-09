from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [

    # path("admin/", admin.site.urls),

    # Public Pages
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    path("blogs/", views.blog_list, name="blog_list"),
    path('blogs/<slug:slug>/', views.blog_detail, name='blog_detail'),
    

    # Auth
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # Profile
    path("profile/", views.profile_view, name="profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),

    # Settings 
    path( "admin-settings/", views.admin_settings, name="admin_settings"),

    # Password system
    path("change-password/", views.change_password_request, name="change_password"),
    path("forgot-password/", views.request_otp, name="request_otp"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),

    # Payment
    path("payments/", views.payments, name="payments"),

    # Client
    path("client-dashboard/", views.client_dashboard, name="client_dashboard"),
    path("book/", views.book_appointment, name="book_appointment"),
    path("my-appointments/", views.my_appointments, name="my_appointments"),
    path("chat/", views.client_chat, name="client_chat"),

    # Admin
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-appointments/", views.admin_appointments, name="admin_appointments"),
    path("update-appointment/<int:appt_id>/<str:status>/", views.update_appointment, name="update_appointment"),
    path("admin-patients/", views.admin_patients, name="admin_patients"),
    path("admin-chat/", views.admin_chat, name="admin_chat"),
    path("admin-chat/<int:patient_id>/", views.admin_chat_detail, name="admin_chat_detail"),
    path('admin-blog/', views.admin_blog_list, name='admin_blog_list'),
    path('admin-blog/add/', views.admin_blog_add, name='admin_blog_add'),
    path('admin-blog/edit/<int:id>/', views.admin_blog_edit, name='admin_blog_edit'),
    path('admin-blog/delete/<int:id>/', views.admin_blog_delete, name='admin_blog_delete'),

    # Messages
    path("delete-message/<int:message_id>/", views.delete_message, name="delete_message"),

    # Typing
    path("start-typing/", views.start_typing),
    path("stop-typing/", views.stop_typing),
    path("check-typing/<int:user_id>/", views.check_typing),

    # Staff
    path("admin-staff/", views.admin_staff, name="admin_staff"),
    path("add-staff/", views.add_staff, name="add_staff"),
    path("admin-leaves/", views.admin_leaves, name="admin_leaves"),
    path("update-leave/<int:leave_id>/<str:status>/", views.update_leave, name="update_leave"),
    path("admin-attendance/", views.admin_attendance, name="admin_attendance"),
    path("admin-salary/", views.admin_salary, name="admin_salary"),
    path("admin-tasks/", views.admin_tasks, name="admin_tasks"),
    path("add-task/", views.add_task, name="add_task"),
    path("admin-session-notes/", views.admin_session_notes, name="admin_session_notes"),

    # Staff
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff-attendance/", views.staff_attendance, name="staff_attendance"),
    path("staff-leave/", views.staff_leave, name="staff_leave"),
    path("staff-salary/", views.staff_salary, name="staff_salary"),
    path("staff-tasks/", views.staff_tasks, name="staff_tasks"),
    path("update-task/<int:task_id>/<str:status>/", views.update_task, name="update_task"),
    path("staff-session-notes/", views.staff_session_notes, name="staff_session_notes"),
    path("add-session-note/", views.add_session_note, name="add_session_note"),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )