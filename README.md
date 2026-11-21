# PhysioRehab Clinic Management Platform

A Django application for clinic operations and patient access. It includes public appointment booking, role-specific dashboards, clinic and patient records, clinical session notes, staff operations, payment tracking, notifications, and configurable email delivery.

## Features

- **Role-based portals:** Platform super administrators, clinic administrators, physiotherapists and staff, and patients.
- **Clinic data boundaries:** Tenant-aware query and authorization helpers in `core/tenancy.py`.
- **Appointments:** Public booking requests, clinic review and confirmation, scheduling, and one-hour email reminders through `send_appointment_reminders`.
- **Patient care:** Patient profiles, treatment progress, session notes, appointment history, and clinic messaging.
- **Clinic operations:** Staff attendance and leave, salary records, payment logs, analytics, notifications, and subscription entitlements.
- **Email:** Separate platform and clinic sender identities, per-account SMTP configuration, delivery logging, and optional Gmail OAuth for Gmail API delivery and inbox synchronization. SMTP sends mail; inbox receiving/synchronization uses Gmail OAuth/API.
- **Security controls:** Django authentication and sessions, CSRF protection, role checks, tenant authorization, secure upload validation, and authenticated access to message attachments.
- **Public site and SEO:** Service and contact pages, Google review links, sitemap, robots rules, canonical URLs, and structured data.

## Technology

- Python 3.12+
- Django 6
- PostgreSQL for production; SQLite or PostgreSQL for development and CI
- Gunicorn and WhiteNoise for production serving
- Optional Celery/Redis integrations
- Django templates, CSS, and JavaScript

## Local development

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE = "myproject.settings.dev"
$env:DB_ENGINE = "django.db.backends.sqlite3"
python manage.py migrate
python manage.py runserver
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=myproject.settings.dev
export DB_ENGINE=django.db.backends.sqlite3
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. To use PostgreSQL locally instead, configure `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` for your local database. `myproject.settings.dev` uses SQLite only when `DB_ENGINE` is set to SQLite, or when CI/`USE_SQLITE` requests it.

`myproject.settings.production` requires a PostgreSQL `DATABASE_URL` or a complete PostgreSQL `DB_*` configuration. It deliberately does not fall back to SQLite. Do not use production settings for a quick local run unless its required secrets and database are configured.

## Email configuration

The application supports separate platform and clinic mail accounts. SMTP credentials can be configured through environment variables or the authorized email settings in the application. Keep real credentials in a secret manager or hosting environment; never commit `.env`.

For Gmail SMTP, use the account’s App Password with STARTTLS on port `587`. SMTP is an outbound sending protocol; it does not provide inbox synchronization. Gmail inbox synchronization uses the optional Google OAuth integration. The OAuth client needs the matching callback URL, and each mailbox must authorize the app.

Some hosting plans block outbound SMTP. In particular, Render Free services cannot connect to SMTP ports. On such a plan, use an enabled email API or Gmail OAuth for sending, or use a host that permits outbound SMTP. Check `.env.example` for the current environment-variable template and provider notes.

For Gmail OAuth, configure these variables only when using the integration:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `FIELD_ENCRYPTION_KEY` (Fernet key used to protect OAuth credentials at rest)
- `GMAIL_INBOUND_MAILBOXES` (mailboxes allowed for synchronization)

The production Gmail callback URL is:

```text
https://<your-domain>/admin-settings/gmail/callback/
```

Add the exact URL to the Google OAuth client’s authorized redirect URIs. Inbox synchronization also needs the corresponding Gmail API scopes and mailbox authorization. Pub/Sub push notifications are optional; the `sync_gmail` management command can also synchronize configured inboxes.

## Production deployment

The repository includes `build.sh`, `Procfile`, and `render.yaml`. The Render Blueprint describes a Django web service, PostgreSQL database, and scheduled appointment-reminder job. Review the plan and environment values in `render.yaml` before using it; Render may provision resources or incur charges when a Blueprint is applied.

Expected web service commands:

```bash
./build.sh
gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
```

Set production secrets and service-specific values in the hosting dashboard, including:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (PostgreSQL connection URL)
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `CANONICAL_BASE_URL`
- A working email provider configuration for required notifications

Use HTTPS and configure the public hostname in both `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. Run migrations against the production database as part of the deployment procedure, provision the initial administrator securely, and confirm the application health endpoint `/healthz`. Keep database backups and verify that they can be restored. A domain name is separate from hosting and must be configured as a custom domain with the hosting provider.

The free Render web-service plan can spin down when idle, which causes a delay on the next request. A custom domain does not prevent this; select a paid always-on service plan if you need to avoid idle spin-downs.

## Login sessions

Authenticated sessions use a rolling 14-day lifetime and are not ended by a 30-minute idle timeout. Activity refreshes the expiry; users can explicitly end the session with **Log Out**. The login form supports browser password-manager autofill through standard autocomplete attributes. The application does not store users’ readable passwords for autofill.

## Useful management commands

```bash
# Apply schema migrations
python manage.py migrate

# Collect production static assets
python manage.py collectstatic --noinput

# Send one-hour appointment reminders (also configured as a Render cron job)
python manage.py send_appointment_reminders

# Preview or run the expired OTP log cleanup
python manage.py cleanup_expired_otp_logs --dry-run
python manage.py cleanup_expired_otp_logs

# Synchronize configured Gmail inboxes (OAuth required)
python manage.py sync_gmail
```

## Tests and CI

GitHub Actions runs the Django test suite with pytest and performs Python lint checks on pushes and pull requests to `main` or `master`.

Run the suite locally with:

```powershell
pip install pytest pytest-django flake8
$env:DJANGO_SETTINGS_MODULE = "myproject.settings.dev"
$env:DB_ENGINE = "django.db.backends.sqlite3"
pytest
```

On Linux or macOS, export the settings before running pytest:

```bash
pip install pytest pytest-django flake8
export DJANGO_SETTINGS_MODULE=myproject.settings.dev
export DB_ENGINE=django.db.backends.sqlite3
pytest
```

For a critical-syntax lint check:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## Repository layout

```text
core/                   Django application, models, views, email, and commands
core/migrations/        Database schema migrations
myproject/settings/     Shared, development, and production settings
templates/              Django HTML templates
static/                 Source CSS, JavaScript, and images
tests/                  Automated test suites
.github/workflows/      CI and scheduled workflow definitions
build.sh                Production build steps
render.yaml             Render Blueprint
.env.example            Environment variable template (placeholder values only)
```

## Security notes

- Never commit `.env`, database URLs, OAuth client secrets, SMTP App Passwords, encryption keys, or production exports.
- Use separate credentials for each email identity and restrict access to production settings.
- Do not put real patient information or credentials in issues, logs, screenshots, or test fixtures.
- Review local privacy, healthcare, and data-retention obligations before using the application with real patient data. This repository documentation is not a compliance certification.

