from pathlib import Path
import os
from dotenv import load_dotenv

# =========================
# BASE CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# =========================
# SECURITY (CRITICAL)
# =========================

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise Exception("DJANGO_SECRET_KEY is missing in environment variables")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1"
).split(",")

# =========================
# APPLICATIONS
# =========================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

# =========================
# MIDDLEWARE
# =========================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # custom middleware
    "core.middleware.UpdateLastSeenMiddleware",
    "core.middleware.SessionTimeoutMiddleware",
    "core.middleware.LoginAttemptMiddleware",
    "core.middleware.SubscriptionGateMiddleware",
    "core.middleware.PreventBackAfterLogoutMiddleware",
]

ROOT_URLCONF = "myproject.urls"

# =========================
# TEMPLATES
# =========================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"

# =========================
# DATABASE
# =========================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# =========================
# PASSWORD VALIDATION
# =========================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# INTERNATIONALIZATION
# =========================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# =========================
# STATIC / MEDIA
# =========================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# SECURITY HEADERS (PRODUCTION SAFE)
# =========================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HTTPS settings (ENABLE IN PRODUCTION)
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

# =========================
# CSRF / TRUSTED ORIGINS
# =========================

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost"
).split(",")

# =========================
# EMAIL CONFIG (PRODUCTION SAFE)
# =========================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    raise Exception("Email credentials missing in environment variables")

DEFAULT_FROM_EMAIL = f"PhysioRehab Clinic <{EMAIL_HOST_USER}>"
SERVER_EMAIL = EMAIL_HOST_USER

# Without a timeout, a hung SMTP connection can block a request/worker
# indefinitely. 10-15s is plenty for a normal SMTP handshake.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", 15))

# =========================
# CELERY (background & bulk email)
# =========================
# Production / Linux: use Redis (or another real broker) — set
# CELERY_BROKER_URL in .env to something like redis://localhost:6379/0
# and remove/ignore the filesystem fallback below.
#
# Local Windows dev without Docker/WSL/Memurai installed: the filesystem
# transport below needs NO server at all — it just uses folders on disk as
# a queue. It's for getting unblocked locally only; do not use it in
# production (no real concurrency guarantees, not for multi-machine setups).

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

if CELERY_BROKER_URL:
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
else:
    # No broker configured in .env -> fall back to filesystem transport.
    #
    # IMPORTANT: per Kombu's own filesystem transport docs, the producer
    # writes new messages into data_folder_in, while the consumer reads
    # messages from data_folder_out. Kombu expects producer and consumer to
    # be configured with those two OPPOSITE to each other (a true "in" vs
    # "out" pair) when they're separate deployments. But here, the Django
    # app (producer, e.g. a view or `shell -c`) and the Celery worker
    # (consumer) both load this exact same settings.py — so if we give them
    # different folders, the producer writes into "in" and the worker only
    # ever polls "out", and the two never meet. The fix is to point both
    # at the SAME single folder, so whichever process writes a task file,
    # the other process (polling that same folder) picks it up.
    _CELERY_QUEUE_DIR = BASE_DIR / "celery_queue"
    _CELERY_QUEUE_MESSAGES = _CELERY_QUEUE_DIR / "messages"
    _CELERY_QUEUE_MESSAGES.mkdir(parents=True, exist_ok=True)
    (_CELERY_QUEUE_DIR / "processed").mkdir(parents=True, exist_ok=True)

    CELERY_BROKER_URL = "filesystem://"
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "data_folder_in": str(_CELERY_QUEUE_MESSAGES),
        "data_folder_out": str(_CELERY_QUEUE_MESSAGES),
        "data_folder_processed": str(_CELERY_QUEUE_DIR / "processed"),
        "store_processed": True,
    }
    # No result backend here on purpose: a "file://C:\Users\..." URL breaks
    # on Windows because urllib misreads the drive letter's ":" as a port
    # separator. We don't need results for fire-and-forget email tasks
    # (nothing in this project calls .get() on a task result), so it's
    # simplest and most robust to just not configure one at all.
    CELERY_RESULT_BACKEND = None

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Don't let one huge bulk-email task hog a worker forever.
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 360

# =========================
# AUTH
# =========================

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/client-dashboard/"
LOGOUT_REDIRECT_URL = "/"

# =========================
# RAZORPAY / PAYMENT
# =========================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

CLINIC_UPI_ID = os.getenv("CLINIC_UPI_ID", "")

# =========================
# LOGGING (IMPORTANT FOR PRODUCTION)
# =========================

# Ensure the logs directory exists before the file handler tries to open
# app.log — without this, a fresh clone/deploy (no logs/ folder yet)
# crashes Django/Celery at startup with "Unable to configure handler 'file'".
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "app.log",
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },
    "loggers": {
        # Bumps email-related logging to INFO so send/failure/bulk-summary
        # lines from email_utils.py and tasks.py actually show up, instead
        # of being swallowed by the root WARNING level above.
        "core.email_utils": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.tasks": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}