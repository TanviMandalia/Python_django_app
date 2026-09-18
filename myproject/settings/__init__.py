"""
Settings package initialization.
Defaults to dev settings for local manage.py execution convenience.
Production environments should set DJANGO_SETTINGS_MODULE=myproject.settings.production
"""
import os

env_setting = os.getenv("DJANGO_SETTINGS_MODULE", "myproject.settings.dev")
if env_setting == "myproject.settings" or env_setting.endswith(".settings"):
    from .dev import *
