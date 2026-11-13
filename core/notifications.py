"""
In-app notifications + notification-triggered emails for PhysioRehab Clinic.

Email sending uses the shared send_email_task when a real Celery broker is
configured. In filesystem-only local mode there is no worker to consume queued
tasks, so sends fall back to the canonical send_clinic_email implementation.
Failures are logged and never hidden with fail_silently.
"""

import logging

from django.conf import settings

from .models import Notification
from .tasks import send_email_task

logger = logging.getLogger(__name__)

SERVICE_NAMES = {
    'orthopedic': 'Orthopedic Therapy',
    'neurological': 'Neurological Rehab',
    'sports': 'Sports Rehabilitation',
    'pediatric': 'Pediatric Therapy',
    'womens': "Women's Health",
    'home_visit': 'Home Visit',
}


# ─────────────────────────────────────────────
# EMAIL HELPERS (queued via Celery, non-blocking)
# ─────────────────────────────────────────────

def send_welcome_email(user):
    if not user.email:
        return

    subject = "Welcome to Hospital System"
    body = f"Hello {user.username}, welcome onboard!"

    send_email_task.delay(subject, body, [user.email])


def send_appointment_email(patient_email, doctor_name, date):
    if not patient_email:
        return

    subject = "Appointment Confirmation"
    body = f"Your appointment with Dr {doctor_name} is scheduled on {date}"

    send_email_task.delay(subject, body, [patient_email])


# ─────────────────────────────────────────────
# UTIL
# ─────────────────────────────────────────────

def get_service_name(appt):
    return SERVICE_NAMES.get(appt.service, appt.service)


def notify(recipient, message, link="", hospital=None):
    """
    Create an in-app notification safely. This does NOT send email — it's
    purely the bell-icon notification record. Email is a separate, explicit
    call (see the email helpers above / email_utils.py / tasks.py).
    """
    if not recipient:
        return

    try:
        Notification.objects.create(
            hospital=hospital,
            recipient=recipient,
            message=message,
            link=link,
        )
    except Exception as e:
        # A failed in-app notification should never break the calling view
        # (e.g. appointment booking, leave approval) — log and move on.
        logger.error(f"Failed to create notification for {recipient}: {e}")


def notify_with_email(recipient, message, subject, link="", hospital=None, email_type="activity_notification"):
    """Create an in-app notification and deliver a matching email when possible."""
    if not recipient:
        return False
    notify(recipient, message, link=link, hospital=hospital)
    if not getattr(recipient, "email", ""):
        return False
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    if not broker_url or broker_url.startswith("filesystem://"):
        # The filesystem broker only stores tasks; it does not deliver them without
        # a separately running worker. Send transactionally in-process in this mode.
        try:
            from .email_utils import send_clinic_email
            return bool(send_clinic_email(
                subject,
                message,
                [recipient.email],
                hospital=hospital,
                email_type=email_type,
            ))
        except Exception:
            logger.exception("Synchronous %s email failed for user id %s", email_type, recipient.pk)
            return False
    try:
        send_email_task.delay(
            subject,
            message,
            [recipient.email],
            hospital_id=getattr(hospital, "id", None),
            email_type=email_type,
        )
        return True
    except Exception:
        logger.exception("Could not queue %s email for user id %s", email_type, recipient.pk)
        try:
            from .email_utils import send_clinic_email
            return bool(send_clinic_email(
                subject,
                message,
                [recipient.email],
                hospital=hospital,
                email_type=email_type,
            ))
        except Exception:
            logger.exception("Email fallback failed for user id %s", recipient.pk)
            return False


def notify_payment_activity(payment, event):
    """Notify a patient about a payment event in the app and by email."""
    patient = getattr(payment, "patient", None)
    if not patient:
        return False
    event_details = {
        "recorded": ("Payment receipt recorded", "Your payment of ₹{amount} ({method}) has been recorded."),
        "submitted": ("Payment submitted for verification", "Your UPI payment of ₹{amount} was submitted and is awaiting verification."),
        "confirmed": ("Payment confirmed", "Your payment of ₹{amount} has been confirmed by the clinic."),
        "rejected": ("Payment needs attention", "Your payment of ₹{amount} could not be verified. Please contact the clinic."),
        "refunded": ("Payment refunded", "Your payment of ₹{amount} has been refunded by the clinic."),
    }
    subject, text = event_details.get(event, event_details["recorded"])
    message = text.format(amount=payment.amount, method=payment.get_method_display())
    clinic_name = payment.hospital.name if payment.hospital else "PhysioRehab Clinic"
    return notify_with_email(
        patient,
        message,
        f"{subject} | {clinic_name}",
        link="/payments/",
        hospital=payment.hospital,
        email_type=f"payment_{event}",
    )


def notify_session_note_activity(note, actor=None, updated=False):
    """Notify the patient and (when different from the actor) assigned therapist of a note change."""
    hospital = getattr(note, "hospital", None)
    patient_message = "A clinical session note was updated in your care record." if updated else "A new clinical session note was added to your care record."
    clinic_name = hospital.name if hospital else "PhysioRehab Clinic"
    if note.patient:
        notify_with_email(
            note.patient,
            f"{patient_message} Sign in to your patient dashboard to review your progress.",
            f"Your care record was updated | {clinic_name}",
            link="/progress/",
            hospital=hospital,
            email_type="session_note_patient",
        )
    if note.staff and note.staff_id != getattr(actor, "id", None):
        patient_label = note.patient.get_full_name() or note.patient.username if note.patient else "a patient"
        staff_message = f"A session note was {'updated' if updated else 'added'} for {patient_label}. Sign in to your staff dashboard to review the record."
        notify_with_email(
            note.staff,
            staff_message,
            f"Session note activity | {clinic_name}",
            link="/staff-session-notes/",
            hospital=hospital,
            email_type="session_note_staff",
        )


def notify_leave_request_created(leave, admin_user):
    if not leave or not admin_user:
        return False
    clinic_name = leave.hospital.name if leave.hospital else "PhysioRehab Clinic"
    staff_name = leave.staff.get_full_name() or leave.staff.username
    message = (
        f"{staff_name} submitted a {leave.get_leave_type_display()} leave request "
        f"from {leave.from_date} to {leave.to_date}. Sign in to review it."
    )
    return notify_with_email(
        admin_user,
        message,
        f"New staff leave request | {clinic_name}",
        link="/admin-leaves/",
        hospital=leave.hospital,
        email_type="leave_request_created",
    )


def notify_chat_message(message):
    if not message or not message.receiver:
        return False
    sender_name = message.sender.get_full_name() or message.sender.username
    hospital = message.hospital
    clinic_name = hospital.name if hospital else "PhysioRehab Clinic"
    return notify_with_email(
        message.receiver,
        f"You received a new message from {sender_name}. Sign in to your dashboard to read and reply.",
        f"New message from {sender_name} | {clinic_name}",
        link="/chat/",
        hospital=hospital,
        email_type="new_chat_message",
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
        hospital=appointment.hospital,
    )

    if appointment.patient:
        notify(
            recipient=appointment.patient,
            message=f"✅ Your {service} appointment on {appointment.date} is {appointment.status}.",
            link="/my-appointments/",
            hospital=appointment.hospital,
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
        hospital=appointment.hospital,
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
        hospital=leave.hospital,
    )


def notify_task_assigned(task):
    if not task.assigned_to:
        return

    notify(
        recipient=task.assigned_to,
        message=f"📋 New task assigned: {task.title} (Priority: {task.priority.upper()}). Due: {task.due_date or 'No deadline'}.",
        link="/staff-tasks/",
        hospital=task.hospital,
    )


def notify_salary_paid(salary_record):
    if not salary_record.staff:
        return

    notify(
        recipient=salary_record.staff,
        message=f"💰 Salary processed for {salary_record.month} {salary_record.year}. Net: ₹{salary_record.net_salary}",
        link="/staff-salary/",
        hospital=salary_record.hospital,
    )
