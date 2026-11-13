"""Send each confirmed patient an email reminder approximately one hour before."""

from datetime import datetime, timedelta
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.email_utils import send_clinic_email
from core.models import Appointment


logger = logging.getLogger(__name__)


def _appointment_datetime(appointment):
    """Parse the legacy appointment time strings in the clinic's local timezone."""
    parsed_time = None
    for time_format in ("%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            parsed_time = datetime.strptime(appointment.time.strip(), time_format).time()
            break
        except (AttributeError, TypeError, ValueError):
            continue

    if parsed_time is None:
        return None

    naive_datetime = datetime.combine(appointment.date, parsed_time)
    return timezone.make_aware(naive_datetime, timezone.get_current_timezone())


class Command(BaseCommand):
    help = "Send one-time email reminders for confirmed appointments within the next hour."

    def handle(self, *args, **kwargs):
        now = timezone.now()
        local_today = timezone.localdate(now)
        tomorrow = local_today + timedelta(days=1)
        appointments = (
            Appointment.objects.filter(
                status="confirmed",
                date__gte=local_today,
                date__lte=tomorrow,
            )
            .select_related("patient", "hospital")
            .order_by("date", "time", "id")
        )

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for appointment in appointments:
            starts_at = _appointment_datetime(appointment)
            if starts_at is None:
                logger.warning(
                    "Skipping appointment reminder for appointment %s: unsupported time value %r",
                    appointment.pk,
                    appointment.time,
                )
                skipped_count += 1
                continue

            if not now < starts_at <= now + timedelta(hours=1):
                continue
            if appointment.reminder_sent_for == starts_at:
                continue

            recipient = (appointment.email or "").strip() or (
                (appointment.patient.email or "").strip() if appointment.patient else ""
            )
            if not recipient:
                logger.warning(
                    "Skipping appointment reminder for appointment %s: patient has no email address",
                    appointment.pk,
                )
                skipped_count += 1
                continue

            patient_name = appointment.name or (
                appointment.patient.get_full_name() or appointment.patient.username
                if appointment.patient
                else "Patient"
            )
            clinic_name = (
                appointment.hospital.name
                if appointment.hospital
                else "Dr. Dhvani Patalia Physio Rehab"
            )
            clinic_phone = (
                appointment.hospital.phone
                if appointment.hospital and appointment.hospital.phone
                else "+91 94095 10501"
            )
            display_time = appointment.get_time_display()
            subject = f"Appointment reminder: your visit is in one hour - {clinic_name}"
            message = f"""Dear {patient_name},

This is a reminder that your appointment is scheduled to begin in about one hour.

Date: {timezone.localtime(starts_at).strftime('%A, %d %B %Y')}
Time: {display_time}
Service: {appointment.get_service_display()}
Clinic: {clinic_name}

Please arrive a few minutes early. If you need to change your appointment, contact the clinic at {clinic_phone}.

Regards,
{clinic_name}
"""

            # Lock before sending so overlapping/manual runs cannot send duplicates.
            with transaction.atomic():
                locked_appointment = (
                    Appointment.objects.select_for_update()
                    .filter(pk=appointment.pk)
                    .first()
                )
                if not (
                    locked_appointment
                    and locked_appointment.status == "confirmed"
                    and _appointment_datetime(locked_appointment) == starts_at
                    and locked_appointment.reminder_sent_for != starts_at
                ):
                    skipped_count += 1
                    continue

                try:
                    delivered = send_clinic_email(
                        subject=subject,
                        message_text=message,
                        recipient_list=[recipient],
                        hospital=locked_appointment.hospital,
                        email_type="appointment_reminder",
                    )
                except Exception:
                    logger.exception(
                        "Appointment reminder delivery raised an error for appointment %s",
                        appointment.pk,
                    )
                    delivered = False

                if not delivered:
                    failed_count += 1
                    self.stderr.write(
                        self.style.WARNING(
                            f"Reminder failed for appointment {appointment.pk} ({recipient})."
                        )
                    )
                    continue

                locked_appointment.reminder_sent_for = starts_at
                locked_appointment.save(update_fields=["reminder_sent_for"])
                sent_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Reminder sent for appointment {appointment.pk} to {recipient}."
                    )
                )

        self.stdout.write(
            f"Appointment reminder run finished: {sent_count} sent, "
            f"{failed_count} failed, {skipped_count} skipped."
        )
