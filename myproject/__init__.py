"""
Place this at: myproject/__init__.py
Ensures the Celery app is loaded when Django starts, so @shared_task
decorators everywhere pick it up automatically.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)