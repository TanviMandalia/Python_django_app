"""Create the platform and clinic Gmail SMTP sender records safely."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import EmailAccount, Hospital


class Command(BaseCommand):
    help = (
        "Create or update the two role-scoped Gmail SMTP accounts using "
        "smtp.gmail.com:587 with STARTTLS. Passwords are never generated or printed."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        platform_email = settings.PLATFORM_SUPERADMIN_EMAIL.strip().lower()
        clinic_email = settings.GMAIL_SHARED_MAILBOX.strip().lower()
        hospital = (
            Hospital.objects.filter(email__iexact=clinic_email).first()
            or Hospital.objects.filter(is_active=True).order_by("id").first()
        )
        if not hospital:
            raise CommandError(
                "No active clinic exists. Create the clinic record before configuring its mailbox."
            )

        self._configure(
            name="TechCraft Super Admin Gmail",
            email=platform_email,
            scope_type="platform",
            hospital=None,
            from_name=getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft"),
        )
        self._configure(
            name=f"{hospital.name} Gmail",
            email=clinic_email,
            scope_type="hospital",
            hospital=hospital,
            from_name=hospital.name,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Configured platform and clinic Gmail SMTP accounts for port 587/STARTTLS. "
                "Set each mailbox's App Password in the Email Accounts screen or its dedicated "
                "SMTP environment variable; credentials were not changed."
            )
        )

    def _configure(self, *, name, email, scope_type, hospital, from_name):
        scope_accounts = EmailAccount.objects.filter(scope_type=scope_type)
        scoped = scope_accounts.filter(hospital=hospital)
        account = scoped.filter(is_default=True).first()
        if account is None:
            account = scoped.filter(from_email__iexact=email).first()
        if account is None:
            account = EmailAccount(
                scope_type=scope_type,
                hospital=hospital,
                encrypted_password="",
            )

        # Keep one unambiguous default account for this scope; retain other
        # account records and their audit history.
        scope_accounts.exclude(pk=account.pk).filter(is_default=True).update(is_default=False)
        account.name = name
        account.account_type = "PLATFORM" if scope_type == "platform" else "CLINIC"
        account.scope_type = scope_type
        account.hospital = hospital
        account.provider = "gmail"
        account.host = "smtp.gmail.com"
        account.port = 587
        account.use_tls = True
        account.use_ssl = False
        account.username = email
        account.from_email = email
        account.from_name = from_name
        account.reply_to = email
        account.is_active = True
        account.is_default = True
        account.save()
        self.stdout.write(f"Ready: {scope_type} sender {email} (password unchanged).")
