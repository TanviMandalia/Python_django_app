from pathlib import Path
import os
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants

# =========================
# BASE CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# =========================
# SECURITY (CRITICAL)
# =========================

# Priority:
# 1. DJANGO_SECRET_KEY environment variable
# 2. SECRET_KEY environment variable (standard Django variable name)
# 3. Persistent .secret_key file (auto-generated on boot if missing)
# 4. Ephemeral cryptographic token fallback
SECRET_KEY = (os.getenv("DJANGO_SECRET_KEY") or os.getenv("SECRET_KEY", "")).strip()
if not SECRET_KEY:
    _secret_file = BASE_DIR / ".secret_key"
    try:
        if _secret_file.exists():
            SECRET_KEY = _secret_file.read_text(encoding="utf-8").strip()
        if not SECRET_KEY:
            import secrets
            SECRET_KEY = secrets.token_urlsafe(50)
            _secret_file.write_text(SECRET_KEY, encoding="utf-8")
    except Exception:
        import secrets
        SECRET_KEY = secrets.token_urlsafe(50)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Canonical production base URL for SEO and XML sitemap generation
CANONICAL_BASE_URL = os.getenv("CANONICAL_BASE_URL", "").strip().rstrip("/")

# Google Search Console ownership verification token/file
GOOGLE_SITE_VERIFICATION_TOKEN = os.getenv("GOOGLE_SITE_VERIFICATION_TOKEN", "").strip()
GOOGLE_SITE_VERIFICATION_FILE = os.getenv("GOOGLE_SITE_VERIFICATION_FILE", "").strip()

# =========================
# APPLICATIONS
# =========================

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
]


THIRD_PARTY_APPS = []

LOCAL_APPS = [
    "core.apps.CoreConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =========================
# MIDDLEWARE
# =========================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
    "core.middleware.SEORobotsTagMiddleware",
    "core.middleware.PublicVisitorTrackingMiddleware",
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
                "core.context_processors.seo_context",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"
ASGI_APPLICATION = "myproject.asgi.application"

# =========================
# PASSWORD VALIDATION
# =========================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_RESET_TIMEOUT = 900

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
# CACHE & SESSIONS
# =========================

CACHES = {
    "default": {
        "BACKEND": os.getenv(
            "CACHE_BACKEND",
            "django.core.cache.backends.locmem.LocMemCache",
        ),
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "physiorehab_sessionid"
REMEMBER_ME_DAYS = 14
REMEMBER_ME_EXPIRY = REMEMBER_ME_DAYS * 24 * 60 * 60  # 1,209,600 seconds (14 days)
SESSION_COOKIE_AGE = REMEMBER_ME_EXPIRY
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # Allows client-side auto-synchronization on form submit
CSRF_COOKIE_AGE = 86400 * 14  # 14 days, synchronized with session lifetime
CSRF_FAILURE_VIEW = "core.views.csrf_failure_view"

# =========================
# CSRF / TRUSTED ORIGINS
# =========================

_default_csrf_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "https://*.onrender.com",
    "https://physio-rehab-app.onrender.com",
]
_env_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "")
_combined_origins = _default_csrf_origins + [origin.strip() for origin in _env_csrf.split(",") if origin.strip()]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_combined_origins))

# =========================
# MESSAGES
# =========================

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# =========================
# AUTH
# =========================

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/client-dashboard/"
LOGOUT_REDIRECT_URL = "/"

# =========================
# EMAIL CONFIG
# =========================

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"PhysioRehab Clinic <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "PhysioRehab Clinic <noreply@physiorehab.com>",
)
SERVER_EMAIL = EMAIL_HOST_USER or "noreply@physiorehab.com"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", 15))
INBOUND_EMAIL_WEBHOOK_SECRET = os.getenv("INBOUND_EMAIL_WEBHOOK_SECRET", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# =========================
# PLATFORM EMAIL IDENTITY (TechCraft)
# =========================

PLATFORM_BRAND_NAME = "TechCraft"
PLATFORM_TAGLINE = "Healthcare SaaS Platform"
PLATFORM_DEFAULT_FROM_EMAIL = os.getenv("PLATFORM_DEFAULT_FROM_EMAIL", "techcraft1215@gmail.com")
PLATFORM_SUPPORT_EMAIL = os.getenv("PLATFORM_SUPPORT_EMAIL", "techcraft1215@gmail.com")
PLATFORM_SMTP_HOST = os.getenv("PLATFORM_SMTP_HOST", "smtp.gmail.com")
PLATFORM_SMTP_PORT = int(os.getenv("PLATFORM_SMTP_PORT", 587))
PLATFORM_SMTP_USER = os.getenv("PLATFORM_SMTP_USER", "techcraft1215@gmail.com")

# =========================
# CELERY
# =========================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

if CELERY_BROKER_URL:
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
else:
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
# PAYMENT / UPI
# =========================

CLINIC_UPI_ID = os.getenv("CLINIC_UPI_ID", "")
CLINIC_NAME = "Dr. Dhvani Patalia Physio Rehab"
CLINIC_PHONE = "+91 94095 10501"
CLINIC_EMAIL = "physio.rehab.guj@gmail.com"
CLINIC_WHATSAPP = "94095 10501"
DOCTOR_WHATSAPP_NUMBER = os.getenv("DOCTOR_WHATSAPP_NUMBER", os.getenv("CLINIC_WHATSAPP_NUMBER", "919409510501")).strip()

# =========================
# FILE UPLOADS
# =========================

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# =========================
# LOGGING
# =========================

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(levelname)s] %(asctime)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
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
        "level": os.getenv("LOG_LEVEL", "WARNING"),
    },
    "loggers": {
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
        "django.google_reviews": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- Google Business Profile & Places API Settings ---
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_PLACE_ID = os.getenv("GOOGLE_PLACE_ID", "").strip()
GOOGLE_REVIEW_URL = os.getenv("GOOGLE_REVIEW_URL", "").strip()
GOOGLE_REVIEWS_CACHE_TTL = int(os.getenv("GOOGLE_REVIEWS_CACHE_TTL", 86400))


