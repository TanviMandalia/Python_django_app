"""
Centralised email utility for PhysioRehab Clinic.
All emails go through send_clinic_email() so formatting is consistent
and failures never crash the main flow (errors are logged).
"""

import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

CLINIC_NAME  = "PhysioRehab Clinic"
CLINIC_EMAIL = settings.EMAIL_HOST_USER
CLINIC_PHONE = "+91 98765 43210"


def send_clinic_email(subject, message_text, recipient_list, html_message=None):
    """
    Core email sender. Wraps send_mail with error handling.
    Returns True on success, False on failure.
    """
    try:
        send_mail(
            subject=f"[{CLINIC_NAME}] {subject}",
            message=message_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list if isinstance(recipient_list, list) else [recipient_list],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipient_list}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed to {recipient_list}: {e}")
        return False


# ─── APPOINTMENT EMAILS ──────────────────────────────────────

def send_appointment_confirmation(appointment):
    """Email sent to patient when they book an appointment."""
    subject = "Appointment Booked Successfully"
    body = f"""Dear {appointment.name},

Your appointment has been booked at {CLINIC_NAME}.

Details:
  Service  : {appointment.get_service_display_name()}
  Date     : {appointment.date.strftime('%d %B %Y')}
  Time     : {appointment.get_time_display_name()}
  Status   : Pending Confirmation

We will confirm your appointment shortly. For any queries, call us at {CLINIC_PHONE}.

Thank you for choosing {CLINIC_NAME}!
"""
    return send_clinic_email(subject, body, appointment.email)


def send_appointment_status_update(appointment):
    """Email sent to patient when admin updates appointment status."""
    status_map = {
        'confirmed': ('Appointment Confirmed ✅', 'confirmed'),
        'completed': ('Appointment Completed 🎉', 'completed'),
        'cancelled': ('Appointment Cancelled ❌', 'cancelled'),
    }
    label, _ = status_map.get(appointment.status, ('Appointment Update', appointment.status))

    body = f"""Dear {appointment.name},

Your appointment status has been updated.

Details:
  Service  : {appointment.get_service_display_name()}
  Date     : {appointment.date.strftime('%d %B %Y')}
  Time     : {appointment.get_time_display_name()}
  Status   : {appointment.status.upper()}

"""
    if appointment.status == 'confirmed':
        body += f"Please arrive 10 minutes before your scheduled time.\n"
    elif appointment.status == 'cancelled':
        body += f"If you'd like to reschedule, please contact us at {CLINIC_PHONE}.\n"

    body += f"\nFor queries, call: {CLINIC_PHONE}\n\n{CLINIC_NAME}"
    return send_clinic_email(label, body, appointment.email)


def send_admin_new_appointment_alert(appointment):
    """Alert admin when a new appointment is booked."""
    admin_email = CLINIC_EMAIL
    subject = f"New Appointment: {appointment.name} – {appointment.date}"
    body = f"""New appointment booked on the system.

Patient  : {appointment.name}
Phone    : {appointment.phone}
Email    : {appointment.email}
Service  : {appointment.get_service_display_name()}
Date     : {appointment.date.strftime('%d %B %Y')}
Time     : {appointment.get_time_display_name()}
Notes    : {appointment.notes or 'None'}

Login to the admin panel to confirm or manage this appointment.
"""
    return send_clinic_email(subject, body, admin_email)


# ─── OTP EMAILS ──────────────────────────────────────────────

def send_otp_email(email, otp, purpose="Password Reset"):
    """Send OTP for password reset / change."""
    subject = f"{purpose} OTP"
    body = f"""Your OTP for {purpose} at {CLINIC_NAME}:

    OTP Code : {otp}

This OTP is valid for 5 minutes. Do not share it with anyone.

If you did not request this, please ignore this email.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, email)


# ─── STAFF EMAILS ────────────────────────────────────────────

def send_leave_status_email(leave):
    """Email staff when leave is approved/rejected."""
    email = leave.staff.email
    if not email:
        return False

    status_word = leave.status.upper()
    subject = f"Leave Application {status_word}"
    body = f"""Dear {leave.staff.get_full_name()},

Your leave application has been {leave.status}.

Details:
  Type     : {leave.get_leave_type_display()}
  From     : {leave.from_date.strftime('%d %B %Y')}
  To       : {leave.to_date.strftime('%d %B %Y')}
  Status   : {status_word}
  Note     : {leave.admin_note or 'No note from admin'}

For queries, contact the admin.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, email)


def send_salary_paid_email(salary_record):
    """Email staff when salary is processed."""
    email = salary_record.staff.email
    if not email:
        return False

    subject = f"Salary Processed – {salary_record.month} {salary_record.year}"
    body = f"""Dear {salary_record.staff.get_full_name()},

Your salary for {salary_record.month} {salary_record.year} has been processed.

Breakdown:
  Basic Salary : ₹{salary_record.basic_salary}
  Bonus        : ₹{salary_record.bonus}
  Deduction    : ₹{salary_record.deduction}
  Net Salary   : ₹{salary_record.net_salary}
  Paid On      : {salary_record.paid_on.strftime('%d %B %Y') if salary_record.paid_on else 'N/A'}

Thank you for your service at {CLINIC_NAME}!
"""
    return send_clinic_email(subject, body, email)


def send_task_assigned_email(task):
    """Email staff when a new task is assigned to them."""
    email = task.assigned_to.email
    if not email:
        return False

    subject = f"New Task Assigned: {task.title}"
    body = f"""Dear {task.assigned_to.get_full_name()},

A new task has been assigned to you.

Task     : {task.title}
Priority : {task.priority.upper()}
Due Date : {task.due_date.strftime('%d %B %Y') if task.due_date else 'No deadline'}
Details  : {task.description or 'N/A'}

Login to your dashboard to update the task status.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, email)


def send_staff_welcome_email(user, password):
    """Email new staff their login credentials."""
    email = user.email
    if not email:
        return False

    subject = "Welcome to PhysioRehab Clinic – Staff Login Details"
    body = f"""Dear {user.get_full_name()},

Welcome to {CLINIC_NAME}! Your staff account has been created.

Login Details:
  Username : {user.username}
  Password : {password}
  Login URL: http://your-domain.com/login/

Please change your password after first login.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, email)