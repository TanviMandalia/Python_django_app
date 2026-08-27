"""
PhysioRehab Modular Views Package.
Exposes all view handlers for clean URL routing and backwards compatibility.
"""

from .public_views import (
    home, about, services, contact, blog_list, blog_detail
)

from .auth_views import (
    login_view, register_view, logout_view, profile_view, edit_profile,
    request_otp, verify_otp, resend_otp, reset_password, change_password_request
)

from .client_views import (
    client_dashboard, book_appointment, my_appointments, submit_review
)

from .doctor_views import (
    progress_tracking, reports_analytics, add_session_note,
    edit_session_note, delete_session_note, send_exercise_reminder
)

from .staff_views import (
    staff_dashboard, staff_attendance, staff_leave, staff_salary,
    staff_tasks, update_task, staff_session_notes
)

from .admin_views import (
    admin_dashboard, admin_appointments, update_appointment, add_appointment,
    edit_appointment, delete_appointment, admin_patients, edit_patient,
    delete_patient, reactivate_patient, admin_staff, add_staff, edit_staff,
    delete_staff, admin_leaves, update_leave, delete_leave, admin_attendance,
    add_attendance, edit_attendance, delete_attendance, admin_salary, edit_salary,
    delete_salary, admin_tasks, add_task, edit_task_admin, delete_task_admin,
    admin_settings, admin_promos, admin_promo_add, admin_promo_delete, dismiss_promo,
    admin_reviews, admin_add_review, toggle_review_approval, admin_delete_review,
    admin_blog_list, admin_blog_add, admin_blog_edit, admin_blog_delete,
    admin_session_notes, admin_add_session_note, submit_support_ticket
)

from .super_admin_views import (
    super_admin_dashboard, super_admin_hospitals, super_admin_add_hospital,
    super_admin_edit_hospital, super_admin_delete_hospital,
    super_admin_subscriptions, super_admin_confirm_sub_payment,
    super_admin_reject_sub_payment, super_admin_hospital_payments,
    super_admin_analytics, super_admin_all_payments, send_subscription_reminder,
    super_admin_support, super_admin_support_reply, subscription_page
)

from .payment_views import (
    payments, razorpay_create_order, razorpay_verify_payment, razorpay_webhook,
    record_cash_payment, record_upi_payment, admin_payments,
    confirm_payment, reject_payment
)

from .chat_views import (
    client_chat, admin_chat, admin_chat_detail, delete_message,
    start_typing, stop_typing, check_typing
)

from .notification_views import (
    notifications_view, mark_all_read, mark_notification_read
)

from .export_views import (
    export_patients_excel, export_patients_pdf,
    export_appointments_excel, export_appointments_pdf,
    export_analytics_pdf, export_payments_excel, export_payments_pdf
)

