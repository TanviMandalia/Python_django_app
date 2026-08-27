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

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-default-development-key-physiorehab-2026"
)

DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,testserver"
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
                "core.context_processors.unread_notifications",
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

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

# =========================
# CSRF / TRUSTED ORIGINS
# =========================

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost,http://127.0.0.1"
).split(",")

# =========================
# EMAIL CONFIG
# =========================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "physiorehab.clinic.demo@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = f"PhysioRehab Clinic <{EMAIL_HOST_USER}>"
SERVER_EMAIL = EMAIL_HOST_USER
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", 15))

# =========================
# CELERY (background & bulk email)
# =========================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

if CELERY_BROKER_URL:
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
else:
    # Filesystem broker fallback for local dev
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
    CELERY_RESULT_BACKEND = None

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
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

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_SampleKeyId12345")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "SampleKeySecret12345")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

CLINIC_UPI_ID = os.getenv("CLINIC_UPI_ID", "physiorehab@upi")

# =========================
# LOGGING
# =========================

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
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },
    "loggers": {
        "core": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}