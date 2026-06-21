from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import SessionNote, Notification
from core.email_utils import send_clinic_email


class Command(BaseCommand):
    help = 'Send exercise reminders to patients whose next session date is tomorrow'

    def handle(self, *args, **kwargs):
        tomorrow = timezone.localdate() + timedelta(days=1)
        notes = SessionNote.objects.filter(next_session__icontains=str(tomorrow)).select_related('patient')
        sent = 0
        for note in notes:
            patient = note.patient
            Notification.objects.create(
                recipient=patient,
                message=f'🏃 Reminder from Dr. Dhvani: Complete your exercises before tomorrow\'s session. Stay consistent for faster recovery!',
                link='/my-appointments/',
            )
            if patient.email:
                send_clinic_email(
                    subject='Exercise Reminder — Tomorrow\'s Session',
                    message_text=f"""Dear {patient.get_full_name() or patient.username},

This is a friendly reminder from Dr. Dhvani Patalia's PhysioRehab Clinic.

Your next physiotherapy session is scheduled for tomorrow ({tomorrow.strftime('%d %B %Y')}).

Please ensure you have completed your prescribed exercises:
{note.next_session}

Consistency is key to faster recovery. See you tomorrow!

Dr. Dhvani Patalia — PhysioRehab Clinic
""",
                    recipient_list=[patient.email],
                )
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Exercise reminders sent to {sent} patients.'))
