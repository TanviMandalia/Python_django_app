from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import HospitalSubscription
from core.email_utils import send_subscription_expiry_warning_email, send_subscription_success_email


class Command(BaseCommand):
    help = 'Check subscription expiries and send warning emails 5 days before expiry'

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        warning_date = today + timedelta(days=5)

        expiring_soon = HospitalSubscription.objects.filter(
            status='active',
            expires_at=warning_date,
        ).select_related('hospital', 'plan')

        count = 0
        for sub in expiring_soon:
            if sub.hospital.email:
                send_subscription_expiry_warning_email(
                    sub.hospital, sub.plan, sub.expires_at, days_left=5
                )
                count += 1
                self.stdout.write(f'  Warned: {sub.hospital.name}')

        expired = HospitalSubscription.objects.filter(
            status='active',
            expires_at__lt=today,
        )
        expired_count = expired.update(status='expired')

        self.stdout.write(self.style.SUCCESS(
            f'Expiry warnings sent: {count}. Subscriptions marked expired: {expired_count}.'
        ))
