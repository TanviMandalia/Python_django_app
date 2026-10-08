from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

# ------------------------------------------------------------------------------
# Hosts & CSRF Origins
# ------------------------------------------------------------------------------
allowed_hosts_raw = os.getenv("ALLOWED_HOSTS")
if not allowed_hosts_raw:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS environment variable is required in production (e.g. 'domain.com,www.domain.com')."
    )
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]

csrf_origins_raw = os.getenv("CSRF_TRUSTED_ORIGINS")
if csrf_origins_raw:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_raw.split(",") if o.strip()]
elif not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith("*") and not h.startswith(".")
    ]

# ------------------------------------------------------------------------------
# Security & SSL / HTTPS Headers
# ------------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "True").lower() == "true"

# ------------------------------------------------------------------------------
# Static Files (WhiteNoise)
# ------------------------------------------------------------------------------
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ------------------------------------------------------------------------------
# Production Database Configuration
# Supports DATABASE_URL with fallback to individual DB_* parameters.
# Never silently falls back to SQLite or an unintended database.
# ------------------------------------------------------------------------------
database_url = os.getenv("DATABASE_URL")
db_name = os.getenv("DB_NAME")

if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "600")),
            conn_health_checks=True,
        )
    }
elif db_name:
    db_password = os.getenv("DB_PASSWORD")
    if db_password is None:
        raise ImproperlyConfigured("DB_PASSWORD is required when configuring production PostgreSQL via DB_* variables.")
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": db_name,
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": db_password,
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "600")),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    raise ImproperlyConfigured(
        "Production database misconfigured: either DATABASE_URL or DB_NAME (with DB_USER, DB_PASSWORD, DB_HOST, DB_PORT) must be set."
    )

