from .base import *

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DB_ENGINE = os.getenv("DB_ENGINE", "")
USE_SQLITE = (
    DB_ENGINE == "django.db.backends.sqlite3"
    or os.getenv("CI") is not None
    or os.getenv("USE_SQLITE", "").lower() in ("true", "1", "yes")
)

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE or "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "physio_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5433"),
        }
    }

# Optional dev overrides for email: console backend if SMTP not desired
if os.getenv("DEV_EMAIL_CONSOLE", "False").lower() == "true":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
