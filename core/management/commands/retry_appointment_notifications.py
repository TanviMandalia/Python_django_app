import logging
from django.core.management.base import BaseCommand
from core.models import PublicAppointmentRequest
from core.email_utils import send_public_appointment_request_notification

logger = logging.getLogger("core.notifications")


class Command(BaseCommand):
    help = "Retry sending failed email notifications for public appointment requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ref",
            type=str,
            help="Specific PublicAppointmentRequest reference ID to retry (e.g. PAR-20261021-A1B2).",
        )
        parser.add_argument(
            "--all-failed",
            action="store_true",
            help="Retry all appointment requests marked with email_notification_status='failed'.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of failed notifications to process in one run (default: 50).",
        )

    def handle(self, *args, **options):
        ref = options.get("ref")
        limit = options.get("limit", 50)

        if ref:
            qs = PublicAppointmentRequest.objects.filter(reference_id=ref)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"No appointment request found with reference ID: {ref}"))
                return
        else:
            qs = PublicAppointmentRequest.objects.filter(email_notification_status="failed").order_by("created_at")[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No pending failed appointment notifications to retry."))
            return

        self.stdout.write(f"Retrying notifications for {total} public appointment request(s)...")

        success_count = 0
        failed_count = 0

        for req in qs:
            self.stdout.write(f"Processing reference: {req.reference_id} ({req.patient_name} - {req.preferred_date})...")
            try:
                sent = send_public_appointment_request_notification(req)
                if sent:
                    req.email_notification_status = "sent"
                    req.notification_error = ""
                    req.save(update_fields=["email_notification_status", "notification_error"])
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  [SENT] {req.reference_id}"))
                else:
                    req.email_notification_status = "failed"
                    req.notification_error = "Notification attempt returned failure"
                    req.save(update_fields=["email_notification_status", "notification_error"])
                    failed_count += 1
                    self.stdout.write(self.style.WARNING(f"  [FAILED] {req.reference_id}"))
            except Exception as exc:
                err_msg = f"{exc.__class__.__name__}: {str(exc)[:200]}"
                req.email_notification_status = "failed"
                req.notification_error = err_msg
                req.save(update_fields=["email_notification_status", "notification_error"])
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"  [ERROR] {req.reference_id}: {err_msg}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Notification retry run complete: {success_count} succeeded, {failed_count} failed out of {total}."
            )
        )
