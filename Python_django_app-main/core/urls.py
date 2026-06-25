# core/urls.py  (app urls)

from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ── Public Pages ──────────────────────────────────────────
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    path("blogs/", views.blog_list, name="blog_list"),
    path("blogs/<slug:slug>/", views.blog_detail, name="blog_detail"),
    # ── Auth ──────────────────────────────────────────────────
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # ── Profile ───────────────────────────────────────────────
    path("profile/", views.profile_view, name="profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    # ── Settings ──────────────────────────────────────────────
    path("admin-settings/", views.admin_settings, name="admin_settings"),
    # ── Password System ───────────────────────────────────────
    path("change-password/", views.change_password_request, name="change_password"),
    path("forgot-password/", views.request_otp, name="request_otp"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),
    # ── Notifications ─────────────────────────────────────────
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/read-all/", views.mark_all_read, name="mark_all_read"),
    path(
        "notifications/<int:notif_id>/read/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
    # ── Payments ──────────────────────────────────────────────
    path("payments/", views.payments, name="payments"),
    path("payments/razorpay-create-order/", views.razorpay_create_order, name="razorpay_create_order"),
    path("payments/razorpay-verify/", views.razorpay_verify_payment, name="razorpay_verify_payment"),
    path("payments/razorpay-webhook/", views.razorpay_webhook, name="razorpay_webhook"),
    path("payments/record-cash/", views.record_cash_payment, name="record_cash_payment"),
    path("payments/record-upi/", views.record_upi_payment, name="record_upi_payment"),
    path("payments/admin/", views.admin_payments, name="admin_payments"),
    path("payments/confirm/<int:payment_id>/", views.confirm_payment, name="confirm_payment"),
    path("payments/reject/<int:payment_id>/", views.reject_payment, name="reject_payment"),
    # ── Subscription ──────────────────────────────────────────
    path("subscription/", views.subscription_page, name="subscription_page"),
    # ── Promo Management ──────────────────────────────────────
    path("admin-promos/", views.admin_promos, name="admin_promos"),
    path("admin-promos/add/", views.admin_promo_add, name="admin_promo_add"),
    path(
        "admin-promos/delete/<int:promo_id>/",
        views.admin_promo_delete,
        name="admin_promo_delete",
    ),
    path("api/promos/dismiss/", views.dismiss_promo, name="dismiss_promo"),
    # ── Exercise Reminder ─────────────────────────────────────
    path(
        "send-exercise-reminder/<int:patient_id>/",
        views.send_exercise_reminder,
        name="send_exercise_reminder",
    ),
    # ── Client ────────────────────────────────────────────────
    path("client-dashboard/", views.client_dashboard, name="client_dashboard"),
    path("book/", views.book_appointment, name="book_appointment"),
    path("my-appointments/", views.my_appointments, name="my_appointments"),
    path("chat/", views.client_chat, name="client_chat"),
    # ── Admin ─────────────────────────────────────────────────
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-appointments/", views.admin_appointments, name="admin_appointments"),
    path(
        "update-appointment/<int:appt_id>/<str:status>/",
        views.update_appointment,
        name="update_appointment",
    ),
    path("admin-patients/", views.admin_patients, name="admin_patients"),
    path("admin-chat/", views.admin_chat, name="admin_chat"),
    path(
        "admin-chat/<int:patient_id>/",
        views.admin_chat_detail,
        name="admin_chat_detail",
    ),
    # ── Admin Blog ────────────────────────────────────────────
    path("admin-blog/", views.admin_blog_list, name="admin_blog_list"),
    path("admin-blog/add/", views.admin_blog_add, name="admin_blog_add"),
    path("admin-blog/edit/<int:id>/", views.admin_blog_edit, name="admin_blog_edit"),
    path(
        "admin-blog/delete/<int:id>/", views.admin_blog_delete, name="admin_blog_delete"
    ),
    # ── Messages ──────────────────────────────────────────────
    path(
        "delete-message/<int:message_id>/", views.delete_message, name="delete_message"
    ),
    # ── Typing Indicators ─────────────────────────────────────
    path("start-typing/", views.start_typing),
    path("stop-typing/", views.stop_typing),
    path("check-typing/<int:user_id>/", views.check_typing),
    # ── Admin Appointments CRUD ───────────────────────────────
    path("admin-appointments/add/", views.add_appointment, name="add_appointment"),
    path(
        "admin-appointments/edit/<int:appt_id>/",
        views.edit_appointment,
        name="edit_appointment",
    ),
    path(
        "admin-appointments/delete/<int:appt_id>/",
        views.delete_appointment,
        name="delete_appointment",
    ),
    # ── Admin Patients CRUD ───────────────────────────────────
    path("admin-patients/edit/<int:user_id>/", views.edit_patient, name="edit_patient"),
    path(
        "admin-patients/delete/<int:user_id>/",
        views.delete_patient,
        name="delete_patient",
    ),
    path(
        "admin-patients/reactivate/<int:user_id>/",
        views.reactivate_patient,
        name="reactivate_patient",
    ),
    # ── Export: Patients ──────────────────────────────────────
    path(
        "export/patients/excel/",
        views.export_patients_excel,
        name="export_patients_excel",
    ),
    path("export/patients/pdf/", views.export_patients_pdf, name="export_patients_pdf"),
    # ── Export: Appointments ──────────────────────────────────
    path(
        "export/appointments/excel/",
        views.export_appointments_excel,
        name="export_appointments_excel",
    ),
    path(
        "export/appointments/pdf/",
        views.export_appointments_pdf,
        name="export_appointments_pdf",
    ),
    # ── Export: Analytics Report ──────────────────────────────
    path(
        "export/analytics/pdf/", views.export_analytics_pdf, name="export_analytics_pdf"
    ),
    # ── Admin Staff Management ────────────────────────────────
    path("admin-staff/", views.admin_staff, name="admin_staff"),
    path("add-staff/", views.add_staff, name="add_staff"),
    path("admin-staff/edit/<int:staff_id>/", views.edit_staff, name="edit_staff"),
    path("admin-staff/delete/<int:staff_id>/", views.delete_staff, name="delete_staff"),
    # ── Admin Leaves CRUD ─────────────────────────────────────
    path("admin-leaves/", views.admin_leaves, name="admin_leaves"),
    path(
        "update-leave/<int:leave_id>/<str:status>/",
        views.update_leave,
        name="update_leave",
    ),
    path(
        "admin-leaves/delete/<int:leave_id>/", views.delete_leave, name="delete_leave"
    ),
    # ── Admin Attendance CRUD ─────────────────────────────────
    path("admin-attendance/", views.admin_attendance, name="admin_attendance"),
    path("admin-attendance/add/", views.add_attendance, name="add_attendance"),
    path(
        "admin-attendance/edit/<int:att_id>/",
        views.edit_attendance,
        name="edit_attendance",
    ),
    path(
        "admin-attendance/delete/<int:att_id>/",
        views.delete_attendance,
        name="delete_attendance",
    ),
    # ── Admin Salary CRUD ─────────────────────────────────────
    path("admin-salary/", views.admin_salary, name="admin_salary"),
    path("admin-salary/edit/<int:record_id>/", views.edit_salary, name="edit_salary"),
    path(
        "admin-salary/delete/<int:record_id>/",
        views.delete_salary,
        name="delete_salary",
    ),
    # ── Admin Tasks CRUD ──────────────────────────────────────
    path("admin-tasks/", views.admin_tasks, name="admin_tasks"),
    path("add-task/", views.add_task, name="add_task"),
    path(
        "admin-tasks/edit/<int:task_id>/", views.edit_task_admin, name="edit_task_admin"
    ),
    path(
        "admin-tasks/delete/<int:task_id>/",
        views.delete_task_admin,
        name="delete_task_admin",
    ),
    # ── Admin Session Notes CRUD ──────────────────────────────
    path("admin-session-notes/", views.admin_session_notes, name="admin_session_notes"),
    path(
        "admin-session-notes/add/",
        views.admin_add_session_note,
        name="admin_add_session_note",
    ),
    path(
        "admin-session-notes/edit/<int:note_id>/",
        views.edit_session_note,
        name="edit_session_note",
    ),
    path(
        "admin-session-notes/delete/<int:note_id>/",
        views.delete_session_note,
        name="delete_session_note",
    ),
    # ── Staff ─────────────────────────────────────────────────
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff-attendance/", views.staff_attendance, name="staff_attendance"),
    path("staff-leave/", views.staff_leave, name="staff_leave"),
    path("staff-salary/", views.staff_salary, name="staff_salary"),
    path("staff-tasks/", views.staff_tasks, name="staff_tasks"),
    path(
        "update-task/<int:task_id>/<str:status>/", views.update_task, name="update_task"
    ),
    path("staff-session-notes/", views.staff_session_notes, name="staff_session_notes"),
    path("add-session-note/", views.add_session_note, name="add_session_note"),
    path("progress/", views.progress_tracking, name="progress_tracking"),
    path("analytics/", views.reports_analytics, name="reports_analytics"),
    # ── Reviews ───────────────────────────────────────────────
    path("submit-review/", views.submit_review, name="submit_review"),
    path("admin-reviews/", views.admin_reviews, name="admin_reviews"),
    path("admin-reviews/add/", views.admin_add_review, name="admin_add_review"),
    path(
        "admin-reviews/toggle/<int:review_id>/",
        views.toggle_review_approval,
        name="toggle_review_approval",
    ),
    path(
        "admin-reviews/delete/<int:review_id>/",
        views.admin_delete_review,
        name="admin_delete_review",
    ),
    # ── Support Ticket (clinic admin → platform) ──────────────
    path("support/submit/", views.submit_support_ticket, name="submit_support_ticket"),
    # ── Super Admin ───────────────────────────────────────────
    path("super-admin/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path(
        "super-admin/hospitals/",
        views.super_admin_hospitals,
        name="super_admin_hospitals",
    ),
    path(
        "super-admin/hospitals/add/",
        views.super_admin_add_hospital,
        name="super_admin_add_hospital",
    ),
    path(
        "super-admin/hospitals/edit/<int:hospital_id>/",
        views.super_admin_edit_hospital,
        name="super_admin_edit_hospital",
    ),
    path(
        "super-admin/hospitals/delete/<int:hospital_id>/",
        views.super_admin_delete_hospital,
        name="super_admin_delete_hospital",
    ),
    path(
        "super-admin/subscriptions/",
        views.super_admin_subscriptions,
        name="super_admin_subscriptions",
    ),
    path(
        "super-admin/subscriptions/confirm/<int:payment_id>/",
        views.super_admin_confirm_sub_payment,
        name="super_admin_confirm_sub_payment",
    ),
    path(
        "super-admin/subscriptions/reject/<int:payment_id>/",
        views.super_admin_reject_sub_payment,
        name="super_admin_reject_sub_payment",
    ),
    path(
        "super-admin/hospitals/<int:hospital_id>/payments/",
        views.super_admin_hospital_payments,
        name="super_admin_hospital_payments",
    ),
    path(
        "super-admin/analytics/",
        views.super_admin_analytics,
        name="super_admin_analytics",
    ),
    path("super-admin/all-payments/", views.super_admin_all_payments, name="super_admin_all_payments"),
    path("super-admin/all-payments/export/excel/", views.export_payments_excel, name="export_payments_excel"),
    path("super-admin/all-payments/export/pdf/", views.export_payments_pdf, name="export_payments_pdf"),
    path("super-admin/subscriptions/remind/<int:hospital_id>/", views.send_subscription_reminder, name="send_subscription_reminder"),
    path("super-admin/support/", views.super_admin_support, name="super_admin_support"),
    path(
        "super-admin/support/reply/<int:ticket_id>/",
        views.super_admin_support_reply,
        name="super_admin_support_reply",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
