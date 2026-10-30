"""
WSGI config for myproject project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from pathlib import Path
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings.production')

# Auto-initialize fallback SQLite database in temp directory if running on Vercel without external DB
if os.getenv("VERCEL") and not os.getenv("DATABASE_URL"):
    import tempfile
    _tmp_db = Path(tempfile.gettempdir()) / "db.sqlite3"
    if not _tmp_db.exists() or _tmp_db.stat().st_size == 0:
        try:
            import django
            django.setup()
            from django.core.management import call_command
            call_command("migrate", interactive=False, verbosity=0)
        except Exception as _e:
            import logging
            logging.getLogger("django.production").warning("Auto-migration on Vercel SQLite failed: %s", _e)

application = get_wsgi_application()
app = application
