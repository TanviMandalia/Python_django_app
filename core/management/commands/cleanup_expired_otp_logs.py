import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from core.models import EmailLog, PasswordResetOTP

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup expired OTP email audit logs and expired OTP verification codes (24-hour retention policy)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the cleanup without deleting records from the database.",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Retention threshold in hours for OTP email logs (default: 24).",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        hours = options.get("hours", 24)
        now = timezone.now()
        threshold_time = now - timezone.timedelta(hours=hours)

        self.stdout.write(
            self.style.NOTICE(
                f"Starting OTP retention cleanup at {now.isoformat()} (Threshold: {hours}h)..."
            )
        )

        # 1. Target expired OTP EmailLog entries
        otp_query = EmailLog.objects.filter(
            Q(is_otp=True, expires_at__lte=now)
            | Q(is_otp=True, created_at__lte=threshold_time)
            | Q(email_type__in=["platform_otp", "otp_verification", "otp", "password_reset_otp"], created_at__lte=threshold_time)
        )
        otp_log_count = otp_query.count()

        # 2. Target expired PasswordResetOTP entries (older than 15 minutes or threshold)
        otp_token_threshold = now - timezone.timedelta(minutes=15)
        otp_tokens_query = PasswordResetOTP.objects.filter(created_at__lte=otp_token_threshold)
        otp_token_count = otp_tokens_query.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Found {otp_log_count} expired OTP email logs and {otp_token_count} expired OTP tokens to delete."
                )
            )
            return

        # Perform deletion
        deleted_logs, _ = otp_query.delete()
        deleted_tokens, _ = otp_tokens_query.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {deleted_logs} expired OTP email logs and {deleted_tokens} expired OTP tokens."
            )
        )
        logger.info(
            f"OTP audit cleanup executed: {deleted_logs} EmailLog records, {deleted_tokens} PasswordResetOTP tokens removed."
        )
