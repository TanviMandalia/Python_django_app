import logging
from django.core.management.base import BaseCommand, CommandError
from core.gmail_service import sync_gmail_messages, setup_gmail_watch, GmailAuthError, GmailConfigError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronize incoming messages from shared Gmail mailbox (physio.rehab.guj@gmail.com) via Gmail API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-results",
            type=int,
            default=25,
            help="Maximum number of messages to fetch in one sync run (default: 25).",
        )
        parser.add_argument(
            "--mailbox",
            type=str,
            default=None,
            help="Specific mailbox address to synchronize (defaults to shared mailbox).",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Call Gmail API watch endpoint to renew or register Google Cloud Pub/Sub push notifications.",
        )

    def handle(self, *args, **options):
        max_results = options.get("max_results") or 25
        mailbox = options.get("mailbox")
        do_watch = options.get("watch")

        if do_watch:
            self.stdout.write("Configuring Google Pub/Sub watch for Gmail mailbox...")
            try:
                watch_res = setup_gmail_watch(mailbox=mailbox)
                if watch_res.get("success"):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully configured watch: historyId={watch_res.get('history_id')}, "
                            f"expiration={watch_res.get('expiration')}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to configure watch: {watch_res.get('error')}")
                    )
            except Exception as e:
                raise CommandError(f"Watch configuration error: {e}")

        self.stdout.write(f"Initiating Gmail API synchronization (max_results={max_results})...")
        try:
            result = sync_gmail_messages(mailbox=mailbox, max_results=max_results)
        except GmailConfigError as e:
            raise CommandError(f"Gmail configuration error: {e}")
        except GmailAuthError as e:
            raise CommandError(f"Gmail authentication error (re-authorization required): {e}")
        except Exception as e:
            logger.exception("Unexpected error during Gmail synchronization: %s", e)
            raise CommandError(f"Unexpected sync failure: {e}")

        synced = result.get("synced", 0)
        duplicates = result.get("duplicates", 0)
        errors = result.get("errors", 0)
        history_id = result.get("history_id")

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete: {synced} new messages ingested, {duplicates} duplicates skipped, "
                f"{errors} errors. Current historyId: {history_id}."
            )
        )
