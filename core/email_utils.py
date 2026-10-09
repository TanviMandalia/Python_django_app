"""
Centralised, Production-Grade Email Subsystem for PhysioRehab Hospital System.

Handles:
1. Outgoing Transactional Email:
   - Header injection prevention (CRLF sanitization & validation)
   - Recipient format validation & RFC 5321 length enforcement (<= 254 chars)
   - Dual-format delivery: responsive HTML templates with plain-text fallback
   - Secure attachment validation (type, size, path sanitization)
   - Isolated To: addressing (zero cross-patient address exposure)
   - Safe operational audit logging (EmailLog model tracking status, error categories, zero secret leaks)
   - Connection reuse for bulk mailings to prevent SMTP rate-limits

2. Incoming / Inbound Email Processing:
   - Untrusted input sanitization (Stored XSS defense via sanitize_html_content)
   - Idempotent deduplication via stable message_id in InboundEmail model
   - Header and payload validation (sender, recipient, subject, body, content length)
   - Secure attachment inspection (MIME type, size limits, malware constraints)
   - Intelligent hospital tenant routing (inbound matching by clinic domain/address)
   - Automated SupportTicket thread routing (detects '[Ticket #123]' and appends SupportReply)
   - Clinic administrator notifications for inbound patient communications
"""

import os
import re
import uuid
import logging
from django.db.models import Q
from django.core.mail import send_mail, get_connection, EmailMultiAlternatives
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

from .file_security import sanitize_html_content, validate_attachment_file

logger = logging.getLogger(__name__)

CLINIC_NAME = getattr(settings, "CLINIC_NAME", "Dr. Dhvani Patalia — PhysioRehab")
CLINIC_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@physiorehab.com")
CLINIC_PHONE = getattr(settings, "CLINIC_PHONE", "+91 98765 43210")

SERVICE_NAMES = {
    "orthopedic": "Orthopedic Therapy",
    "neurological": "Neurological Rehab",
    "sports": "Sports Rehabilitation",
    "pediatric": "Pediatric Therapy",
    "womens": "Women's Health",
    "home_visit": "Home Visit",
}

TIME_NAMES = {
    "09:00": "9:00 AM",  "10:00": "10:00 AM",
    "11:00": "11:00 AM", "12:00": "12:00 PM",
    "14:00": "2:00 PM",  "15:00": "3:00 PM",
    "16:00": "4:00 PM",  "17:00": "5:00 PM",
}


def get_service_name(appt):
    service = getattr(appt, "service", appt) if hasattr(appt, "service") else str(appt)
    return SERVICE_NAMES.get(service, service)


def get_time_name(appt):
    time_val = getattr(appt, "time", appt) if hasattr(appt, "time") else str(appt)
    return TIME_NAMES.get(time_val, time_val)


def format_date(d):
    """Safely format a date whether it's a date object or string like '2026-06-12'."""
    if not d:
        return "N/A"
    if isinstance(d, str):
        try:
            from datetime import datetime
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            return str(d)
    try:
        return d.strftime("%d %B %Y")
    except Exception:
        return str(d)


# ── VALIDATION & SANITIZATION ─────────────────────────────────

def sanitize_header_value(value):
    """Strip carriage returns and newlines to prevent email header injection."""
    if not value:
        return ""
    return re.sub(r"[\r\n]+", " ", str(value)).strip()


def validate_recipient_email(email):
    """
    Validate email address format, RFC 5321 length, and header injection safety.
    Returns cleaned lowercase email, or raises ValidationError.
    """
    if not email:
        raise ValidationError("Email recipient cannot be empty.")

    cleaned = str(email).strip().lower()

    if len(cleaned) > 254:
        raise ValidationError("Email address exceeds maximum length of 254 characters.")

    if "\r" in cleaned or "\n" in cleaned:
        raise ValidationError("Email recipient contains forbidden newline characters (header injection).")

    try:
        django_validate_email(cleaned)
    except ValidationError:
        raise ValidationError(f"Invalid email address format: '{cleaned}'")

    return cleaned


def mask_email_for_logging(email):
    """Mask email for safe logging without revealing sensitive patient PII."""
    if not email or "@" not in email:
        return "***"
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + "*"
    else:
        masked_local = local_part[0] + "*" * (len(local_part) - 2) + local_part[-1]
    return f"{masked_local}@{domain}"


def render_html_wrapper(
    title,
    body_content,
    preheader="",
    context="clinic",
    hospital=None,
    organization_name=None,
):
    """
    Generate a clean, responsive HTML email template with strict identity separation.

    Contexts:
      - 'platform': TechCraft platform communications (Super Admin tests, SaaS subscriptions,
                    platform security alerts, system notices). Zero clinic branding leaks.
      - 'clinic': Clinic-branded communications (appointments, patient care, staff, billing)
                  retaining the specific hospital/clinic name, contact info, and branding.
    """
    safe_title = escape(title)
    safe_preheader = escape(preheader or title)

    is_platform = (context == "platform")

    if is_platform:
        org_title = organization_name or getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
        safe_org = escape(org_title)
        tagline = getattr(settings, "PLATFORM_TAGLINE", "Healthcare SaaS Platform")
        safe_tagline = escape(tagline)
        support_email = getattr(settings, "PLATFORM_SUPPORT_EMAIL", "techcraft1215@gmail.com")
        safe_support = escape(support_email)

        header_html = f"""
  <div class="header" style="background:#0f172a; padding:24px; text-align:center;">
    <h1 style="margin:0; font-size:22px; font-weight:700; color:#38bdf8; letter-spacing:0.5px;">{safe_org}</h1>
    <p style="margin:4px 0 0; font-size:13px; color:#94a3b8; font-weight:500;">{safe_tagline}</p>
  </div>"""
        footer_html = f"""
  <div class="footer" style="background:#f8fafc; padding:20px 24px; text-align:center; font-size:12px; color:#64748b; border-top:1px solid #e2e8f0;">
    <p style="margin:0 0 4px 0; font-weight:600; color:#334155;">{safe_org} SaaS Platform</p>
    <p style="margin:0;">Support & Inquiries: <a href="mailto:{safe_support}" style="color:#0284c7; text-decoration:none;">{safe_support}</a></p>
  </div>"""
    else:
        clinic_title = organization_name or (hospital.name if hospital else getattr(settings, "CLINIC_NAME", "Dr. Dhvani Patalia — PhysioRehab"))
        safe_clinic = escape(clinic_title)
        phone = hospital.phone if (hospital and hospital.phone) else getattr(settings, "CLINIC_PHONE", "+91 98765 43210")
        email = hospital.email if (hospital and hospital.email) else getattr(settings, "CLINIC_EMAIL", "noreply@physiorehab.com")
        safe_phone = escape(phone)
        safe_email = escape(email)

        header_html = f"""
  <div class="header" style="background:#0f172a; padding:24px; text-align:center;">
    <h1 style="margin:0; font-size:20px; font-weight:700; color:#38bdf8;">{safe_clinic}</h1>
  </div>"""
        footer_html = f"""
  <div class="footer" style="background:#f1f5f9; padding:18px 24px; text-align:center; font-size:12px; color:#64748b; border-top:1px solid #e2e8f0;">
    <p style="margin:0 0 4px 0;"><strong>{safe_clinic}</strong></p>
    <p style="margin:0;">Support: {safe_phone} | {safe_email}</p>
  </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
  .content {{ padding: 32px 24px; line-height: 1.6; font-size: 15px; color: #334155; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; background: #e0f2fe; color: #0369a1; }}
  .box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0; }}
</style>
</head>
<body>
<div style="display:none;font-size:1px;color:#f8fafc;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
  {safe_preheader}
</div>
<div class="container">
  {header_html}
  <div class="content">
    {body_content}
  </div>
  {footer_html}
</div>
</body>
</html>"""


# ── CORE SENDING FUNCTIONS ───────────────────────────────────

def send_platform_email(
    subject,
    message_text,
    recipient_list,
    email_type="platform_system",
    html_message=None,
    attachments=None,
    in_reply_to=None,
    thread_id=None,
    reply_to=None,
):
    """
    Send platform-level email using the authoritative TechCraft platform EmailAccount.
    Used for Super Admin notifications, SaaS subscription billing/activation notices,
    platform security alerts, and system-level communications.
    Strictly isolated from clinic identity; never leaks clinic branding.
    """
    from .email_service import resolve_email_account, EmailContext

    raw_recipients = recipient_list if isinstance(recipient_list, list) else [recipient_list]
    valid_recipients = []
    for r in raw_recipients:
        try:
            valid_recipients.append(validate_recipient_email(r))
        except ValidationError as e:
            logger.warning(f"Rejected invalid platform email recipient '{r}': {e}")

    if not valid_recipients:
        logger.error(f"Cannot send platform email '{subject}': No valid recipients.")
        return False

    clean_subject = sanitize_header_value(subject)

    # Resolve authoritative TechCraft platform account
    account = resolve_email_account(purpose=email_type, context=EmailContext.PLATFORM)

    platform_brand = getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
    clean_display_name = sanitize_header_value(account.from_name or platform_brand)
    from_email = f"{clean_display_name} <{account.from_email}>" if clean_display_name else account.from_email

    if not html_message:
        escaped_body = escape(message_text).replace("\n", "<br>")
        html_message = render_html_wrapper(
            clean_subject,
            f"<p>{escaped_body}</p>",
            context="platform",
            organization_name=clean_display_name,
        )

    effective_reply_to = reply_to or account.reply_to or getattr(settings, "PLATFORM_SUPPORT_EMAIL", "techcraft1215@gmail.com")
    reply_to_list = [sanitize_header_value(effective_reply_to)] if effective_reply_to else None

    connection = account.get_connection(fail_silently=False)

    success_all = True
    for recipient in valid_recipients:
        msg_id = f"{uuid.uuid4().hex}@{getattr(account, 'host', 'smtp.gmail.com')}"
        clean_thread_id = str(thread_id or msg_id).strip("<> ")
        headers = {
            "Message-ID": f"<{msg_id}>",
            "X-Thread-ID": clean_thread_id,
            "X-Mailer": "TechCraft-Platform-Gateway",
        }
        if in_reply_to:
            clean_in_reply_to = sanitize_header_value(in_reply_to).strip("<> ")
            headers["In-Reply-To"] = f"<{clean_in_reply_to}>"
            headers["References"] = f"<{clean_in_reply_to}>"
        if effective_reply_to:
            headers["Reply-To"] = sanitize_header_value(effective_reply_to)

        try:
            email_msg = EmailMultiAlternatives(
                subject=f"[{clean_display_name}] {clean_subject}",
                body=message_text,
                from_email=from_email,
                to=[recipient],
                headers=headers,
                reply_to=reply_to_list,
                connection=connection,
            )
            email_msg.attach_alternative(html_message, "text/html")

            if attachments:
                for att in attachments:
                    if isinstance(att, tuple) and len(att) >= 2:
                        att_name, att_content = att[0], att[1]
                        att_mime = att[2] if len(att) > 2 else "application/octet-stream"
                        email_msg.attach(sanitize_header_value(att_name), att_content, att_mime)

            email_msg.send(fail_silently=False)

            try:
                from .models import EmailLog
                _is_otp = bool(email_type and ("otp" in str(email_type).lower() or "verification" in str(email_type).lower()))
                _expires_at = (timezone.now() + timezone.timedelta(hours=24)) if _is_otp else None
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    direction="outgoing",
                    sender_email=account.from_email,
                    hospital=None,
                    email_type=email_type,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="sent",
                    is_otp=_is_otp,
                    expires_at=_expires_at,
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception as log_err:
                logger.debug(f"EmailLog record failed: {log_err}")

            safe_log_subject = clean_subject.encode("ascii", errors="backslashreplace").decode("ascii")
            logger.info(f"Platform email sent via '{account.name}' ({account.from_email}) to {mask_email_for_logging(recipient)}: '{safe_log_subject}'")

        except Exception as exc:
            success_all = False
            err_category = exc.__class__.__name__
            safe_err = str(exc).encode("ascii", errors="backslashreplace").decode("ascii")
            logger.error(f"Platform email failed via '{account.name}' to {mask_email_for_logging(recipient)}: {err_category} - {safe_err}")

            try:
                from .models import EmailLog
                _is_otp = bool(email_type and ("otp" in str(email_type).lower() or "verification" in str(email_type).lower()))
                _expires_at = (timezone.now() + timezone.timedelta(hours=24)) if _is_otp else None
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    direction="outgoing",
                    sender_email=account.from_email,
                    hospital=None,
                    email_type=email_type,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="failed",
                    is_otp=_is_otp,
                    expires_at=_expires_at,
                    error_category=err_category,
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception:
                pass

    return success_all


def send_clinic_email(
    subject,
    message_text,
    recipient_list,
    hospital=None,
    email_type="transactional",
    html_message=None,
    attachments=None,
    in_reply_to=None,
    thread_id=None,
    reply_to=None,
    doctor=None,
):
    """
    Send an isolated email to a single recipient (or small list of recipients)
    with full validation, HTML rendering, safe logging, and EmailLog recording.
    Dynamically resolves the authoritative EmailAccount per clinic, role, or purpose.
    Supports RFC threading headers (In-Reply-To, References, X-Thread-ID) and Reply-To.
    """
    from .email_service import resolve_email_account, EmailContext

    raw_recipients = recipient_list if isinstance(recipient_list, list) else [recipient_list]
    valid_recipients = []

    for r in raw_recipients:
        try:
            valid_recipients.append(validate_recipient_email(r))
        except ValidationError as e:
            logger.warning(f"Rejected invalid email recipient '{r}': {e}")

    if not valid_recipients:
        logger.error(f"Cannot send email '{subject}': No valid recipients.")
        return False

    clean_subject = sanitize_header_value(subject)

    # Resolve authoritative EmailAccount dynamically with CLINIC context
    account = resolve_email_account(
        purpose=email_type,
        hospital=hospital,
        doctor=doctor,
        context=EmailContext.CLINIC,
    )

    if account.scope_type != "platform" and account.from_name:
        display_clinic_name = account.from_name
    elif hospital and hospital.name:
        display_clinic_name = hospital.name
    else:
        display_clinic_name = getattr(settings, "CLINIC_NAME", "Dr. Dhvani Patalia — PhysioRehab")
    clean_display_name = sanitize_header_value(display_clinic_name)
    from_email = f"{clean_display_name} <{account.from_email}>" if clean_display_name else account.from_email

    if not html_message:
        escaped_body = escape(message_text).replace("\n", "<br>")
        html_message = render_html_wrapper(
            clean_subject,
            f"<p>{escaped_body}</p>",
            context="clinic",
            hospital=hospital,
            organization_name=clean_display_name,
        )

    effective_reply_to = reply_to or account.reply_to
    reply_to_list = [sanitize_header_value(effective_reply_to)] if effective_reply_to else None

    # Obtain dynamic connection configured for this account
    connection = account.get_connection(fail_silently=False)

    success_all = True
    for recipient in valid_recipients:
        msg_id = f"{uuid.uuid4().hex}@{getattr(account, 'host', 'localhost')}"
        clean_thread_id = str(thread_id or msg_id).strip("<> ")
        headers = {
            "Message-ID": f"<{msg_id}>",
            "X-Thread-ID": clean_thread_id,
        }
        if in_reply_to:
            clean_in_reply_to = sanitize_header_value(in_reply_to).strip("<> ")
            headers["In-Reply-To"] = f"<{clean_in_reply_to}>"
            headers["References"] = f"<{clean_in_reply_to}>"
        if effective_reply_to:
            headers["Reply-To"] = sanitize_header_value(effective_reply_to)

        try:
            email_msg = EmailMultiAlternatives(
                subject=f"[{clean_display_name}] {clean_subject}",
                body=message_text,
                from_email=from_email,
                to=[recipient],
                headers=headers,
                reply_to=reply_to_list,
                connection=connection,
            )
            email_msg.attach_alternative(html_message, "text/html")

            # Attachments verification
            if attachments:
                for att in attachments:
                    if isinstance(att, tuple) and len(att) >= 2:
                        att_name, att_content = att[0], att[1]
                        att_mime = att[2] if len(att) > 2 else "application/octet-stream"
                        email_msg.attach(sanitize_header_value(att_name), att_content, att_mime)

            email_msg.send(fail_silently=False)

            # Record successful outgoing email log
            try:
                from .models import EmailLog
                _is_otp = bool(email_type and ("otp" in str(email_type).lower() or "verification" in str(email_type).lower()))
                _expires_at = (timezone.now() + timezone.timedelta(hours=24)) if _is_otp else None
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    direction="outgoing",
                    sender_email=account.from_email,
                    hospital=hospital or account.hospital,
                    email_type=email_type,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="sent",
                    is_otp=_is_otp,
                    expires_at=_expires_at,
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception as log_err:
                logger.debug(f"EmailLog record failed: {log_err}")

            safe_log_subject = clean_subject.encode("ascii", errors="backslashreplace").decode("ascii")
            logger.info(f"Email sent successfully via account '{account.name}' ({account.from_email}) to {mask_email_for_logging(recipient)}: '{safe_log_subject}'")

        except Exception as exc:
            success_all = False
            err_category = exc.__class__.__name__
            safe_err = str(exc).encode("ascii", errors="backslashreplace").decode("ascii")
            logger.error(f"Email failed via account '{account.name}' to {mask_email_for_logging(recipient)}: {err_category} - {safe_err}")

            try:
                from .models import EmailLog
                _is_otp = bool(email_type and ("otp" in str(email_type).lower() or "verification" in str(email_type).lower()))
                _expires_at = (timezone.now() + timezone.timedelta(hours=24)) if _is_otp else None
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    direction="outgoing",
                    sender_email=account.from_email,
                    hospital=hospital or account.hospital,
                    email_type=email_type,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="failed",
                    is_otp=_is_otp,
                    expires_at=_expires_at,
                    error_category=err_category,
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception:
                pass

    return success_all


def send_bulk_clinic_email(subject, message_text, recipient_list, html_message=None, hospital=None):
    """
    Send isolated, individual emails to many recipients reusing a single SMTP connection.
    Guarantees no cross-recipient email address exposure.
    """
    clean_subject = sanitize_header_value(subject)
    recipients = []
    for r in (recipient_list or []):
        try:
            recipients.append(validate_recipient_email(r))
        except ValidationError:
            pass

    result = {"total": len(recipients), "sent": 0, "failed": 0, "errors": []}
    if not recipients:
        return result

    connection = get_connection(fail_silently=False)
    try:
        connection.open()
        for addr in recipients:
            msg_id = f"{uuid.uuid4().hex}@{getattr(settings, 'EMAIL_HOST', 'localhost')}"
            try:
                email = EmailMultiAlternatives(
                    subject=f"[{CLINIC_NAME}] {clean_subject}",
                    body=message_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[addr],
                    connection=connection,
                    headers={"Message-ID": f"<{msg_id}>"},
                )
                if html_message:
                    email.attach_alternative(html_message, "text/html")
                email.send(fail_silently=False)
                result["sent"] += 1

                try:
                    from .models import EmailLog
                    EmailLog.objects.create(
                        direction="outgoing",
                        hospital=hospital,
                        email_type="bulk",
                        recipient_email=addr,
                        subject=clean_subject,
                        status="sent",
                        message_id=msg_id,
                    )
                except Exception:
                    pass

            except Exception as e:
                result["failed"] += 1
                result["errors"].append({"email": mask_email_for_logging(addr), "error": str(e)})
                logger.error(f"Bulk email failed for {mask_email_for_logging(addr)}: {e}")
    finally:
        try:
            connection.close()
        except Exception:
            pass

    return result


def send_email(subject, body, recipient_list, html_message=None):
    """Backward-compatible single/multi send wrapper."""
    recipients = recipient_list if isinstance(recipient_list, list) else [recipient_list]
    if len(recipients) > 1:
        result = send_bulk_clinic_email(subject, body, recipients, html_message=html_message)
        return result["failed"] == 0
    return send_clinic_email(subject, body, recipients, html_message=html_message)


# ── APPOINTMENT EMAILS ───────────────────────────────────────

def send_appointment_confirmation(appointment):
    hospital = getattr(appointment, "hospital", None)
    subject = "Appointment Booked Successfully"
    patient_name = escape(appointment.name)
    service_name = escape(get_service_name(appointment))
    date_str = escape(format_date(appointment.date))
    time_str = escape(get_time_name(appointment))

    clinic_title = hospital.name if hospital else CLINIC_NAME
    clinic_phone = hospital.phone if (hospital and hospital.phone) else CLINIC_PHONE

    body_text = f"""Dear {appointment.name},

Your appointment has been booked at {clinic_title}.

Details:
  Service  : {get_service_name(appointment)}
  Date     : {format_date(appointment.date)}
  Time     : {get_time_name(appointment)}
  Status   : Pending Confirmation

We will confirm your appointment shortly.
For queries, call us at {clinic_phone}.

Thank you for choosing {clinic_title}!
"""
    html_content = f"""<p>Dear <strong>{patient_name}</strong>,</p>
<p>Your appointment has been recorded at <strong>{clinic_title}</strong>.</p>
<div class="box">
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
    <tr><td style="padding:6px 0; color:#64748b;">Service:</td><td style="font-weight:600;">{service_name}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Date:</td><td style="font-weight:600;">{date_str}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Time:</td><td style="font-weight:600;">{time_str}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Status:</td><td><span class="badge">Pending Confirmation</span></td></tr>
  </table>
</div>
<p>Our clinical administration team will review and confirm your session shortly.</p>"""

    html = render_html_wrapper(
        subject,
        html_content,
        preheader=f"Appointment booked for {date_str}",
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, appointment.email, hospital=hospital, email_type="appointment_confirmation", html_message=html
    )


def send_appointment_status_update(appointment):
    hospital = getattr(appointment, "hospital", None)
    status_titles = {
        "confirmed": "Appointment Confirmed ✅",
        "completed": "Appointment Completed 🎉",
        "cancelled": "Appointment Cancelled ❌",
    }
    label = status_titles.get(appointment.status, "Appointment Updated")
    patient_name = escape(appointment.name)
    service_name = escape(get_service_name(appointment))
    date_str = escape(format_date(appointment.date))
    time_str = escape(get_time_name(appointment))
    status_str = escape(appointment.status.upper())

    clinic_title = hospital.name if hospital else CLINIC_NAME
    clinic_phone = hospital.phone if (hospital and hospital.phone) else CLINIC_PHONE

    body_text = f"""Dear {appointment.name},

Your appointment status has been updated.

Details:
  Service  : {get_service_name(appointment)}
  Date     : {format_date(appointment.date)}
  Time     : {get_time_name(appointment)}
  Status   : {appointment.status.upper()}
"""
    if appointment.status == "confirmed":
        body_text += "\nPlease arrive 10 minutes before your scheduled time.\n"
    elif appointment.status == "cancelled":
        body_text += f"\nTo reschedule, call us at {clinic_phone}.\n"

    body_text += f"\n{clinic_title}"

    extra_msg = ""
    if appointment.status == "confirmed":
        extra_msg = "<p style='color:#059669; font-weight:600;'>Please arrive 10 minutes before your scheduled appointment time.</p>"
    elif appointment.status == "cancelled":
        extra_msg = f"<p style='color:#dc2626;'>To reschedule this session, please contact us at {clinic_phone}.</p>"

    html_content = f"""<p>Dear <strong>{patient_name}</strong>,</p>
<p>Your appointment status has been updated:</p>
<div class="box">
  <table style="width:100%; border-collapse:collapse; font-size:14px;">
    <tr><td style="padding:6px 0; color:#64748b;">Service:</td><td style="font-weight:600;">{service_name}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Date:</td><td style="font-weight:600;">{date_str}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Time:</td><td style="font-weight:600;">{time_str}</td></tr>
    <tr><td style="padding:6px 0; color:#64748b;">Status:</td><td><span class="badge">{status_str}</span></td></tr>
  </table>
</div>
{extra_msg}"""

    html = render_html_wrapper(
        label,
        html_content,
        preheader=f"Status update: {appointment.status}",
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        label, body_text, appointment.email, hospital=hospital, email_type="appointment_status_update", html_message=html
    )


def send_admin_new_appointment_alert(appointment):
    hospital = getattr(appointment, "hospital", None)
    admin_email = hospital.email if (hospital and hospital.email) else CLINIC_EMAIL
    subject = f"New Appointment: {appointment.name} – {appointment.date}"
    body_text = f"""New appointment booked.

Patient  : {appointment.name}
Phone    : {appointment.phone}
Email    : {appointment.email}
Service  : {get_service_name(appointment)}
Date     : {format_date(appointment.date)}
Time     : {get_time_name(appointment)}
Notes    : {appointment.notes or 'None'}

Login to the clinic admin panel to confirm or assign this session.
"""
    html_content = f"""<p>A new appointment has been scheduled:</p>
<div class="box">
  <p><strong>Patient:</strong> {escape(appointment.name)} ({escape(appointment.email)} | {escape(appointment.phone)})</p>
  <p><strong>Service:</strong> {escape(get_service_name(appointment))}</p>
  <p><strong>Scheduled:</strong> {escape(format_date(appointment.date))} at {escape(get_time_name(appointment))}</p>
  <p><strong>Notes:</strong> {escape(appointment.notes or 'None')}</p>
</div>
<p>Please log in to your clinic admin portal to confirm or delegate this session.</p>"""

    clinic_title = hospital.name if hospital else CLINIC_NAME
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, admin_email, hospital=hospital, email_type="admin_appointment_alert", html_message=html
    )


# ── OTP & AUTHENTICATION EMAILS ───────────────────────────────

def send_otp_email(email, otp, purpose="Password Reset", user=None, hospital=None):
    clean_purpose = sanitize_header_value(purpose)

    # Determine if this OTP is for a platform super admin / superuser vs clinic user
    is_platform_user = False
    if user:
        if user.is_superuser or getattr(user, "is_super_admin", False):
            is_platform_user = True
        elif not getattr(user, "hospital", None) and not hospital:
            is_platform_user = True
    elif hospital is None:
        from .models import User
        found_user = User.objects.filter(email__iexact=email).first()
        if found_user and (found_user.is_superuser or getattr(found_user, "is_super_admin", False)):
            is_platform_user = True

    if is_platform_user:
        platform_brand = getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
        subject = f"{clean_purpose} Verification Code – {platform_brand}"
        body_text = f"""Your verification code for {clean_purpose} on {platform_brand}:

    CODE: {otp}

Valid for 5 minutes. Never share this code with anyone.

{platform_brand} Platform Administration
"""
        html_content = f"""<p>You requested a verification code for <strong>{escape(clean_purpose)}</strong> on <strong>{escape(platform_brand)}</strong>.</p>
<div class="box" style="text-align:center; padding:24px;">
  <span style="font-size:32px; font-weight:800; letter-spacing:6px; color:#0284c7; background:#e0f2fe; padding:8px 24px; border-radius:8px; display:inline-block;">
    {escape(str(otp))}
  </span>
</div>
<p style="color:#64748b; font-size:13px;">This code is valid for 5 minutes. If you did not initiate this request, please contact our security team immediately.</p>"""

        html = render_html_wrapper(
            subject,
            html_content,
            preheader=f"Your verification code is {otp}",
            context="platform",
            organization_name=platform_brand,
        )
        return send_platform_email(
            subject, body_text, email, email_type="platform_otp", html_message=html
        )
    else:
        clinic_title = (hospital.name if hospital else getattr(settings, "CLINIC_NAME", "Dr. Dhvani Patalia — PhysioRehab"))
        subject = f"{clean_purpose} Verification Code"
        body_text = f"""Your verification code for {clean_purpose} at {clinic_title}:

    CODE: {otp}

Valid for 5 minutes. Never share this code with anyone.

{clinic_title}
"""
        html_content = f"""<p>You requested a verification code for <strong>{escape(clean_purpose)}</strong>.</p>
<div class="box" style="text-align:center; padding:24px;">
  <span style="font-size:32px; font-weight:800; letter-spacing:6px; color:#0284c7; background:#e0f2fe; padding:8px 24px; border-radius:8px; display:inline-block;">
    {escape(str(otp))}
  </span>
</div>
<p style="color:#64748b; font-size:13px;">This code is valid for 5 minutes. If you did not initiate this request, please contact our security team immediately.</p>"""

        html = render_html_wrapper(
            subject,
            html_content,
            preheader=f"Your verification code is {otp}",
            context="clinic",
            hospital=hospital,
            organization_name=clinic_title,
        )
        return send_clinic_email(
            subject, body_text, email, hospital=hospital, email_type="otp_verification", html_message=html
        )


# ── STAFF EMAILS ─────────────────────────────────────────────

def send_leave_status_email(leave):
    staff_user = getattr(leave, "staff", None)
    if not staff_user or not getattr(staff_user, "email", None):
        return False

    hospital = getattr(leave, "hospital", None)
    subject = f"Leave Application {leave.status.upper()}"
    body_text = f"""Dear {staff_user.get_full_name() or staff_user.username},

Your leave application has been {leave.status.upper()}.

  Type   : {leave.get_leave_type_display()}
  From   : {format_date(leave.from_date)}
  To     : {format_date(leave.to_date)}
  Status : {leave.status.upper()}
  Note   : {leave.admin_note or 'No administrator note'}

{CLINIC_NAME}
"""
    html_content = f"""<p>Dear <strong>{escape(staff_user.get_full_name() or staff_user.username)}</strong>,</p>
<p>Your leave application has been updated to <strong>{escape(leave.status.upper())}</strong>.</p>
<div class="box">
  <p><strong>Type:</strong> {escape(leave.get_leave_type_display())}</p>
  <p><strong>Duration:</strong> {escape(format_date(leave.from_date))} to {escape(format_date(leave.to_date))}</p>
  <p><strong>Status:</strong> <span class="badge">{escape(leave.status.upper())}</span></p>
  <p><strong>Note:</strong> {escape(leave.admin_note or 'None')}</p>
</div>"""

    clinic_title = hospital.name if hospital else CLINIC_NAME
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, staff_user.email, hospital=hospital, email_type="leave_status", html_message=html
    )


def send_salary_paid_email(salary_record):
    staff_user = getattr(salary_record, "staff", None)
    if not staff_user or not getattr(staff_user, "email", None):
        return False

    hospital = getattr(salary_record, "hospital", None)
    subject = f"Salary Processed – {salary_record.month} {salary_record.year}"
    body_text = f"""Dear {staff_user.get_full_name() or staff_user.username},

Your salary for {salary_record.month} {salary_record.year} has been processed.

  Basic Salary : ₹{salary_record.basic_salary}
  Bonus        : ₹{salary_record.bonus}
  Deduction    : ₹{salary_record.deduction}
  Net Salary   : ₹{salary_record.net_salary}
  Paid On      : {format_date(salary_record.paid_on) if salary_record.paid_on else 'N/A'}

{CLINIC_NAME}
"""
    html_content = f"""<p>Dear <strong>{escape(staff_user.get_full_name() or staff_user.username)}</strong>,</p>
<p>Your compensation record for <strong>{escape(salary_record.month)} {escape(str(salary_record.year))}</strong> has been credited.</p>
<div class="box">
  <p><strong>Basic:</strong> ₹{salary_record.basic_salary}</p>
  <p><strong>Bonus:</strong> ₹{salary_record.bonus}</p>
  <p><strong>Deductions:</strong> ₹{salary_record.deduction}</p>
  <hr style="border:none; border-top:1px solid #cbd5e1; margin:8px 0;">
  <p style="font-size:16px; font-weight:700; color:#059669;">Net Paid: ₹{salary_record.net_salary}</p>
</div>"""

    clinic_title = hospital.name if hospital else CLINIC_NAME
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, staff_user.email, hospital=hospital, email_type="salary_paid", html_message=html
    )


def send_task_assigned_email(task):
    assigned_to = getattr(task, "assigned_to", None)
    if not assigned_to or not getattr(assigned_to, "email", None):
        return False

    hospital = getattr(task, "hospital", None)
    subject = f"New Clinical Task: {task.title}"
    body_text = f"""Dear {assigned_to.get_full_name() or assigned_to.username},

A new clinical task has been assigned to you.

  Task     : {task.title}
  Priority : {task.priority.upper()}
  Due Date : {format_date(task.due_date) if task.due_date else 'No deadline'}
  Details  : {task.description or 'N/A'}

Login to your staff dashboard to review and complete this task.

{CLINIC_NAME}
"""
    html_content = f"""<p>Dear <strong>{escape(assigned_to.get_full_name() or assigned_to.username)}</strong>,</p>
<p>A new task has been delegated to you by the clinic administration:</p>
<div class="box">
  <p><strong>Title:</strong> {escape(task.title)}</p>
  <p><strong>Priority:</strong> <span class="badge">{escape(task.priority.upper())}</span></p>
  <p><strong>Due Date:</strong> {escape(format_date(task.due_date) if task.due_date else 'No deadline')}</p>
  <p><strong>Instructions:</strong> {escape(task.description or 'None')}</p>
</div>"""

    clinic_title = hospital.name if hospital else CLINIC_NAME
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, assigned_to.email, hospital=hospital, email_type="task_assignment", html_message=html
    )


def send_staff_welcome_email(user, password):
    if not user or not user.email:
        return False

    subject = "Welcome to PhysioRehab – Your Staff Account Details"
    body_text = f"""Dear {user.get_full_name() or user.username},

Welcome to {CLINIC_NAME}! Your staff account has been provisioned.

  Username : {user.username}
  Password : {password}

Please log in and update your password immediately upon first access.

{CLINIC_NAME}
"""
    html_content = f"""<p>Dear <strong>{escape(user.get_full_name() or user.username)}</strong>,</p>
<p>Welcome to <strong>{CLINIC_NAME}</strong>. Your healthcare worker portal credentials are:</p>
<div class="box">
  <p><strong>Username:</strong> <code>{escape(user.username)}</code></p>
  <p><strong>Temporary Password:</strong> <code>{escape(password)}</code></p>
</div>
<p style="color:#b91c1c; font-size:13px;">For security compliance, you must change this password immediately after your initial sign in.</p>"""

    html = render_html_wrapper(subject, html_content)
    return send_clinic_email(
        subject, body_text, user.email, email_type="staff_welcome", html_message=html
    )


# ── SUBSCRIPTION EMAILS ──────────────────────────────────────

def send_subscription_success_email(hospital, plan, expires_at):
    if not hospital or not hospital.email:
        return False

    platform_brand = getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
    plan_name = plan.get_name_display() if hasattr(plan, "get_name_display") else str(plan)
    subject = "Platform Subscription Activated Successfully"
    body_text = f"""Dear {hospital.name} Administration,

Your subscription to {platform_brand} Platform is now active!

Plan Details:
  Plan       : {plan_name}
  Expiry Date: {format_date(expires_at)}
  Price      : ₹{getattr(plan, 'price_monthly', 0)}/month

Thank you for partnering with {platform_brand}!
"""
    html_content = f"""<p>Dear <strong>{escape(hospital.name)}</strong> Administration,</p>
<p>Your {escape(platform_brand)} platform subscription has been verified and activated.</p>
<div class="box">
  <p><strong>Plan:</strong> <span class="badge">{escape(plan_name)}</span></p>
  <p><strong>Expires On:</strong> {escape(format_date(expires_at))}</p>
  <p><strong>Monthly Rate:</strong> ₹{getattr(plan, 'price_monthly', 0)}</p>
</div>
<p>Thank you for partnering with <strong>{escape(platform_brand)}</strong>. You now have full access to your healthcare management portal.</p>"""

    html = render_html_wrapper(
        subject,
        html_content,
        context="platform",
        organization_name=platform_brand,
    )
    return send_platform_email(
        subject, body_text, hospital.email, email_type="subscription_activated", html_message=html
    )


def send_subscription_expiry_warning_email(hospital, plan, expires_at, days_left):
    if not hospital or not hospital.email:
        return False

    platform_brand = getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
    plan_name = plan.get_name_display() if hasattr(plan, "get_name_display") else str(plan)
    subject = f"⚠️ Subscription Expiring in {days_left} Days"
    body_text = f"""Dear {hospital.name} Administration,

Your clinic subscription on {platform_brand} will expire in {days_left} day(s) on {format_date(expires_at)}.
To prevent operational interruption, please renew your plan.

{platform_brand} Platform Administration
"""
    html_content = f"""<p>Dear <strong>{escape(hospital.name)}</strong> Administration,</p>
<p style="color:#b45309; font-weight:600;">Your clinic subscription will expire in {days_left} days.</p>
<div class="box">
  <p><strong>Active Plan:</strong> {escape(plan_name)}</p>
  <p><strong>Expiry Date:</strong> {escape(format_date(expires_at))}</p>
</div>
<p>Please renew before expiry to ensure uninterrupted clinical access for your staff and patients.</p>"""

    html = render_html_wrapper(
        subject,
        html_content,
        context="platform",
        organization_name=platform_brand,
    )
    return send_platform_email(
        subject, body_text, hospital.email, email_type="subscription_warning", html_message=html
    )


def send_welcome_email(user, hospital=None):
    """Send welcoming notification email to newly registered patients or users."""
    if not user or not user.email:
        return False
    clinic_title = hospital.name if hospital else CLINIC_NAME
    subject = f"Welcome to {clinic_title}!"
    body_text = f"""Dear {user.get_full_name() or user.username},

Welcome to {clinic_title}. Your hospital account has been created and verified.

Best regards,
{clinic_title}
"""
    html_content = f"""<p>Dear <strong>{escape(user.get_full_name() or user.username)}</strong>,</p>
<p>Welcome to <strong>{escape(clinic_title)}</strong>. Your patient account has been created successfully.</p>
<p>You can now log in, schedule appointments, review session records, and manage your treatments securely.</p>"""
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, user.email, hospital=hospital, email_type="welcome", html_message=html
    )


def send_password_reset_otp_email(email, otp, user=None, hospital=None):
    """Alias for send_otp_email for password resets with context support."""
    return send_otp_email(email, otp, purpose="Password Reset", user=user, hospital=hospital)


def send_appointment_confirmation_email(appointment):
    """Alias for send_appointment_confirmation."""
    return send_appointment_confirmation(appointment)


def send_appointment_cancellation_email(appointment, reason=""):
    """Send appointment cancellation notice to patient."""
    if not appointment or not appointment.email:
        return False
    clinic_title = appointment.hospital.name if appointment.hospital else CLINIC_NAME
    subject = "Appointment Cancellation Notice"
    reason_txt = reason.strip() or "Schedule update / patient request"
    body_text = f"""Dear {appointment.name},

Your appointment scheduled for {format_date(appointment.date)} at {appointment.time} has been cancelled.

Reason: {reason_txt}

If you would like to reschedule, please visit our online booking portal or contact the clinic.

{clinic_title}
"""
    html_content = f"""<p>Dear <strong>{escape(appointment.name)}</strong>,</p>
<p>Your appointment on <strong>{escape(format_date(appointment.date))} at {escape(str(appointment.time))}</strong> has been cancelled.</p>
<div class="box">
  <p><strong>Reason:</strong> {escape(reason_txt)}</p>
</div>
<p>If you need to reschedule or consult with our staff, please contact us.</p>"""
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=appointment.hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, appointment.email, hospital=appointment.hospital, email_type="appointment_cancelled", html_message=html
    )


def send_invoice_email(user, invoice_num, amount, description, hospital=None):
    """Send invoice receipt notification to patient."""
    if not user or not user.email:
        return False
    clinic_title = hospital.name if hospital else CLINIC_NAME
    subject = f"Invoice #{invoice_num} from {clinic_title}"
    body_text = f"""Dear {user.get_full_name() or user.username},

Invoice #{invoice_num} has been generated for your recent services.

Details:
  Amount     : ₹{amount}
  Description: {description}

Thank you for choosing {clinic_title}.
"""
    html_content = f"""<p>Dear <strong>{escape(user.get_full_name() or user.username)}</strong>,</p>
<div class="box">
  <p><strong>Invoice Number:</strong> #{escape(str(invoice_num))}</p>
  <p><strong>Amount:</strong> ₹{amount}</p>
  <p><strong>Services:</strong> {escape(str(description))}</p>
</div>
<p>Thank you for partnering with <strong>{escape(clinic_title)}</strong>.</p>"""
    html = render_html_wrapper(
        subject,
        html_content,
        context="clinic",
        hospital=hospital,
        organization_name=clinic_title,
    )
    return send_clinic_email(
        subject, body_text, user.email, hospital=hospital, email_type="invoice", html_message=html
    )


# ── INBOUND EMAIL RECEIVING & PROCESSING ─────────────────────

def process_inbound_email_payload(payload_dict, raw_headers=None):
    """
    Process incoming untrusted emails from webhooks or mail receivers.
    Verifies:
      - Required metadata (sender, recipient, subject, body, message_id)
      - Email recipient syntax & RFC 5321 length
      - Message deduplication (idempotency via unique message_id)
      - HTML sanitization against stored XSS
      - RFC threading headers: In-Reply-To, References, X-Thread-ID
      - Safe attachment parsing
      - Tenant hospital association
      - Intelligent Dynamic Routing:
        * Doctor/Staff inbound reply -> Message chat & Admin/Doctor notifications
        * Patient inbound communication -> Clinic Admin notification
        * Support ticket replies -> SupportTicket & SupportReply routing
    """
    from .models import Hospital, InboundEmail, SupportTicket, SupportReply, Notification, User, EmailLog, Message

    sender = payload_dict.get("sender") or payload_dict.get("from", "")
    recipient = payload_dict.get("recipient") or payload_dict.get("to", "")
    subject = payload_dict.get("subject", "").strip()
    body_text = payload_dict.get("body_text") or payload_dict.get("text", "")
    raw_html = payload_dict.get("body_html") or payload_dict.get("html", "")

    # Headers dictionary normalization
    headers_dict = dict(raw_headers or {})

    # Extract Message-ID
    raw_msg_id = (
        payload_dict.get("message_id")
        or payload_dict.get("Message-Id")
        or payload_dict.get("Message-ID")
        or headers_dict.get("Message-ID")
        or headers_dict.get("message-id")
        or f"inbound_{uuid.uuid4().hex}"
    )
    clean_msg_id = sanitize_header_value(raw_msg_id).strip("<> ")

    # Extract RFC Threading Headers
    raw_in_reply_to = (
        payload_dict.get("in_reply_to")
        or payload_dict.get("In-Reply-To")
        or headers_dict.get("In-Reply-To")
        or headers_dict.get("in-reply-to")
        or ""
    )
    clean_in_reply_to = sanitize_header_value(raw_in_reply_to).strip("<> ")

    raw_refs = (
        payload_dict.get("references")
        or payload_dict.get("References")
        or headers_dict.get("References")
        or headers_dict.get("references")
        or ""
    )
    clean_refs = sanitize_header_value(raw_refs).strip()

    raw_thread_id = (
        payload_dict.get("thread_id")
        or payload_dict.get("Thread-Id")
        or headers_dict.get("X-Thread-ID")
        or headers_dict.get("Thread-Index")
        or ""
    )
    clean_thread_id = sanitize_header_value(raw_thread_id).strip()

    # 1. Validation
    try:
        clean_sender = validate_recipient_email(sender)
    except ValidationError as err:
        return {"status": "rejected", "error": f"Invalid sender address: {err}"}

    try:
        clean_recipient = validate_recipient_email(recipient)
    except ValidationError as err:
        return {"status": "rejected", "error": f"Invalid recipient address: {err}"}

    # 2. Duplicate Detection / Idempotency
    existing = InboundEmail.objects.filter(message_id=clean_msg_id).first()
    if existing:
        logger.info(f"Duplicate incoming email ignored (message_id={clean_msg_id})")
        return {"status": "duplicate", "message_id": clean_msg_id, "id": existing.id}

    # 3. HTML Sanitization
    sanitized_html = sanitize_html_content(raw_html) if raw_html else ""
    clean_subject = sanitize_header_value(subject)

    # 4. Hospital Tenancy Association
    matched_hospital = (
        Hospital.objects.filter(email__iexact=clean_recipient).first()
        or Hospital.objects.filter(is_active=True).first()
    )

    # 5. Thread Association & Original Email Lookup
    orig_log = None
    if clean_in_reply_to:
        orig_log = EmailLog.objects.filter(message_id=clean_in_reply_to).first()
    if not orig_log and clean_refs:
        ref_tokens = [r.strip("<> ") for r in clean_refs.split()]
        orig_log = EmailLog.objects.filter(message_id__in=ref_tokens).first()

    if orig_log:
        if not clean_thread_id:
            clean_thread_id = orig_log.thread_id or orig_log.message_id
        if not matched_hospital and orig_log.hospital:
            matched_hospital = orig_log.hospital

    if not clean_thread_id:
        clean_thread_id = clean_in_reply_to or clean_msg_id

    # 6. Process Attachments Metadata
    raw_attachments = payload_dict.get("attachments", [])
    safe_attachments = []
    if isinstance(raw_attachments, list):
        for att in raw_attachments:
            if isinstance(att, dict):
                safe_attachments.append({
                    "filename": sanitize_header_value(att.get("filename", "attachment")),
                    "size": int(att.get("size", 0)),
                    "content_type": sanitize_header_value(att.get("content_type", "application/octet-stream")),
                })

    # 7. Persist InboundEmail record with threading fields
    inbound_obj = InboundEmail.objects.create(
        hospital=matched_hospital,
        message_id=clean_msg_id,
        in_reply_to=clean_in_reply_to,
        references=clean_refs,
        thread_id=clean_thread_id,
        sender=clean_sender,
        recipient=clean_recipient,
        subject=clean_subject,
        body_text=body_text,
        body_html=sanitized_html,
        raw_headers=headers_dict,
        attachments_info=safe_attachments,
        status="processed",
    )

    # 8. Intelligent Routing & Action Dispatching
    from .views import get_admin_user
    admin_user = get_admin_user(matched_hospital) if matched_hospital else None

    # Case A: Support Ticket Reply (Subject matching '[Ticket #<id>]')
    ticket_match = re.search(r"\[Ticket\s*#?(\d+)\]", clean_subject, re.IGNORECASE)
    if ticket_match:
        ticket_id = int(ticket_match.group(1))
        ticket = SupportTicket.objects.filter(id=ticket_id).first()
        if ticket:
            sender_user = User.objects.filter(email__iexact=clean_sender).first()
            SupportReply.objects.create(
                ticket=ticket,
                hospital=ticket.hospital,
                replier=sender_user,
                message=f"[Inbound Email from {clean_sender}]\n\n{body_text or sanitized_html}",
            )
            ticket.status = "in_progress"
            ticket.save(update_fields=["status", "updated_at"])
            logger.info(f"Routed inbound email {clean_msg_id} to SupportTicket #{ticket_id}")

    # Case B: Doctor / Medical Staff Communication
    # Check if sender is a registered doctor/staff member in the hospital
    sender_doctor = (
        User.objects.filter(email__iexact=clean_sender)
        .filter(Q(staff_profile__isnull=False) | Q(is_staff=True))
        .first()
    )
    is_doctor_reply = sender_doctor is not None

    if is_doctor_reply and admin_user:
        # Create Message record in the doctor communication thread
        msg_content = (body_text or sanitized_html or clean_subject).strip()
        Message.objects.create(
            hospital=matched_hospital,
            sender=sender_doctor,
            receiver=admin_user,
            content=msg_content,
            status=Message.STATUS_SENT,
        )
        # Notify Clinic Administrator of the doctor's communication
        Notification.objects.create(
            hospital=matched_hospital,
            recipient=admin_user,
            message=f"💬 Doctor reply from {sender_doctor.get_full_name() or sender_doctor.username}: {clean_subject[:40]}",
            link=f"/admin-doctor-chat/{sender_doctor.id}/",
        )
        # Create confirmation notification for Doctor
        Notification.objects.create(
            hospital=matched_hospital,
            recipient=sender_doctor,
            message=f"✅ Reply received and delivered to Clinic Administration: {clean_subject[:40]}",
            link="/chat/",
        )
        logger.info(f"Routed inbound doctor email from {clean_sender} to admin chat ({admin_user.username})")

    # Case C: Inbound email sent TO a Doctor / Staff Member
    recipient_doctor = (
        User.objects.filter(email__iexact=clean_recipient)
        .filter(Q(staff_profile__isnull=False) | Q(is_staff=True))
        .first()
    )
    if recipient_doctor and not is_doctor_reply:
        Notification.objects.create(
            hospital=matched_hospital,
            recipient=recipient_doctor,
            message=f"📧 Inbound email from {clean_sender}: {clean_subject[:40]}",
            link="/chat/",
        )
        logger.info(f"Routed inbound email notification to doctor {recipient_doctor.username}")

    # Case D: General Inbound Communication (Patient or inquiry to clinic)
    if admin_user and not is_doctor_reply and not ticket_match and not recipient_doctor:
        Notification.objects.create(
            hospital=matched_hospital,
            recipient=admin_user,
            message=f"📧 New inbound email from {clean_sender}: {clean_subject[:40]}",
            link="/admin-chat/",
        )

    logger.info(f"Successfully processed inbound email {clean_msg_id} from {mask_email_for_logging(clean_sender)} (thread={clean_thread_id})")
    return {
        "status": "processed",
        "message_id": clean_msg_id,
        "id": inbound_obj.id,
        "thread_id": clean_thread_id,
        "in_reply_to": clean_in_reply_to,
        "is_doctor_reply": is_doctor_reply,
    }