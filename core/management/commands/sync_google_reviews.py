"""
Management command to synchronize Google Reviews for the clinic.
Safe execution: If GOOGLE_MAPS_API_KEY is not configured, logs a clear notice without failing.
"""

from django.core.management.base import BaseCommand
from core.google_reviews import sync_google_reviews_to_db


class Command(BaseCommand):
    help = "Sync verified Google Reviews from Google Places API into the local database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bypass cached review data and fetch fresh records from Google Places API',
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting Google Reviews synchronization...")
        force = options.get('force', False)
        
        result = sync_google_reviews_to_db(force_refresh=force)
        
        if result.get("synced"):
            count = result.get("created_count", 0)
            rating = result.get("rating", 0)
            total = result.get("user_ratings_total", 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully synced Google Reviews! "
                    f"Rating: {rating} stars | Total Reviews on Google: {total} | Synced {count} new reviews."
                )
            )
        else:
            reason = result.get("error", "Unknown reason")
            self.stdout.write(
                self.style.WARNING(
                    f"Google Review sync skipped or completed with fallback: {reason}. "
                    "Public pages will continue using cached data or fallback destination gracefully."
                )
            )
