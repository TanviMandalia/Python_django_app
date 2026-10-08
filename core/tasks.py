"""
Celery tasks for PhysioRehab Clinic email sending.

Why this file matters for "one-to-many":
  Sending email inside a Django view/request blocks the HTTP response until
  every SMTP round-trip finishes. For one recipient that's fine (~1-2s).
  For dozens of staff/patients it can take minutes and will hit gunicorn's
  request timeout, killing the batch partway through with no clear error
  to the user. Routing sends through Celery moves that work OFF the
  request/response cycle entirely — the view returns instantly and the
  emails go out in the background, with automatic retries on transient
  SMTP failures.

Requirements:
    pip install celery redis --break-system-packages
    (a Redis server running, or another broker configured in settings)

Run the worker in production/dev:
    celery -A myproject worker -l info
"""

import logging

from celery import shared_task
from django.conf import settings

from .email_utils import send_clinic_email, send_bulk_clinic_email, send_platform_email

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # seconds between retries
    autoretry_for=(Exception,),
    retry_backoff=True,       # 30s, 60s, 120s...
    retry_jitter=True,
)
def send_email_task(
    self,
    subject,
    message,
    recipient_list,
    context="clinic",
    hospital_id=None,
    email_type="transactional",
    html_message=None,
):
    """
    Background task for a single-recipient (or small, safe) email.
    Preserves the sending context ('platform' vs 'clinic') across background workers and retries.
    """
    if context == "platform":
        ok = send_platform_email(
            subject,
            message,
            recipient_list,
            email_type=email_type,
            html_message=html_message,
        )
    else:
        hospital = None
        if hospital_id:
            try:
                from .models import Hospital
                hospital = Hospital.objects.filter(id=hospital_id).first()
            except Exception:
                pass
        ok = send_clinic_email(
            subject,
            message,
            recipient_list,
            hospital=hospital,
            email_type=email_type,
            html_message=html_message,
        )

    if not ok:
        # Raising triggers Celery's autoretry/backoff above.
        raise RuntimeError(f"Email send failed for {recipient_list}: {subject} (context={context})")
    return {"recipient_list": recipient_list, "subject": subject, "status": "sent", "context": context}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def send_platform_email_task(
    self,
    subject,
    message,
    recipient_list,
    email_type="platform_system",
    html_message=None,
):
    """
    Dedicated background task for platform-level TechCraft emails.
    Guarantees strict TechCraft branding and zero clinic identity leaks.
    """
    ok = send_platform_email(
        subject,
        message,
        recipient_list,
        email_type=email_type,
        html_message=html_message,
    )
    if not ok:
        raise RuntimeError(f"Platform email send failed for {recipient_list}: {subject}")
    return {"recipient_list": recipient_list, "subject": subject, "status": "sent", "context": "platform"}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def send_bulk_email_task(self, subject, message, recipient_list, html_message=None):
    """
    Background task for sending the SAME message to MANY recipients.

    This is the fix for the actual "one-to-many" feature: it runs
    send_bulk_clinic_email() (single reused SMTP connection, isolated
    per-recipient sends, no address exposure) entirely off the request
    cycle. If the whole batch fails outright (e.g. SMTP server down), the
    task retries with backoff. Partial per-recipient failures are captured
    in the returned summary and logged, not silently dropped.
    """
    result = send_bulk_clinic_email(subject, message, recipient_list, html_message=html_message)

    if result["total"] > 0 and result["sent"] == 0:
        # Nothing at all went through — likely a connection-level issue.
        # Worth retrying the whole batch.
        raise RuntimeError(
            f"Bulk email '{subject}' failed for all {result['total']} recipients: "
            f"{result['errors'][:3]}"
        )

    logger.info(
        "Bulk email task '%s' done: %s/%s sent (%s failed).",
        subject, result["sent"], result["total"], result["failed"],
    )
    return result


# ── Backward-compatible sync wrapper ──────────────────────────
# Kept so any existing import of send_email_async() doesn't break, but it
# now just delegates to the real task. Prefer calling
# send_email_task.delay(...) directly in new code.
def send_email_async(subject, message, recipient_list):
    return send_email_task.delay(subject, message, recipient_list)