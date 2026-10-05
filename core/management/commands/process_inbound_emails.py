import json
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from core.email_utils import process_inbound_email_payload


class Command(BaseCommand):
    help = "Ingest and process inbound emails from a JSON file, standard input, or payload queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Path to JSON file containing single or array of inbound email objects.",
        )
        parser.add_argument(
            "--stdin",
            action="store_true",
            help="Read JSON email payload directly from standard input (stdin).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate validation and parsing without committing database records.",
        )

    def handle(self, *args, **options):
        file_path = options.get("file")
        from_stdin = options.get("stdin")
        dry_run = options.get("dry_run")

        if not file_path and not from_stdin:
            raise CommandError("Please specify either --file <path> or --stdin.")

        raw_data = ""
        if from_stdin:
            self.stdout.write("Reading inbound email JSON from stdin...")
            raw_data = sys.stdin.read()
        elif file_path:
            p = Path(file_path)
            if not p.is_file():
                raise CommandError(f"Inbound email file does not exist: {file_path}")
            raw_data = p.read_text(encoding="utf-8")

        try:
            parsed = json.loads(raw_data)
        except Exception as e:
            raise CommandError(f"Failed to parse inbound email JSON: {e}")

        payloads = parsed if isinstance(parsed, list) else [parsed]
        self.stdout.write(f"Processing {len(payloads)} inbound email message(s)...")

        processed = 0
        duplicates = 0
        rejected = 0

        for idx, payload in enumerate(payloads, start=1):
            if not isinstance(payload, dict):
                self.stderr.write(f"Item #{idx}: Skipped, item is not a valid JSON dictionary.")
                rejected += 1
                continue

            if dry_run:
                self.stdout.write(f"[DRY-RUN] Item #{idx}: Sender={payload.get('sender') or payload.get('from')} Subject={payload.get('subject')}")
                processed += 1
                continue

            result = process_inbound_email_payload(payload)
            status = result.get("status")

            if status == "processed":
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"Item #{idx}: Successfully processed (ID={result.get('id')}, MsgID={result.get('message_id')})"))
            elif status == "duplicate":
                duplicates += 1
                self.stdout.write(self.style.WARNING(f"Item #{idx}: Duplicate detected, ignored (MsgID={result.get('message_id')})"))
            else:
                rejected += 1
                self.stdout.write(self.style.ERROR(f"Item #{idx}: Rejected - {result.get('error')}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nFinished: {processed} processed, {duplicates} duplicates ignored, {rejected} rejected."
            )
        )
