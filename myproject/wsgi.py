"""
WSGI config for myproject project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from pathlib import Path
from django import setup
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings.production')

# Render build containers may not resolve private PostgreSQL service DNS. Apply
# migrations when the web process starts instead, before serving any requests.
# Serialize Gunicorn workers with a PostgreSQL advisory lock so concurrent
# worker imports cannot race migrations.
setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connections


def _migrate_production_database():
    if settings.DEBUG or os.getenv("RUN_MIGRATIONS_ON_START", "true").lower() not in {"1", "true", "yes"}:
        return

    connection = connections["default"]
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [731942610584])
        try:
            call_command("migrate", interactive=False, verbosity=1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [731942610584])
    else:
        call_command("migrate", interactive=False, verbosity=1)


_migrate_production_database()
application = get_wsgi_application()
app = application

