Implementation Plan
PhysioRehab Django Project Reorganisation
Reorganise the existing Django project's file structure following the 6 steps you outlined, without rewriting any existing logic.

User Review Required
IMPORTANT

control/ app is empty — It contains only two Celery exchange files (celery.exchange, celery.pidbox.exchange), no Python code. It's not a Django app at all — just stale Celery broker artefacts. I'll delete this folder entirely rather than rename it. Please confirm.

IMPORTANT

Two competing settings files exist: 
myproject/settings.py
 (the active one, referenced by manage.py, wsgi.py, asgi.py, celery.py) and 
core/settings.py
 (stale — references physio_rehab.urls which doesn't exist). I will merge the best parts of core/settings.py into the new split settings and then delete core/settings.py. Please confirm.

IMPORTANT

physio_rehab/ is an empty directory (only __pycache__). This is dead — I'll delete it.

WARNING

Filename with spaces: 
core/context processors.py
 and 
core/0001 initial.py
 have spaces in their names. context processors.py is real code referenced by core/settings.py as core.context_processors.unread_notifications. I'll rename it to context_processors.py (underscore). The 0001 initial.py is a stale duplicate of the real migration in migrations/0001_initial.py — I'll delete it.

WARNING

core/ has both views.py (152KB monolith) and an empty views/ directory, and both forms.py and an empty forms/ directory. I will NOT split these in this reorganisation (it's a separate refactoring task). I'll clean up the empty directories.

Open Questions
IMPORTANT

Skipping the apps/ move: Since control/ is empty (not a real Django app) and core is the only Django app, creating an apps/ directory with a single app inside would add nesting for no benefit and require updating every import, middleware path, template tag, migration reference, and URL config. I recommend keeping core/ at the project root. Would you like me to proceed with the apps/ move regardless?

Proposed Changes
Step 1 — Clean Junk
Delete or git-untrack these files/folders:

Path	Action	Reason
.agents/	Delete	AI working directory
artifacts/	Delete	Replit mockup sandbox, not project code
attached_assets/	Delete	Error paste files and a screenshot from debugging
control/	Delete	Empty — only Celery exchange files, not a Django app
physio_rehab/	Delete	Empty dir, only __pycache__/
celery_queue/	Git-ignore	Runtime Celery filesystem broker queue (auto-created by settings)
ls	Delete	Empty junk file
processed	Delete	Stale Celery message file
core/0001 initial.py	Delete	Duplicate of migrations/0001_initial.py, has space in name
core/settings.py	Delete	Stale settings referencing non-existent physio_rehab module
core/tests.py	Delete	Contains only from django.test import TestCase — we'll create proper tests
core/forms.py	Delete	Contains only from django import forms — empty stub
db_backup.sqlite3	Git-untrack	Database backup shouldn't be in VCS
.venv/, venv/	Git-untrack	Virtual environments
media/	Git-untrack	User uploads
staticfiles/	Git-untrack	collectstatic output
profile_photos/	Git-untrack	Should be inside media/ (already exists there)
logs/	Git-untrack	Runtime logs
.replit	Delete	Replit config, not needed
Empty __pycache__/ dirs in core/views/, core/forms/, core/services/, core/tests/	Delete	Empty package dirs with only __pycache__
.gitignore additions

# Celery filesystem broker queue
celery_queue/
# Database backups
db_backup.sqlite3
*.sqlite3-bak
# Profile photos at root (should be in media/)
profile_photos/
Step 2 — Reorganise Apps
Recommendation: Skip the apps/ directory (see Open Questions above). core is the only app — moving it into apps/core/ would force changes to:

Every from core.xxx import in 10+ files
All middleware paths in settings (core.middleware.XxxMiddleware)
INSTALLED_APPS
Context processor paths
Template tag loading ({% load custom_filters %})
Celery autodiscovery
URL includes
Migration history references
If you still want apps/, I'll do it, but it adds complexity with no structural benefit for a single-app project.

What I WILL do:

Rename core/context processors.py → core/context_processors.py (fix space in filename)
Remove empty core/views/, core/forms/, core/services/, core/tests/ directories (they only have __pycache__/)
Add core/context_processors.py to the template context processors in settings (currently missing from myproject/settings.py)
Step 3 — Split settings.py
Split 
myproject/settings.py
 into a settings package, merging in the better patterns from the stale core/settings.py:

[DELETE] 
settings.py
Replaced by the settings package below.

[NEW] myproject/settings/__init__.py
python

# Settings package — import dev by default for manage.py convenience.
# Production deployments should set DJANGO_SETTINGS_MODULE=myproject.settings.production
[NEW] myproject/settings/base.py
All shared config merged from both settings files. Key changes:

SECRET_KEY from env (kept)
BASE_DIR adjusted: Path(__file__).resolve().parent.parent.parent (one more .parent since we're deeper)
Merges CACHE config, SESSION config, MESSAGE_TAGS, SECURITY headers, PASSWORD_RESET_TIMEOUT, file upload limits from core/settings.py
Adds core.context_processors.unread_notifications to template context processors
Keeps all Celery config
Keeps all Razorpay config
Keeps all logging config
DATABASE is not set here (left to dev/production)
[NEW] myproject/settings/dev.py
python

from .base import *
DEBUG = True
DATABASES = { "default": { "ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3" } }
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # optional override
[NEW] myproject/settings/production.py
python

from .base import *
DEBUG = False
DATABASES = { "default": { ... PostgreSQL from env vars ... } }
# HSTS, SSL redirect, etc.
[MODIFY] 
manage.py
Change default DJANGO_SETTINGS_MODULE from myproject.settings → myproject.settings.dev

[MODIFY] 
wsgi.py
Change default to myproject.settings.production

[MODIFY] 
asgi.py
Change default to myproject.settings.production

[MODIFY] 
celery.py
Change default to myproject.settings.production

Step 4 — Fix requirements.txt
[MODIFY] 
requirements.txt
Remove 7 duplicate lines (Django, gunicorn, openpyxl, pillow, reportlab, requests, stripe all appear twice)
Pin razorpay to a version (razorpay==1.4.2)
Add python-dotenv (used by settings but not listed)
Add celery (imported but not listed)
Sort alphabetically
Step 5 — Create Missing Files
[NEW] README.md
Setup instructions, env variables list, how to run dev server, how to run Celery worker.

[NEW] .env.example
All environment variables with placeholder values (SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DB_, EMAIL_, RAZORPAY_, CELERY_, CLINIC_UPI_ID).

[NEW] tests/__init__.py
Empty file to create the tests package.

[NEW] tests/test_placeholder.py
One simple passing test to confirm pytest works.

[NEW] .github/workflows/ci.yml
GitHub Actions workflow: runs pytest and flake8 on push/PR.

[NEW] setup.cfg
Minimal config for flake8 and pytest (tells pytest where to find Django settings).

Step 6 — Final Check
Show the complete new folder tree after all changes.

Verification Plan
Automated Tests
bash

# Verify settings load correctly
python manage.py check --settings=myproject.settings.dev
# Verify migrations are intact
python manage.py showmigrations --settings=myproject.settings.dev
# Run the placeholder test
python -m pytest tests/test_placeholder.py -v
Manual Verification
Confirm the dev server starts: python manage.py runserver
Confirm the folder tree matches expectations
Confirm no import errors when loading the app