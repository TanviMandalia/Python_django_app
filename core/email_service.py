"""
Central Email Service & Dynamic Sender Resolution Engine for PhysioRehab.

Provides:
1. Multi-account sender resolution (Platform, Clinic, Doctor, Support, Notification).
2. Strict tenant isolation (Clinic A cannot send through Clinic B's account).
3. Purpose-based routing (Appointments -> Clinic; Password Reset -> Platform; Support -> Support account).
4. Dynamic SMTP / API connection acquisition per EmailAccount with Fernet-decrypted credentials.
5. Threading preservation and audit logging with masked PII.
"""

import uuid
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

from .models import EmailAccount, EmailLog, Hospital
from .crypto import encrypt_credential, decrypt_credential

logger = logging.getLogger(__name__)


class EmailPurpose:
    PLATFORM_SYSTEM = "PLATFORM_SYSTEM"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    APPOINTMENT_CONFIRMATION = "APPOINTMENT_CONFIRMATION"
    APPOINTMENT_UPDATED = "APPOINTMENT_UPDATED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    DOCTOR_COMMUNICATION = "DOCTOR_COMMUNICATION"
    PATIENT_NOTIFICATION = "PATIENT_NOTIFICATION"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    STAFF_WELCOME = "STAFF_WELCOME"
    INVOICE_RECEIPT = "INVOICE_RECEIPT"
    SUBSCRIPTION_SUCCESS = "SUBSCRIPTION_SUCCESS"
    SUBSCRIPTION_WARNING = "SUBSCRIPTION_WARNING"
    SUPPORT_TICKET = "SUPPORT_TICKET"


def resolve_email_account(purpose=None, hospital=None, doctor=None, user=None) -> EmailAccount:
    """
    Resolve the authoritative EmailAccount for sending based on context.
    
    Resolution Priority:
    1. Doctor-specific account (if doctor provided and has active EmailAccount)
    2. Clinic-specific account (if hospital provided and has active EmailAccount)
       - First matches specific purpose type (e.g. NOTIFICATION for patient notifications)
       - Next matches clinic default
    3. Platform-wide account (for platform purposes or allowed fallback)
    4. Fallback in-memory EmailAccount initialized from settings if no DB account configured.
    
    CRITICAL SECURITY INVARIANT:
    Never use an unrelated hospital's EmailAccount under any circumstances.
    """
    # 0. Purpose-Specific Global Routing (Platform Auth / Support)
    if purpose in (
        EmailPurpose.PASSWORD_RESET,
        "password_reset",
        "otp_verification",
        EmailPurpose.PLATFORM_SYSTEM,
        "platform",
    ):
        plat_acc = EmailAccount.objects.filter(
            scope_type="platform", is_active=True
        ).order_by("-is_default").first()
        if plat_acc:
            return plat_acc

    if purpose in (EmailPurpose.SUPPORT_TICKET, "support"):
        supp_acc = (
            EmailAccount.objects.filter(account_type="SUPPORT", is_active=True).first()
            or EmailAccount.objects.filter(scope_type="platform", is_active=True)
            .order_by("-is_default")
            .first()
        )
        if supp_acc:
            return supp_acc

    # 1. Doctor-specific account
    if doctor:
        doc_account = EmailAccount.objects.filter(
            user=doctor, is_active=True
        ).first()
        if doc_account:
            return doc_account

    # 2. Clinic-specific account
    if hospital:
        clinic_accounts = EmailAccount.objects.filter(
            hospital=hospital, is_active=True
        )
        if purpose in (EmailPurpose.PATIENT_NOTIFICATION, "notification"):
            notif_acc = clinic_accounts.filter(account_type="NOTIFICATION").first()
            if notif_acc:
                return notif_acc
        
        default_acc = clinic_accounts.filter(is_default=True).first()
        if default_acc:
            return default_acc
        
        first_clinic_acc = clinic_accounts.first()
        if first_clinic_acc:
            return first_clinic_acc

    # 3. Platform account (for platform/system actions or allowed platform fallback)
    platform_accounts = EmailAccount.objects.filter(
        scope_type="platform", is_active=True
    )
    if purpose in (EmailPurpose.SUPPORT_TICKET, "support"):
        supp_acc = platform_accounts.filter(account_type="SUPPORT").first()
        if supp_acc:
            return supp_acc

    platform_default = platform_accounts.filter(is_default=True).first()
    if platform_default:
        return platform_default

    first_platform = platform_accounts.first()
    if first_platform:
        return first_platform

    # 4. Virtual Fallback Account based on active settings (guarantees backward compatibility)
    fallback = EmailAccount(
        name="System Default SMTP",
        account_type="PLATFORM" if not hospital else "CLINIC",
        scope_type="platform" if not hospital else "hospital",
        hospital=hospital,
        host=getattr(settings, "EMAIL_HOST", "smtp.gmail.com"),
        port=getattr(settings, "EMAIL_PORT", 587),
        use_tls=getattr(settings, "EMAIL_USE_TLS", True),
        use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
        username=getattr(settings, "EMAIL_HOST_USER", "noreply@physiorehab.com"),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@physiorehab.com"),
        from_name=getattr(settings, "CLINIC_NAME", "PhysioRehab Clinic") if not hospital else hospital.name,
        is_active=True,
        is_default=True,
    )
    fallback.set_password(getattr(settings, "EMAIL_HOST_PASSWORD", ""))
    return fallback


def send_email_via_account(
    account: EmailAccount,
    subject: str,
    body_text: str,
    recipient_list,
    html_body: str = None,
    reply_to: str = None,
    in_reply_to: str = None,
    thread_id: str = None,
    attachments=None,
    purpose: str = "transactional",
    hospital=None,
) -> bool:
    """
    Send an isolated email using the dynamic connection and credentials of the specified EmailAccount.
    """
    from .email_utils import (
        validate_recipient_email,
        sanitize_header_value,
        mask_email_for_logging,
        render_html_wrapper,
    )

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
    
    # Formulate authoritative sender
    from_name = account.from_name or getattr(settings, "CLINIC_NAME", "PhysioRehab")
    clean_from_name = sanitize_header_value(from_name)
    from_email = f"{clean_from_name} <{account.from_email}>" if clean_from_name else account.from_email

    effective_reply_to = reply_to or account.reply_to
    reply_to_list = [sanitize_header_value(effective_reply_to)] if effective_reply_to else None

    if not html_body:
        escaped_body = escape(body_text).replace("\n", "<br>")
        html_body = render_html_wrapper(clean_subject, f"<p>{escaped_body}</p>")

    effective_hospital = hospital or account.hospital

    # Obtain dynamic connection for this specific account
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
                subject=clean_subject,
                body=body_text,
                from_email=from_email,
                to=[recipient],
                headers=headers,
                reply_to=reply_to_list,
                connection=connection,
            )
            email_msg.attach_alternative(html_body, "text/html")

            if attachments:
                for att in attachments:
                    if isinstance(att, tuple) and len(att) >= 2:
                        att_name, att_content = att[0], att[1]
                        att_mime = att[2] if len(att) > 2 else "application/octet-stream"
                        email_msg.attach(sanitize_header_value(att_name), att_content, att_mime)

            email_msg.send(fail_silently=False)

            # Record in EmailLog
            try:
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    sender_email=account.from_email,
                    hospital=effective_hospital,
                    email_type=purpose,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="sent",
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception as log_err:
                logger.debug(f"EmailLog record failed: {log_err}")

            masked_rec = mask_email_for_logging(recipient)
            logger.info(
                f"Email sent successfully via account '{account.name}' ({account.from_email}) "
                f"to {masked_rec}: '{clean_subject}'"
            )

        except Exception as e:
            success_all = False
            logger.error(
                f"Failed to send email via account '{account.name}' to {mask_email_for_logging(recipient)}: {e}"
            )
            try:
                EmailLog.objects.create(
                    account=account if getattr(account, "pk", None) else None,
                    sender_email=account.from_email,
                    hospital=effective_hospital,
                    email_type=purpose,
                    recipient_email=recipient,
                    subject=clean_subject,
                    status="failed",
                    error_category=type(e).__name__,
                    message_id=msg_id,
                    thread_id=clean_thread_id,
                    sent_at=timezone.now(),
                )
            except Exception as log_err:
                logger.debug(f"EmailLog failure record failed: {log_err}")

    return success_all


def test_account_connection(account: EmailAccount, test_recipient: str) -> tuple[bool, str]:
    """
    Test real connection and deliver a diagnostic test email using the EmailAccount.
    Never exposes passwords or sensitive credentials in the response.
    """
    subject = f"Test Email from {account.name}"
    body = (
        f"This is a verified test email sent from the PhysioRehab Email Service.\n\n"
        f"Account Name: {account.name}\n"
        f"Sender: {account.from_email}\n"
        f"Account Type: {account.get_account_type_display()}\n"
        f"Scope: {account.get_scope_type_display()}\n"
        f"Timestamp: {timezone.now().isoformat()}\n\n"
        f"If you received this email, the SMTP configuration and credentials are functioning correctly."
    )
    try:
        ok = send_email_via_account(
            account=account,
            subject=subject,
            body_text=body,
            recipient_list=[test_recipient],
            purpose="TEST_EMAIL",
            hospital=account.hospital,
        )
        if ok:
            return True, f"✅ Test email successfully dispatched to {test_recipient} via {account.from_email}."
        return False, "❌ Email dispatch failed. Please verify SMTP host, port, and security settings."
    except Exception as e:
        return False, f"❌ Connection error: {type(e).__name__} - {str(e)}"


# Tell pytest not to discover this helper function as a test
test_account_connection.__test__ = False

