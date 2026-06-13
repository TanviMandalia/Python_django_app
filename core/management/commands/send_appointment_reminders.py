# ════════════════════════════════════════════════════════════
# FEATURE 1 — Appointment Reminder Email
# FILE: core/management/commands/send_appointment_reminders.py
# ════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from core.models import Appointment

class Command(BaseCommand):
    help = 'Send appointment reminder emails 24 hours before appointment'

    def handle(self, *args, **kwargs):
        tomorrow = timezone.localdate() + timedelta(days=1)

        appointments = Appointment.objects.filter(
            date=tomorrow,
            status__in=['confirmed', 'pending'],
        ).select_related('patient')

        self.stdout.write(f'Found {appointments.count()} appointments for tomorrow.')

        for appt in appointments:
            email = appt.email or (appt.patient.email if appt.patient else None)
            name  = appt.name or (appt.patient.get_full_name() if appt.patient else 'Patient')

            if not email:
                self.stdout.write(f'  ⚠️ No email for {name} — skipping.')
                continue

            try:
                send_mail(
                    subject='📅 Appointment Reminder — Tomorrow at Dr. Dhvani Patalia Physio Rehab',
                    message=f"""
Dear {name},

This is a friendly reminder that you have an appointment scheduled for TOMORROW.

  📅 Date     : {appt.date.strftime('%d %B %Y')}
  🕐 Time     : {appt.get_time_display() if hasattr(appt, 'get_time_display') else appt.time}
  🏥 Service  : {appt.get_service_display()}
  📌 Status   : {appt.status.title()}

📍 Location:
Dr. Dhvani Patalia Physio Rehab Clinic

Please arrive 10 minutes early.
If you need to cancel or reschedule, please contact us as soon as possible.

For queries, reply to this email or contact us directly.

Regards,
Dr. Dhvani Patalia
Physio Rehab Clinic
                    """.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                self.stdout.write(f'  ✅ Reminder sent to {name} ({email})')
            except Exception as e:
                self.stdout.write(f'  ❌ Failed for {name}: {e}')

        self.stdout.write(self.style.SUCCESS('✅ Appointment reminders done.'))