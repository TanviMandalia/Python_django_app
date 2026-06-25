from .models import Notification

SERVICE_NAMES = {
    'orthopedic':   'Orthopedic Therapy',
    'neurological': 'Neurological Rehab',
    'sports':       'Sports Rehabilitation',
    'pediatric':    'Pediatric Therapy',
    'womens':       "Women's Health",
    'home_visit':   'Home Visit',
}

def get_service_name(appt):
    return SERVICE_NAMES.get(appt.service, appt.service)


def notify(recipient, message, link=''):
    """Create a notification matching YOUR Notification model fields."""
    Notification.objects.create(
        recipient=recipient,
        message=message,
        link=link,
    )


# ── APPOINTMENT NOTIFICATIONS ────────────────────────────────

def notify_appointment_booked(appointment, admin_user):
    service = get_service_name(appointment)

    # Notify admin
    notify(
        recipient=admin_user,
        message=f'📅 New appointment: {appointment.name} booked {service} on {appointment.date}',
        link='/admin-appointments/',
    )
    # Notify patient if registered
    if appointment.patient:
        notify(
            recipient=appointment.patient,
            message=f'✅ Your {service} appointment on {appointment.date} is pending confirmation.',
            link='/my-appointments/',
        )


def notify_appointment_status(appointment):
    if not appointment.patient:
        return
    service = get_service_name(appointment)
    status_icons = {
        'confirmed': '✅',
        'completed': '🎉',
        'cancelled': '❌',
    }
    icon = status_icons.get(appointment.status, '📋')
    notify(
        recipient=appointment.patient,
        message=f'{icon} Your {service} appointment on {appointment.date} has been {appointment.status}.',
        link='/my-appointments/',
    )


# ── STAFF NOTIFICATIONS ──────────────────────────────────────

def notify_leave_decision(leave):
    icon = '✅' if leave.status == 'approved' else '❌'
    notify(
        recipient=leave.staff,
        message=f'{icon} Your {leave.get_leave_type_display()} ({leave.from_date} to {leave.to_date}) was {leave.status}.',
        link='/staff-leave/',
    )


def notify_task_assigned(task):
    notify(
        recipient=task.assigned_to,
        message=f'📋 New task assigned: {task.title} (Priority: {task.priority.upper()}). Due: {task.due_date or "No deadline"}.',
        link='/staff-tasks/',
    )


def notify_salary_paid(salary_record):
    notify(
        recipient=salary_record.staff,
        message=f'💰 Salary processed for {salary_record.month} {salary_record.year}. Net: ₹{salary_record.net_salary}',
        link='/staff-salary/',
    )