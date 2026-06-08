"""
Centralised notification helper.
Creates in-app Notification records. Import and call these
from views instead of creating notifications manually.
"""

from .models import Notification


def notify(recipient, notif_type, title, message, link=''):
    """Create an in-app notification for a user."""
    Notification.objects.create(
        recipient=recipient,
        notif_type=notif_type,
        title=title,
        message=message,
        link=link,
    )


# ─── APPOINTMENT NOTIFICATIONS ───────────────────────────────

def notify_appointment_booked(appointment, admin_user):
    """Notify admin when patient books appointment."""
    notify(
        recipient=admin_user,
        notif_type='appointment_booked',
        title=f'New Appointment: {appointment.name}',
        message=f'{appointment.name} booked {appointment.get_service_display_name()} on {appointment.date}',
        link='/admin-appointments/',
    )
    # Notify patient (if registered)
    if appointment.patient:
        notify(
            recipient=appointment.patient,
            notif_type='appointment_booked',
            title='Appointment Booked',
            message=f'Your {appointment.get_service_display_name()} appointment on {appointment.date} is pending confirmation.',
            link='/my-appointments/',
        )


def notify_appointment_status(appointment):
    """Notify patient when admin changes appointment status."""
    if not appointment.patient:
        return
    status_titles = {
        'confirmed': '✅ Appointment Confirmed',
        'completed': '🎉 Session Completed',
        'cancelled': '❌ Appointment Cancelled',
    }
    title = status_titles.get(appointment.status, 'Appointment Updated')
    notify(
        recipient=appointment.patient,
        notif_type=f'appointment_{appointment.status}',
        title=title,
        message=f'Your {appointment.get_service_display_name()} on {appointment.date} – {appointment.status}.',
        link='/my-appointments/',
    )


# ─── STAFF NOTIFICATIONS ─────────────────────────────────────

def notify_leave_decision(leave):
    notify(
        recipient=leave.staff,
        notif_type=f'leave_{leave.status}',
        title=f'Leave {leave.status.capitalize()}',
        message=f'Your {leave.get_leave_type_display()} ({leave.from_date} to {leave.to_date}) was {leave.status}.',
        link='/staff-leave/',
    )


def notify_task_assigned(task):
    notify(
        recipient=task.assigned_to,
        notif_type='task_assigned',
        title=f'New Task: {task.title}',
        message=f'Priority: {task.priority.upper()}. Due: {task.due_date or "No deadline"}.',
        link='/staff-tasks/',
    )


def notify_salary_paid(salary_record):
    notify(
        recipient=salary_record.staff,
        notif_type='salary_paid',
        title=f'Salary Processed – {salary_record.month} {salary_record.year}',
        message=f'Net salary ₹{salary_record.net_salary} has been credited.',
        link='/staff-salary/',
    )
    
from .notifications import (
    notify_appointment_booked,
    notify_appointment_status,
    notify_leave_decision,
    notify_task_assigned,
    notify_salary_paid,
)