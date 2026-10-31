from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1")

# ------------------------------------------------------------------------------
# Hosts & CSRF Origins
# ------------------------------------------------------------------------------
allowed_hosts_raw = os.getenv("ALLOWED_HOSTS")
render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
vercel_url = os.getenv("VERCEL_URL", "").strip()

if allowed_hosts_raw:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]
elif render_hostname:
    ALLOWED_HOSTS = [render_hostname, f".{render_hostname}", "localhost", "127.0.0.1", "physio-rehab-app.onrender.com"]
elif vercel_url:
    ALLOWED_HOSTS = [vercel_url, f".{vercel_url}", ".vercel.app", "localhost", "127.0.0.1"]
else:
    # Default fallback for Render, Vercel deployment & local verification
    ALLOWED_HOSTS = [
        "physio-rehab-app.onrender.com",
        ".onrender.com",
        ".vercel.app",
        "localhost",
        "127.0.0.1",
    ]

csrf_origins_raw = os.getenv("CSRF_TRUSTED_ORIGINS")
if csrf_origins_raw:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_raw.split(",") if o.strip()]
else:
    extra_origins = [
        f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith("*") and not h.startswith(".")
    ] + [
        "https://*.onrender.com",
        "https://physio-rehab-app.onrender.com",
        "https://*.vercel.app",
    ]
    if vercel_url:
        extra_origins.append(f"https://{vercel_url}")
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS + extra_origins))

# Always ensure .vercel.app is included if running on Vercel
if os.getenv("VERCEL") or vercel_url:
    if ".vercel.app" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".vercel.app")
    if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")
# ------------------------------------------------------------------------------
# Canonical Production Domain for SEO & Sitemap
# ------------------------------------------------------------------------------
if not CANONICAL_BASE_URL:
    if vercel_url:
        CANONICAL_BASE_URL = f"https://{vercel_url}"
    else:
        primary_host = next((h for h in ALLOWED_HOSTS if not h.startswith("*") and not h.startswith(".")), "physio-rehab-app.onrender.com")
        CANONICAL_BASE_URL = f"https://{primary_host}"
# ------------------------------------------------------------------------------
# Security & SSL / HTTPS Headers
# ------------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Serverless (Vercel) lambdas are ephemeral and should not require DB session table lookups for static/public visitors
if os.getenv("VERCEL"):
    SESSION_ENGINE = os.getenv("SESSION_ENGINE", "django.contrib.sessions.backends.signed_cookies")

SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "True").lower() == "true"

# ------------------------------------------------------------------------------
# Storage Configuration:
# - Static Files: WhiteNoise CompressedManifestStaticFilesStorage
# - Media / Attachments: Cloudflare R2 (S3-compatible private bucket) when R2_* 
#   variables are provided, with fallback to local FileSystemStorage.
# ------------------------------------------------------------------------------
r2_bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("AWS_STORAGE_BUCKET_NAME")
if r2_bucket:
    r2_account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
    r2_endpoint = os.getenv("R2_ENDPOINT_URL")
    if not r2_endpoint and r2_account_id:
        r2_endpoint = f"https://{r2_account_id}.r2.cloudflarestorage.com"

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": r2_bucket,
                "endpoint_url": r2_endpoint,
                "access_key": os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
                "secret_key": os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
                "default_acl": "private",
                "querystring_auth": True,
                "querystring_expire": int(os.getenv("R2_PRESIGNED_EXPIRY", "3600")),
                "signature_version": "s3v4",
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

WHITENOISE_MANIFEST_STRICT = False

# ------------------------------------------------------------------------------
# Production Database Configuration
# Supports DATABASE_URL with fallback to individual DB_* parameters.
# Never silently falls back to SQLite or an unintended database.
# ------------------------------------------------------------------------------
database_url = os.getenv("DATABASE_URL")
db_name = os.getenv("DB_NAME")

if database_url:
    # Serverless (Vercel) cannot maintain pooled TCP connections across lambda freeze cycles
    conn_max_age = 0 if os.getenv("VERCEL") else int(os.getenv("DB_CONN_MAX_AGE", "600"))
    db_config = dj_database_url.parse(
        database_url,
        conn_max_age=conn_max_age,
        conn_health_checks=True,
        ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() == "true",
    )
    # Ensure PgBouncer / Neon / Supabase connection pooler compatibility
    db_config["DISABLE_SERVER_SIDE_CURSORS"] = True
    db_config.setdefault("OPTIONS", {})
    # Fail fast on unreachable host to prevent hitting Vercel's 10s lambda timeout
    db_config["OPTIONS"].setdefault("connect_timeout", int(os.getenv("DB_CONNECT_TIMEOUT", "5")))
    DATABASES = {"default": db_config}
elif db_name and not os.getenv("VERCEL"):
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
            "OPTIONS": {
                "sslmode": os.getenv("DB_SSLMODE", "require"),
            },
        }
    }
else:
    # On Vercel, the application directory is read-only (/var/task).
    # Use the system temp directory for writable SQLite database when DATABASE_URL is not yet configured.
    if os.getenv("VERCEL"):
        import tempfile
        sqlite_db_path = str(Path(tempfile.gettempdir()) / "db.sqlite3")
    else:
        sqlite_db_path = str(BASE_DIR / "db.sqlite3")

    import logging
    logging.getLogger("django.production").warning(
        "DATABASE_URL was not set in environment variables. "
        f"Falling back to local SQLite database ({sqlite_db_path}). "
        "To connect your PostgreSQL database: Add DATABASE_URL to your Vercel/Render Environment Variables."
    )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_db_path,
        }
    }


# ------------------------------------------------------------------------------
# Production Email Configuration
# Priority:
# 1. Resend REST API (HTTPS Port 443) when RESEND_API_KEY is provided:
#    Reliable delivery bypassing cloud firewall SMTP blocks (e.g. Render Free).
# 2. Standard SMTP backend if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are provided.
# 3. Explicit EMAIL_BACKEND environment variable if provided.
#    (Console backend is forbidden in production unless ALLOW_CONSOLE_EMAIL_IN_PRODUCTION is True).
# 4. Strict validation preventing accidental fallback to console backend in production.
# ------------------------------------------------------------------------------
email_backend_env = os.getenv("EMAIL_BACKEND", "").strip()
resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
email_user = os.getenv("EMAIL_HOST_USER", "").strip()
email_password = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
allow_console = os.getenv("ALLOW_CONSOLE_EMAIL_IN_PRODUCTION", "False").lower() in ("true", "1")

if resend_api_key:
    EMAIL_BACKEND = "core.email_backend.ResendEmailBackend"
    RESEND_API_KEY = resend_api_key
elif email_user and email_password:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif email_backend_env:
    EMAIL_BACKEND = email_backend_env
elif allow_console:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # Safe fallback allowing zero-downtime builds, migrations, and checks (e.g. Render build.sh)
    # while notifying administrators in logs that live outbound delivery credentials should be configured.
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    import logging
    logging.getLogger("django.production").warning(
        "Production email backend is currently unconfigured (using dummy backend). "
        "To enable real delivery: Set RESEND_API_KEY (recommended for Render HTTPS delivery) "
        "or EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in your hosting dashboard."
    )


