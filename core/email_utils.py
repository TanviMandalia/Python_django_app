"""
Centralised email utility for PhysioRehab Clinic.
All emails go through send_clinic_email() so formatting is consistent
and failures never crash the main flow (errors are logged).
"""

import logging
from datetime import date as date_type
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

CLINIC_NAME  = "Dr. Dhvani Patalia — PhysioRehab"
CLINIC_EMAIL = settings.DEFAULT_FROM_EMAIL
CLINIC_PHONE = "+91 98765 43210"

SERVICE_NAMES = {
    'orthopedic':   'Orthopedic Therapy',
    'neurological': 'Neurological Rehab',
    'sports':       'Sports Rehabilitation',
    'pediatric':    'Pediatric Therapy',
    'womens':       "Women's Health",
    'home_visit':   'Home Visit',
}

TIME_NAMES = {
    '09:00': '9:00 AM',  '10:00': '10:00 AM',
    '11:00': '11:00 AM', '12:00': '12:00 PM',
    '14:00': '2:00 PM',  '15:00': '3:00 PM',
    '16:00': '4:00 PM',  '17:00': '5:00 PM',
}

def get_service_name(appt):
    return SERVICE_NAMES.get(appt.service, appt.service)

def get_time_name(appt):
    return TIME_NAMES.get(appt.time, appt.time)

def format_date(d):
    """Safely format a date whether it's a date object or string like '2026-06-12'."""
    if isinstance(d, str):
        try:
            from datetime import datetime
            d = datetime.strptime(d, '%Y-%m-%d').date()
        except Exception:
            return d  # return as-is if parsing fails
    return d.strftime('%d %B %Y')


def send_clinic_email(subject, message_text, recipient_list):
    try:
        send_mail(
            subject=f"[{CLINIC_NAME}] {subject}",
            message=message_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list if isinstance(recipient_list, list) else [recipient_list],
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipient_list}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed to {recipient_list}: {e}")
        return False


# ── APPOINTMENT EMAILS ───────────────────────────────────────

def send_appointment_confirmation(appointment):
    subject = "Appointment Booked Successfully"
    body = f"""Dear {appointment.name},

Your appointment has been booked at {CLINIC_NAME}.

Details:
  Service  : {get_service_name(appointment)}
  Date     : {format_date(appointment.date)}
  Time     : {get_time_name(appointment)}
  Status   : Pending Confirmation

We will confirm your appointment shortly.
For queries, call us at {CLINIC_PHONE}.

Thank you for choosing {CLINIC_NAME}!
"""
    return send_clinic_email(subject, body, appointment.email)


def send_appointment_status_update(appointment):
    status_titles = {
        'confirmed': 'Appointment Confirmed ✅',
        'completed': 'Appointment Completed 🎉',
        'cancelled': 'Appointment Cancelled ❌',
    }
    label = status_titles.get(appointment.status, 'Appointment Updated')
    body = f"""Dear {appointment.name},

Your appointment status has been updated.

Details:
  Service  : {get_service_name(appointment)}
  Date     : {format_date(appointment.date)}
  Time     : {get_time_name(appointment)}
  Status   : {appointment.status.upper()}

"""
    if appointment.status == 'confirmed':
        body += "Please arrive 10 minutes before your scheduled time.\n"
    elif appointment.status == 'cancelled':
        body += f"To reschedule, call us at {CLINIC_PHONE}.\n"

    body += f"\n{CLINIC_NAME}"
    return send_clinic_email(label, body, appointment.email)


def send_admin_new_appointment_alert(appointment):
    subject = f"New Appointment: {appointment.name} – {appointment.date}"
    body = f"""New appointment booked.

Patient  : {appointment.name}
Phone    : {appointment.phone}
Email    : {appointment.email}
Service  : {get_service_name(appointment)}
Date     : {format_date(appointment.date)}
Time     : {get_time_name(appointment)}
Notes    : {appointment.notes or 'None'}

Login to admin panel to confirm or manage this appointment.
"""
    return send_clinic_email(subject, body, CLINIC_EMAIL)


# ── OTP EMAILS ───────────────────────────────────────────────

def send_otp_email(email, otp, purpose="Password Reset"):
    subject = f"{purpose} OTP"
    body = f"""Your OTP for {purpose} at {CLINIC_NAME}:

    OTP Code : {otp}

Valid for 5 minutes. Do not share it with anyone.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, email)


# ── STAFF EMAILS ─────────────────────────────────────────────

def send_leave_status_email(leave):
    if not leave.staff.email:
        return False
    subject = f"Leave Application {leave.status.upper()}"
    body = f"""Dear {leave.staff.get_full_name()},

Your leave application has been {leave.status}.

  Type   : {leave.get_leave_type_display()}
  From   : {format_date(leave.from_date)}
  To     : {format_date(leave.to_date)}
  Status : {leave.status.upper()}
  Note   : {leave.admin_note or 'No note'}

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, leave.staff.email)


def send_salary_paid_email(salary_record):
    if not salary_record.staff.email:
        return False
    subject = f"Salary Processed – {salary_record.month} {salary_record.year}"
    body = f"""Dear {salary_record.staff.get_full_name()},

Your salary for {salary_record.month} {salary_record.year} has been processed.

  Basic Salary : ₹{salary_record.basic_salary}
  Bonus        : ₹{salary_record.bonus}
  Deduction    : ₹{salary_record.deduction}
  Net Salary   : ₹{salary_record.net_salary}
  Paid On      : {format_date(salary_record.paid_on) if salary_record.paid_on else 'N/A'}

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, salary_record.staff.email)


def send_task_assigned_email(task):
    if not task.assigned_to.email:
        return False
    subject = f"New Task Assigned: {task.title}"
    body = f"""Dear {task.assigned_to.get_full_name()},

A new task has been assigned to you.

  Task     : {task.title}
  Priority : {task.priority.upper()}
  Due Date : {format_date(task.due_date) if task.due_date else 'No deadline'}
  Details  : {task.description or 'N/A'}

Login to your dashboard to update the task status.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, task.assigned_to.email)


def send_staff_welcome_email(user, password):
    if not user.email:
        return False
    subject = "Welcome to PhysioRehab – Your Login Details"
    body = f"""Dear {user.get_full_name()},

Welcome to {CLINIC_NAME}! Your staff account has been created.

  Username : {user.username}
  Password : {password}

Please change your password after first login.

{CLINIC_NAME}
"""
    return send_clinic_email(subject, body, user.email)