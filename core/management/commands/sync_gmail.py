import logging

from django.core.management.base import BaseCommand, CommandError
from core.gmail_service import (
    GmailAuthError,
    GmailConfigError,
    get_configured_mailboxes,
    setup_gmail_watch,
    sync_gmail_messages,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronize incoming messages from configured Gmail inboxes via Gmail API."

    def add_arguments(self, parser):
        parser.add_argument("--max-results", type=int, default=25)
        parser.add_argument("--mailbox", type=str, default=None, help="Sync only this configured mailbox.")
        parser.add_argument("--watch", action="store_true", help="Register or renew Pub/Sub watch for each selected mailbox.")

    def handle(self, *args, **options):
        max_results = options.get("max_results") or 25
        requested = options.get("mailbox")
        mailboxes = [requested.strip().lower()] if requested else get_configured_mailboxes()
        allowed = set(get_configured_mailboxes())
        if any(address not in allowed for address in mailboxes):
            raise CommandError("Requested mailbox is not listed in GMAIL_INBOUND_MAILBOXES.")

        failures = 0
        for mailbox in mailboxes:
            if options.get("watch"):
                try:
                    result = setup_gmail_watch(mailbox=mailbox)
                    self.stdout.write(self.style.SUCCESS(f"Pub/Sub watch ready for {mailbox} (historyId={result.get('historyId', '')})."))
                except Exception as exc:
                    failures += 1
                    self.stderr.write(self.style.ERROR(f"Watch setup failed for {mailbox}: {type(exc).__name__}: {exc}"))
            try:
                result = sync_gmail_messages(mailbox=mailbox, max_results=max_results)
                self.stdout.write(self.style.SUCCESS(
                    f"{mailbox}: {result.get('synced', 0)} new, {result.get('duplicates', 0)} duplicates, "
                    f"{result.get('errors', 0)} errors."
                ))
            except (GmailConfigError, GmailAuthError) as exc:
                failures += 1
                self.stderr.write(self.style.ERROR(f"{mailbox}: {exc}"))
            except Exception as exc:
                failures += 1
                logger.exception("Unexpected Gmail synchronization failure for %s", mailbox)
                self.stderr.write(self.style.ERROR(f"{mailbox}: sync failed ({type(exc).__name__})."))
        if failures:
            raise CommandError(f"Gmail operation completed with {failures} mailbox failure(s).")
