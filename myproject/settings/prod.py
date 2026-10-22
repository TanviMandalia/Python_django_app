"""
Production settings alias module (`prod.py`).
Allows using DJANGO_SETTINGS_MODULE=myproject.settings.prod interchangeably with
DJANGO_SETTINGS_MODULE=myproject.settings.production.
"""
from .production import *  # noqa: F401, F403
