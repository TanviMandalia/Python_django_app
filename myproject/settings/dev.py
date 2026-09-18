from .base import *

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Optional dev overrides for email: console backend if SMTP not desired
if os.getenv("DEV_EMAIL_CONSOLE", "False").lower() == "true":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
