from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import VisitorSession, VisitorConsentRecord, AnalyticsSetting, AnalyticsAuditLog


class Command(BaseCommand):
    help = (
        "Clean up expired visitor sessions and pageview events based on privacy retention policies. "
        "Strictly isolated: does not delete clinic data, appointments, patient records, or voluntary leads."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override retention threshold in days. Defaults to AnalyticsSetting.retention_days.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate cleanup and print how many records would be deleted without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        days = options.get("days")

        if days is None:
            settings_obj = AnalyticsSetting.get_settings()
            days = settings_obj.retention_days or 90

        cutoff = timezone.now() - timedelta(days=days)
        self.stdout.write(f"Evaluating visitor data older than {days} days (cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')})...")

        expired_sessions = VisitorSession.objects.filter(started_at__lt=cutoff)
        session_count = expired_sessions.count()

        expired_consents = VisitorConsentRecord.objects.filter(timestamp__lt=cutoff)
        consent_count = expired_consents.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Would delete {session_count} expired VisitorSession(s) (plus cascading PageViewEvents) "
                    f"and {consent_count} expired VisitorConsentRecord(s)."
                )
            )
            return

        # Perform deletion
        deleted_sessions, _ = expired_sessions.delete()
        deleted_consents, _ = expired_consents.delete()

        # Audit the automated or manual purge
        AnalyticsAuditLog.objects.create(
            user=None,
            action="purge_data",
            details=f"Retention cleanup command purged {deleted_sessions} sessions and {deleted_consents} consent records older than {days} days.",
            ip_address="127.0.0.1",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {session_count} expired VisitorSession(s) and {consent_count} expired VisitorConsentRecord(s). "
                f"Clinic, patient, and enquiry records were completely unaffected."
            )
        )
