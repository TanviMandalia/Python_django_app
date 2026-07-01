from django.conf import settings
from .models import Notification

# IMPORTANT:
# Replace this import with your actual email function location
# If you don't have async system yet, fallback is fine.
try:
    from .tasks import send_email_async
except ImportError:
    from django.core.mail import send_mail

    def send_email_async(subject, message, recipient_list):
        return send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            recipient_list,
            fail_silently=True,
        )


SERVICE_NAMES = {
    'orthopedic': 'Orthopedic Therapy',
    'neurological': 'Neurological Rehab',
    'sports': 'Sports Rehabilitation',
    'pediatric': 'Pediatric Therapy',
    'womens': "Women's Health",
    'home_visit': 'Home Visit',
}


# ─────────────────────────────────────────────
# EMAIL HELPERS
# ─────────────────────────────────────────────

def send_welcome_email(user):
    if not user.email:
        return

    subject = "Welcome to Hospital System"
    body = f"Hello {user.username}, welcome onboard!"

    send_email_async(subject, body, [user.email])


def send_appointment_email(patient_email, doctor_name, date):
    if not patient_email:
        return

    subject = "Appointment Confirmation"
    body = f"Your appointment with Dr {doctor_name} is scheduled on {date}"

    send_email_async(subject, body, [patient_email])


# ─────────────────────────────────────────────
# UTIL
# ─────────────────────────────────────────────

def get_service_name(appt):
    return SERVICE_NAMES.get(appt.service, appt.service)


def notify(recipient, message, link=""):
    """
    Create a notification safely.
    """
    if not recipient:
        return

    Notification.objects.create(
        recipient=recipient,
        message=message,
        link=link,
    )


# ─────────────────────────────────────────────
# APPOINTMENT NOTIFICATIONS
# ─────────────────────────────────────────────

def notify_appointment_booked(appointment, admin_user):
    service = get_service_name(appointment)

    notify(
        recipient=admin_user,
        message=f"📅 New appointment: {appointment.name} booked {service} on {appointment.date}",
        link="/admin-appointments/",
    )

    if appointment.patient:
        notify(
            recipient=appointment.patient,
            message=f"✅ Your {service} appointment on {appointment.date} is pending confirmation.",
            link="/my-appointments/",
        )


def notify_appointment_status(appointment):
    if not appointment.patient:
        return

    service = get_service_name(appointment)

    status_icons = {
        "confirmed": "✅",
        "completed": "🎉",
        "cancelled": "❌",
    }

    icon = status_icons.get(appointment.status, "📋")

    notify(
        recipient=appointment.patient,
        message=f"{icon} Your {service} appointment on {appointment.date} has been {appointment.status}.",
        link="/my-appointments/",
    )


# ─────────────────────────────────────────────
# STAFF NOTIFICATIONS
# ─────────────────────────────────────────────

def notify_leave_decision(leave):
    if not leave.staff:
        return

    icon = "✅" if leave.status == "approved" else "❌"

    notify(
        recipient=leave.staff,
        message=f"{icon} Your {leave.get_leave_type_display()} ({leave.from_date} to {leave.to_date}) was {leave.status}.",
        link="/staff-leave/",
    )


def notify_task_assigned(task):
    if not task.assigned_to:
        return

    notify(
        recipient=task.assigned_to,
        message=f"📋 New task assigned: {task.title} (Priority: {task.priority.upper()}). Due: {task.due_date or 'No deadline'}.",
        link="/staff-tasks/",
    )


def notify_salary_paid(salary_record):
    if not salary_record.staff:
        return

    notify(
        recipient=salary_record.staff,
        message=f"💰 Salary processed for {salary_record.month} {salary_record.year}. Net: ₹{salary_record.net_salary}",
        link="/staff-salary/",
    )