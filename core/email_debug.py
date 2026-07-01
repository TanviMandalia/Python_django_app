"""
Manual email test endpoint — DEVELOPMENT ONLY.

This replaces the send_demo_email() debug view that was previously (and
incorrectly) sitting inside models.py. It's isolated here and gated behind
DEBUG so it can never be reached in production, even if someone forgets to
remove it from urls.py.

To wire it up in urls.py (only add this in your DEBUG/dev urlpatterns):
    from . import email_debug
    path("email-test/", email_debug.send_demo_email, name="email_test"),
"""

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required


@login_required
def send_demo_email(request):
    if not settings.DEBUG:
        # Hard stop in production regardless of urls.py wiring.
        return HttpResponseForbidden("Not available in production.")

    if not request.user.is_superuser:
        return HttpResponseForbidden("Admins only.")

    from .tasks import send_email_task

    target = request.user.email or settings.EMAIL_HOST_USER
    send_email_task.delay(
        "Test Email",
        "Hello from Django — this is a manual test send.",
        [target],
    )
    return HttpResponse(f"Test email queued to {target}. Check the Celery worker log.")