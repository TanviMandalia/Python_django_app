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
import socket
import ssl
import smtplib
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


def test_account_connection(account: EmailAccount, test_recipient: str, force_smtp: bool = False) -> tuple[bool, str]:
    """
    Test live SMTP connection, TLS negotiation, authentication, and test message dispatch.
    Returns (success: bool, diagnostic_message: str).
    Never exposes passwords or sensitive credentials in the response or logs.
    """
    from .email_utils import validate_recipient_email, sanitize_header_value, render_html_wrapper

    # 1. Validate Recipient Email
    try:
        clean_recipient = validate_recipient_email(test_recipient)
    except ValidationError:
        return False, f"❌ Invalid recipient email address: '{test_recipient}'. Please provide a valid email format."

    # 2. Validate Account Configuration Fields
    if not account.host or not account.username or not account.from_email:
        return False, "❌ Incomplete SMTP configuration. Host, Username, and From Email are required."

    try:
        port = int(account.port)
        if not (1 <= port <= 65535):
            raise ValueError()
    except (ValueError, TypeError):
        return False, f"❌ Invalid SMTP port ({account.port}). Port must be between 1 and 65535."

    password = account.get_password()
    if not password:
        return False, "❌ Missing credentials: No SMTP password or App Password is configured. Please enter and save credentials before testing."

    # Mutual exclusivity defense
    if port == 587 and account.use_ssl:
        return False, "❌ Port 587 requires STARTTLS (TLS), not implicit SSL. Please uncheck SSL and enable TLS."
    if port == 465 and account.use_tls:
        return False, "❌ Port 465 requires SSL, not STARTTLS. Please uncheck TLS and enable SSL."

    backend_name = getattr(settings, "EMAIL_BACKEND", "")
    is_locmem_test = ("locmem" in backend_name and not force_smtp)

    # 3. Establish Connection & Authenticate
    try:
        connection = account.get_connection(fail_silently=False, timeout=15, force_smtp=force_smtp)
        connection.open()
    except smtplib.SMTPAuthenticationError as auth_err:
        code = getattr(auth_err, "smtp_code", 535)
        raw_err = getattr(auth_err, "smtp_error", b"")
        err_str = raw_err.decode("utf-8", "ignore") if isinstance(raw_err, bytes) else str(raw_err or auth_err)
        logger.warning(f"SMTP Auth failure for {account.username} on {account.host}: code={code}")
        if "BadCredentials" in err_str or "5.7.8" in err_str or code == 535:
            return False, (
                f"❌ SMTP Authentication Failed (Code 535): Username or App Password rejected by {account.host}. "
                "For Gmail, verify that 2-Step Verification is active and supply a valid, newly generated "
                "16-character Google App Password (not your personal Google account password)."
            )
        return False, f"❌ SMTP Authentication Failed (Code {code}): {err_str}"
    except smtplib.SMTPServerDisconnected as disc_err:
        logger.warning(f"SMTP Server disconnected for {account.host}:{account.port}: {disc_err}")
        if "gmail" in account.host.lower() or getattr(account, "provider", "") == "gmail":
            return False, (
                f"❌ SMTP Server Disconnected (Gmail Authentication Rejected): The server at "
                f"{account.host}:{account.port} accepted the connection and TLS handshake, but closed "
                "the socket during authentication. Google SMTP immediately severs the connection when "
                "presented with an invalid, expired, or revoked 16-character Google App Password. "
                "Action needed: Click 'Edit' on this account, paste your newly generated 16-character "
                "Google App Password into the Password field, click 'Save Account', and then test again."
            )
        return False, (
            f"❌ SMTP Server Disconnected: The server at {account.host}:{account.port} unexpectedly "
            "closed the connection. Common causes: invalid/revoked credentials, port/encryption mode "
            "mismatch (Port 587 STARTTLS vs Port 465 SSL), or security restrictions on the mail host."
        )
    except smtplib.SMTPConnectError as conn_err:
        logger.warning(f"SMTP connection error for {account.host}:{account.port}: {conn_err}")
        return False, f"❌ SMTP Connection Error: Could not connect to {account.host}:{account.port}. Verify host name, port, and firewall rules."
    except (socket.timeout, TimeoutError):
        logger.warning(f"SMTP connection timeout for {account.host}:{account.port}")
        return False, f"❌ Connection Timeout: Connection to {account.host}:{account.port} timed out after 15 seconds. Check outbound network access to SMTP ports."
    except (socket.gaierror, ConnectionRefusedError) as net_err:
        logger.warning(f"Network error connecting to {account.host}:{account.port}: {net_err}")
        return False, f"❌ Network Error: Could not reach {account.host}:{account.port} ({type(net_err).__name__}). Check DNS resolution and internet connectivity."
    except ssl.SSLError as ssl_err:
        logger.warning(f"TLS/SSL negotiation error for {account.host}:{account.port}: {ssl_err}")
        return False, f"❌ TLS/SSL Negotiation Error: {ssl_err}. Verify encryption settings (STARTTLS on port 587 or SSL on port 465)."
    except Exception as e:
        logger.exception(f"Unexpected connection error for account '{account.name}': {e}")
        return False, f"❌ SMTP Connection Error: {type(e).__name__} - {str(e)}"

    # 4. Construct Identifiable Test Message
    sender_title = account.from_name or getattr(settings, "CLINIC_NAME", "TechCraft")
    clean_sender_title = sanitize_header_value(sender_title)
    from_header = f"{clean_sender_title} <{account.from_email}>" if clean_sender_title else account.from_email
    subject = f"SMTP Configuration Test - {clean_sender_title}"
    msg_id = f"{uuid.uuid4().hex}@{getattr(account, 'host', 'localhost')}"
    now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    body_text = (
        f"SMTP Configuration Test Verification\n"
        f"------------------------------------\n"
        f"Account Label : {account.name}\n"
        f"SMTP Server   : {account.host}:{account.port}\n"
        f"Security Mode : {'STARTTLS (Port 587)' if account.use_tls else 'SSL (Port 465)' if account.use_ssl else 'Plain'}\n"
        f"SMTP Username : {account.username}\n"
        f"From Sender   : {from_header}\n"
        f"Recipient     : {clean_recipient}\n"
        f"Dispatched At : {now_str}\n"
        f"Message ID    : <{msg_id}>\n\n"
        f"Verification Result: The remote SMTP gateway connection, TLS negotiation, and credentials authenticated successfully.\n"
        f"This test email confirms that your outgoing mail pipeline is operational."
    )

    html_content = (
        f"<p><strong>SMTP Configuration Test Verification</strong></p>"
        f"<div class=\"box\">"
        f"<table style=\"width:100%; border-collapse:collapse; font-size:14px;\">"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Account Label:</td><td style=\"font-weight:600;\">{escape(account.name)}</td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">SMTP Server:</td><td style=\"font-weight:600;\">{escape(account.host)}:{account.port}</td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Security Mode:</td><td><span class=\"badge\">{'STARTTLS (Port 587)' if account.use_tls else 'SSL (Port 465)' if account.use_ssl else 'Plain'}</span></td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Authenticated:</td><td style=\"font-weight:600;\">{escape(account.username)}</td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Sender 'From':</td><td>{escape(from_header)}</td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Recipient:</td><td>{escape(clean_recipient)}</td></tr>"
        f"<tr><td style=\"padding:4px 0; color:#64748b;\">Dispatched At:</td><td>{now_str}</td></tr>"
        f"</table>"
        f"</div>"
        f"<p style=\"color:#059669; font-weight:600;\">"
        f"The SMTP connection, TLS handshake, and authentication checks have passed successfully."
        f"</p>"
    )
    html_wrapped = render_html_wrapper(subject, html_content)

    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_header,
        to=[clean_recipient],
        headers={"Message-ID": f"<{msg_id}>", "X-Mailer": "PhysioRehab-Email-Gateway"},
        connection=connection,
    )
    email_msg.attach_alternative(html_wrapped, "text/html")

    # 5. Dispatch Message
    try:
        sent_count = connection.send_messages([email_msg])
        if sent_count < 1 and not is_locmem_test:
            return False, "❌ SMTP server did not accept the message for delivery."
    except smtplib.SMTPRecipientsRefused:
        return False, f"❌ Recipient Rejected: The SMTP server refused recipient '{clean_recipient}'."
    except smtplib.SMTPSenderRefused:
        return False, (
            f"❌ Sender Rejected: The SMTP server refused sender '{account.from_email}'. "
            f"For Gmail, the 'From' address must match the authenticated account ({account.username}) or an authorized alias."
        )
    except smtplib.SMTPDataError as data_err:
        return False, f"❌ SMTP Data Error: Server rejected message payload: {data_err}"
    except Exception as send_err:
        logger.exception(f"Failed to transmit test message for {account.name}: {send_err}")
        return False, f"❌ Transmission Error: {type(send_err).__name__} - {str(send_err)}"
    finally:
        try:
            connection.close()
        except Exception:
            pass

    # 6. Record Audit Log
    try:
        EmailLog.objects.create(
            account=account if getattr(account, "pk", None) else None,
            sender_email=account.from_email,
            hospital=account.hospital,
            email_type="TEST_EMAIL",
            recipient_email=clean_recipient,
            subject=subject,
            status="sent",
            message_id=msg_id,
            sent_at=timezone.now(),
        )
    except Exception as log_err:
        logger.debug(f"EmailLog audit creation failed: {log_err}")

    # 7. Return Result Distinguishing SMTP Acceptance from Inbox Delivery
    return True, (
        f"✅ SMTP connection successful and test message accepted by {account.host}:{account.port}! "
        f"Dispatched to '{clean_recipient}' from '{account.from_email}'. "
        "(Note: SMTP acceptance confirms the server accepted the message; delivery to inbox depends on recipient mail provider.)"
    )


# Tell pytest not to discover this helper function as a test
test_account_connection.__test__ = False

