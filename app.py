"""
Compatibility WSGI entrypoint for Render and PaaS hosting environments.

When Render deploys a Python Web Service without an explicit custom start command,
it executes the default command:
    `gunicorn app:app`

This module exposes `app` (and `application`) as the Django WSGI callable,
ensuring zero-configuration deployments succeed immediately.
"""
import os
import sys

# Ensure repository root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Ensure production settings are loaded by default on Render/production
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings.production")

from myproject.wsgi import application  # noqa: E402

# Expose 'app' alias for `gunicorn app:app`
app = application

__all__ = ["app", "application"]
