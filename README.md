# PhysioRehab Clinic - Django Web Application

A management system and client portal for the PhysioRehab Clinic, providing appointment scheduling, patient tracking, staff management, session notes, daily tasks, automated email notifications, and online payment integrations (Razorpay and Stripe).

## Project Structure

```text
Python_django_app/
├── core/                   # Main Django application
│   ├── management/         # Management commands (reminders, shift checks)
│   ├── migrations/         # Database migrations
│   ├── templatetags/       # Custom template tags and filters
│   ├── models.py           # Domain models
│   ├── views.py            # Application views
│   ├── urls.py             # Route definitions
│   └── ...
├── myproject/              # Project configuration directory
│   ├── settings/           # Modular environment settings
│   │   ├── __init__.py     # Settings package entrypoint
│   │   ├── base.py         # Shared base configuration
│   │   ├── dev.py          # Local development configuration (SQLite)
│   │   └── production.py   # Production configuration (PostgreSQL & security headers)
│   ├── asgi.py             # ASGI configuration
│   ├── celery.py           # Celery background tasks setup
│   ├── urls.py             # Root URL routing
│   └── wsgi.py             # WSGI configuration
├── static/                 # Static assets (CSS, JS, images)
├── templates/              # HTML templates
├── tests/                  # Automated test suite
├── .env.example            # Sample environment variables template
├── manage.py               # Django administrative CLI
└── requirements.txt        # Python package dependencies
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Virtualenv (`python -m venv .venv`)
- Redis (optional for development; Celery falls back to local filesystem queue if unconfigured)

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your secrets:
```bash
cp .env.example .env
```

### 5. Apply Migrations & Create Superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Run the Development Server
```bash
python manage.py runserver
```
Navigate to `http://127.0.0.1:8000/`.

---

## Running Celery Worker

For asynchronous email notifications and background tasks:
```bash
celery -A myproject worker -l info
```

---

## Running Tests

Run the test suite via `pytest`:
```bash
pytest
```

Or with Django test runner:
```bash
python manage.py test tests
```

---

## Environment Variables

| Variable | Description | Default / Example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django cryptographic signing key | Required |
| `DEBUG` | Enable/disable debug mode | `True` in dev |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF protection | `http://localhost:8000` |
| `EMAIL_BACKEND` | Django email backend class | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP server address | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Enable TLS encryption | `True` |
| `EMAIL_HOST_USER` | Email username / sender address | Required for SMTP |
| `EMAIL_HOST_PASSWORD` | Email app password | Required for SMTP |
| `EMAIL_TIMEOUT` | SMTP socket timeout in seconds | `15` |
| `RAZORPAY_KEY_ID` | Razorpay API key | `rzp_test_...` |
| `RAZORPAY_KEY_SECRET` | Razorpay API secret key | Secret |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Webhook secret | Secret |
| `CLINIC_UPI_ID` | Clinic UPI address for direct payments | `physiorehab@upi` |
| `CELERY_BROKER_URL` | Celery broker URL (Redis or RabbitMQ) | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result store URL | `redis://localhost:6379/0` |
| `DB_ENGINE` | Database engine (production) | `django.db.backends.postgresql` |
| `DB_NAME` | Database name | `physiorehab_db` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | Secret |
| `DB_HOST` | Database server host | `localhost` |
| `DB_PORT` | Database server port | `5432` |
