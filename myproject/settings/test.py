"""
Test settings module (`test.py`).
Provides isolated, deterministic test configuration with in-memory database,
fast password hashing, and in-memory email delivery.
"""
import os
from .base import *  # noqa: F401, F403

DEBUG = False
TESTING = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Ensure in-memory database for clean test isolation if not using PostgreSQL service
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Strict locmem email backend for automated testing (no external network or real delivery)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
