from django.core.management.base import BaseCommand
from core.models import EmailAccount, GmailOAuthCredential


class Command(BaseCommand):
    help = "Preview or reset email sender and Gmail OAuth configuration records; preserve mail history."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Delete the listed configuration records.")

    def handle(self, *args, **options):
        accounts = list(EmailAccount.objects.order_by("id"))
        mailboxes = list(GmailOAuthCredential.objects.order_by("email"))
        self.stdout.write("Email sender accounts to remove:")
        if accounts:
            for account in accounts:
                self.stdout.write(f"  id={account.pk} | {account.name} | {account.scope_type} | {account.from_email}")
        else:
            self.stdout.write("  (none)")
        self.stdout.write("Gmail OAuth mailbox authorizations to remove:")
        if mailboxes:
            for credential in mailboxes:
                self.stdout.write(f"  {credential.email} | active={credential.is_active} | authorized={credential.is_authorized}")
        else:
            self.stdout.write("  (none)")
        self.stdout.write("EmailLog and InboundEmail history will be preserved.")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Preview only. Add --apply to remove only these configuration records."))
            return

        account_count = len(accounts)
        mailbox_count = len(mailboxes)
        EmailAccount.objects.all().delete()
        GmailOAuthCredential.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f"Removed {account_count} sender account(s) and {mailbox_count} Gmail authorization(s); mail history was preserved."
        ))
