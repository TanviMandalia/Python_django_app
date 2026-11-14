"""
Central Gmail API (OAuth 2.0) Shared Backend Service for PhysioRehab.

Provides:
1. Official Google Gmail API integration using OAuth 2.0 Web Server flow.
2. Separate configured mailbox authorization for platform and clinic Gmail inboxes.
3. Automated post-commit email dispatch for bookings, confirmations, and supported status transitions.
4. Robust idempotency protection against duplicate emails on retries.
5. Inbound message synchronization with Gmail API, persisting to PostgreSQL InboundEmail.
6. Safe token refresh and revoked grant handling without exposing secrets or PII.
"""

import base64
import email
from email.message import EmailMessage
from email.utils import formataddr
import json
import logging
import re
import uuid
from typing import Dict, Any, Optional, Tuple, List

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google_auth_oauthlib.flow

from .models import (
    GmailOAuthCredential,
    EmailLog,
    Hospital,
    PublicAppointmentRequest,
    Appointment,
)
from .email_utils import (
    mask_email_for_logging,
    sanitize_header_value,
    validate_recipient_email,
    process_inbound_email_payload,
)

logger = logging.getLogger(__name__)

# Official minimal scopes required for sending notifications and reading inbound replies
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SCOPES = [
    GMAIL_SEND_SCOPE,
    GMAIL_READONLY_SCOPE,
]
SHARED_GMAIL_MAILBOX = "physio.rehab.guj@gmail.com"


def get_configured_mailboxes() -> List[str]:
    """Configured inboxes eligible for Gmail OAuth and synchronization."""
    configured = getattr(settings, "GMAIL_INBOUND_MAILBOXES", "")
    mailboxes = [item.strip().lower() for item in str(configured).split(",") if item.strip()]
    if not mailboxes:
        mailboxes = [get_shared_mailbox_address()]
    return list(dict.fromkeys(mailboxes))


def get_mailboxes_for_user(user) -> List[str]:
    """Return only the Gmail inbox owned by the signed-in administrator role."""
    if not getattr(user, "is_authenticated", False):
        return []

    if getattr(user, "is_superuser", False):
        role_mailbox = getattr(settings, "PLATFORM_SUPERADMIN_EMAIL", "techcraft1215@gmail.com")
    elif hasattr(user, "clinic_admin_profile"):
        role_mailbox = get_shared_mailbox_address()
    else:
        return []

    role_mailbox = str(role_mailbox or "").strip().lower()
    return [role_mailbox] if role_mailbox in get_configured_mailboxes() else []


def user_can_manage_mailbox(user, mailbox: str) -> bool:
    """Keep platform and clinic OAuth grants isolated to their owning admin."""
    return (mailbox or "").strip().lower() in get_mailboxes_for_user(user)


class GmailServiceError(Exception):
    """Base exception for Gmail API operations."""
    pass


class GmailConfigError(GmailServiceError):
    """Raised when Gmail configuration or environment variables are missing or invalid."""
    pass


class GmailAuthError(GmailServiceError):
    """Raised when Gmail OAuth authorization is missing, expired, or revoked."""
    pass


class GmailDeliveryError(GmailServiceError):
    """Raised when Gmail API message sending fails."""
    pass


# ═════════════════════════════════════════════════════════════════════════════
# 1. OAUTH 2.0 WEB SERVER FLOW HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def get_shared_mailbox_address() -> str:
    """Return the configured shared Gmail mailbox address."""
    return getattr(settings, "GMAIL_SHARED_MAILBOX", "physio.rehab.guj@gmail.com").strip().lower()


def get_oauth_client_config(redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Build the OAuth 2.0 client config dictionary from environment variables."""
    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    effective_redirect_uri = redirect_uri or getattr(
        settings,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/admin-settings/gmail/callback/",
    ).strip()

    if not client_id or not client_secret:
        raise GmailConfigError(
            "Google OAuth Client ID or Client Secret is not configured. "
            "Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in environment variables."
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [effective_redirect_uri],
        }
    }


def get_authorization_url(
    redirect_uri_or_request: Optional[Any] = None,
    state: Optional[str] = None,
    mailbox: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Generate Google OAuth 2.0 authorization URL for the shared clinic mailbox.
    Requests offline access to obtain a refresh token.
    """
    redirect_uri = None
    if redirect_uri_or_request:
        if isinstance(redirect_uri_or_request, str):
            redirect_uri = redirect_uri_or_request
        elif hasattr(redirect_uri_or_request, "build_absolute_uri"):
            from django.urls import reverse
            try:
                redirect_uri = redirect_uri_or_request.build_absolute_uri(reverse("admin_gmail_oauth_callback"))
            except Exception:
                redirect_uri = None

    config = get_oauth_client_config(redirect_uri=redirect_uri)
    effective_redirect_uri = redirect_uri or config["web"]["redirect_uris"][0]

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        config,
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = effective_redirect_uri

    auth_url, generated_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        login_hint=(mailbox or get_shared_mailbox_address()).strip().lower(),
    )
    return auth_url, generated_state


def exchange_code_for_tokens(
    code_or_request: Any,
    code: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    hospital: Optional[Hospital] = None,
    expected_email: Optional[str] = None,
) -> GmailOAuthCredential:
    """
    Exchange the OAuth authorization code for credentials, inspect the authorized
    profile email, and store encrypted tokens in PostgreSQL.
    """
    actual_code = code
    effective_redirect_uri = redirect_uri

    if isinstance(code_or_request, str) and not actual_code:
        actual_code = code_or_request
    elif hasattr(code_or_request, "build_absolute_uri"):
        from django.urls import reverse
        try:
            effective_redirect_uri = effective_redirect_uri or code_or_request.build_absolute_uri(
                reverse("admin_gmail_oauth_callback")
            )
        except Exception:
            pass
        if not actual_code and hasattr(code_or_request, "GET"):
            actual_code = code_or_request.GET.get("code")

    if not actual_code:
        raise GmailAuthError("Missing authorization code for token exchange.")

    config = get_oauth_client_config(redirect_uri=effective_redirect_uri)
    final_redirect_uri = effective_redirect_uri or config["web"]["redirect_uris"][0]

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        config,
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = final_redirect_uri

    try:
        flow.fetch_token(code=actual_code)
    except Exception as exc:
        logger.error("Google OAuth token exchange failed (%s).", type(exc).__name__)
        raise GmailAuthError("OAuth token exchange failed. Check the Google OAuth client and redirect URI configuration.") from None

    creds = flow.credentials

    # Verify authorized email address via Gmail API users().getProfile()
    try:
        temp_service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = temp_service.users().getProfile(userId="me").execute()
        authorized_email = profile.get("emailAddress", "").strip().lower()
        initial_history_id = str(profile.get("historyId", ""))
    except Exception as exc:
        logger.warning("Could not verify Gmail account during OAuth exchange: %s", type(exc).__name__)
        raise GmailAuthError("Could not verify the Google account. No mailbox credentials were saved.") from exc

    target_email = authorized_email or get_shared_mailbox_address()
    if expected_email and target_email.lower() != expected_email.strip().lower():
        raise GmailAuthError("The authorized Google account does not match the selected mailbox.")
    if target_email.lower() not in get_configured_mailboxes():
        raise GmailAuthError("This Google account is not an enabled mailbox for this application.")

    # Persist or update credential in PostgreSQL
    credential, _ = GmailOAuthCredential.objects.get_or_create(
        email=target_email,
        defaults={"hospital": hospital, "encrypted_refresh_token": ""},
    )

    if hospital and not credential.hospital:
        credential.hospital = hospital

    if creds.refresh_token:
        credential.set_refresh_token(creds.refresh_token)
    elif not credential.encrypted_refresh_token:
        raise GmailAuthError("Google did not return a refresh token. Revoke this app's access in Google Account settings and authorize again.")

    if creds.token:
        credential.set_access_token(creds.token)

    if creds.expiry:
        if timezone.is_naive(creds.expiry):
            import datetime
            credential.token_expiry = creds.expiry.replace(tzinfo=datetime.timezone.utc)
        else:
            credential.token_expiry = creds.expiry
    else:
        credential.token_expiry = None
    credential.scopes = list(creds.scopes or GMAIL_SCOPES)
    if initial_history_id:
        credential.history_id = initial_history_id
    credential.is_active = True
    credential.authorized_at = timezone.now()
    credential.last_error = ""
    credential.save()

    logger.info(f"Successfully authorized Gmail OAuth for mailbox: {mask_email_for_logging(target_email)}")
    return credential


# ═════════════════════════════════════════════════════════════════════════════
# 2. CREDENTIAL MANAGEMENT & AUTO-REFRESH
# ═════════════════════════════════════════════════════════════════════════════

def get_gmail_credential_model(mailbox: Optional[str] = None) -> Optional[GmailOAuthCredential]:
    """Retrieve the active GmailOAuthCredential record for the selected mailbox."""
    target_email = (mailbox or get_shared_mailbox_address()).strip().lower()
    return GmailOAuthCredential.objects.filter(email__iexact=target_email, is_active=True).first()


def get_gmail_credentials(mailbox: Optional[str] = None) -> Tuple[Credentials, GmailOAuthCredential]:
    """
    Retrieve valid Google OAuth Credentials, automatically refreshing expired access tokens.
    Handles revoked authorization safely by marking the credential inactive.
    """
    target_email = (mailbox or get_shared_mailbox_address()).strip().lower()
    credential = get_gmail_credential_model(target_email)

    if not credential or not credential.encrypted_refresh_token:
        raise GmailAuthError(
            f"No active Gmail OAuth authorization found for {mask_email_for_logging(target_email)}. "
            "The mailbox owner must authorize the application once via the Admin Settings portal."
        )

    refresh_token = credential.get_refresh_token()
    access_token = credential.get_access_token()

    if not refresh_token:
        credential.is_active = False
        credential.last_error = "Decryption failed: Refresh token is empty or invalid."
        credential.save(update_fields=["is_active", "last_error", "updated_at"])
        raise GmailAuthError(f"Refresh token decryption failed for {mask_email_for_logging(target_email)}.")

    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

    expiry_naive = credential.token_expiry
    if expiry_naive:
        if timezone.is_aware(expiry_naive):
            import datetime
            expiry_naive = expiry_naive.astimezone(datetime.timezone.utc).replace(tzinfo=None)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=credential.scopes or GMAIL_SCOPES,
        expiry=expiry_naive,
    )

    # Check if access token is expired or close to expiry
    if credential.is_token_expired or not creds.valid:
        try:
            logger.debug(f"Refreshing expired Gmail access token for {mask_email_for_logging(target_email)}...")
            creds.refresh(Request())

            # Update cached access token and expiry in PostgreSQL
            credential.set_access_token(creds.token)
            if creds.expiry:
                if timezone.is_naive(creds.expiry):
                    import datetime
                    credential.token_expiry = creds.expiry.replace(tzinfo=datetime.timezone.utc)
                else:
                    credential.token_expiry = creds.expiry
            credential.last_error = ""
            credential.save(update_fields=["encrypted_access_token", "token_expiry", "last_error", "updated_at"])
            logger.info(f"Successfully refreshed Gmail access token for {mask_email_for_logging(target_email)}.")
        except RefreshError as exc:
            sanitized_err = re.sub(r'(GOCSPX-[^\s]+|client_secret=[^\s]+)', '***', str(exc))
            credential.is_active = False
            credential.last_error = f"Token refresh failed: {sanitized_err}"
            credential.save(update_fields=["is_active", "last_error", "updated_at"])
            logger.error(f"Gmail OAuth refresh token revoked or expired: {sanitized_err}")
            raise GmailAuthError(f"Gmail OAuth authorization revoked or expired: {sanitized_err}")
        except Exception as exc:
            sanitized_err = str(exc)[:200]
            credential.last_error = f"Token refresh exception: {sanitized_err}"
            credential.save(update_fields=["last_error", "updated_at"])
            raise GmailServiceError(f"Transient error refreshing Gmail token: {sanitized_err}")

    return creds, credential


def build_gmail_client(mailbox: Optional[str] = None):
    """Build and return an authorized googleapiclient Gmail service instance."""
    creds, _ = get_gmail_credentials(mailbox=mailbox)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def is_gmail_api_configured_and_active(mailbox: Optional[str] = None) -> bool:
    """Return True if Gmail OAuth integration is fully configured and active."""
    try:
        credential = get_gmail_credential_model(mailbox)
        return bool(credential and credential.is_authorized and credential.get_refresh_token())
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════════════
# 3. OUTGOING EMAIL DISPATCHER (OFFICIAL GMAIL API)
# ═════════════════════════════════════════════════════════════════════════════

def send_gmail_message(
    subject: str,
    body_text: str,
    to_email: str,
    html_content: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    attachments: Optional[List[Any]] = None,
    hospital: Optional[Hospital] = None,
    email_type: str = "transactional",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send an email via the official Gmail API (users().messages().send).
    
    Guarantees:
    - Idempotent: If idempotency_key was already successfully dispatched, skips duplicate.
    - Audited: Records outgoing delivery status in EmailLog.
    - Never exposes tokens, secrets, or unmasked patient PHI.
    - Does NOT silently mark failed sends as successful.
    """
    # 1. Idempotency Check
    if idempotency_key:
        clean_key = str(idempotency_key).strip()
        existing_log = EmailLog.objects.filter(
            message_id=clean_key,
            status="sent",
        ).first()
        if existing_log:
            logger.info(
                f"Skipping duplicate email dispatch (idempotency key '{clean_key}' "
                f"already sent to {mask_email_for_logging(to_email)})"
            )
            return {
                "success": True,
                "status": "duplicate_skipped",
                "duplicate": True,
                "message_id": existing_log.message_id,
                "thread_id": existing_log.thread_id,
            }

    # 2. Recipient Validation
    clean_to = validate_recipient_email(to_email)
    clean_subject = sanitize_header_value(subject)
    sender_mailbox = (from_email or get_shared_mailbox_address()).strip().lower()

    clinic_name = from_name or (hospital.name if hospital else getattr(settings, "CLINIC_NAME", "Dr. Dhvani Patalia Physio Rehab"))
    formatted_from = formataddr((sanitize_header_value(clinic_name), sender_mailbox))

    # 3. Build RFC 2822 MIME message
    mime_msg = EmailMessage()
    mime_msg["From"] = formatted_from
    mime_msg["To"] = clean_to
    mime_msg["Subject"] = clean_subject

    # Threading and custom headers
    custom_headers = dict(headers or {})
    gen_msg_id = clean_key if idempotency_key else f"{uuid.uuid4().hex}@{getattr(settings, 'GMAIL_SHARED_MAILBOX', 'gmail.com')}"
    if "Message-ID" not in custom_headers:
        mime_msg["Message-ID"] = f"<{gen_msg_id}>"

    for h_name, h_val in custom_headers.items():
        if h_name.lower() not in ("from", "to", "subject"):
            mime_msg[h_name] = sanitize_header_value(str(h_val))

    mime_msg.set_content(body_text)
    if html_content:
        mime_msg.add_alternative(html_content, subtype="html")

    # Attachments
    if attachments:
        for att in attachments:
            if isinstance(att, tuple) and len(att) >= 2:
                att_name = sanitize_header_value(att[0])
                att_bytes = att[1]
                mime_msg.add_attachment(
                    att_bytes,
                    maintype="application",
                    subtype="octet-stream",
                    filename=att_name,
                )

    raw_bytes = mime_msg.as_bytes()
    encoded_raw = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

    # 4. Dispatch via Gmail API
    try:
        service = build_gmail_client(mailbox=sender_mailbox)
        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded_raw},
        ).execute()

        gmail_id = result.get("id", "")
        thread_id = result.get("threadId", "")

        # Record successful EmailLog in PostgreSQL
        _is_otp = bool(email_type and ("otp" in str(email_type).lower() or "verification" in str(email_type).lower()))
        _expires_at = (timezone.now() + timezone.timedelta(hours=24)) if _is_otp else None

        EmailLog.objects.create(
            direction="outgoing",
            sender_email=sender_mailbox,
            hospital=hospital,
            email_type=email_type,
            recipient_email=clean_to,
            subject=clean_subject,
            status="sent",
            is_otp=_is_otp,
            expires_at=_expires_at,
            message_id=idempotency_key or gmail_id,
            thread_id=thread_id,
            sent_at=timezone.now(),
        )

        logger.info(
            f"Gmail API email sent successfully to {mask_email_for_logging(clean_to)}: "
            f"'{clean_subject}' [Gmail ID: {gmail_id}]"
        )
        return {
            "success": True,
            "status": "sent",
            "duplicate": False,
            "message_id": gmail_id,
            "thread_id": thread_id,
        }

    except Exception as exc:
        sanitized_err = re.sub(
            r'(re_[a-zA-Z0-9_\-]{10,}|Bearer\s+[^\s]+|client_secret=[^\s]+)',
            '***',
            str(exc)[:400],
        )
        err_cat = exc.__class__.__name__

        # Record failed delivery in EmailLog (NEVER silently mark as successful)
        try:
            EmailLog.objects.create(
                direction="outgoing",
                sender_email=sender_mailbox,
                hospital=hospital,
                email_type=email_type,
                recipient_email=clean_to,
                subject=clean_subject,
                status="failed",
                error_category=err_cat,
                error_details=sanitized_err,
                message_id=idempotency_key or f"failed_{uuid.uuid4().hex[:8]}",
                sent_at=timezone.now(),
            )
        except Exception as log_err:
            logger.debug(f"EmailLog failed status recording failed: {log_err}")

        logger.error(
            f"Gmail API delivery failed to {mask_email_for_logging(clean_to)}: {err_cat} - {sanitized_err}"
        )
        raise GmailServiceError(f"Gmail API delivery failed: {err_cat} - {sanitized_err}") from exc


# ═════════════════════════════════════════════════════════════════════════════
# 4. POST-COMMIT AUTOMATED BOOKING NOTIFICATIONS (REQUIREMENT 2)
# ═════════════════════════════════════════════════════════════════════════════

def dispatch_booking_created_notifications_post_commit(public_request_id: int):
    """
    Executed exclusively AFTER the database transaction commits.
    Dispatches:
      1. Booking confirmation / receipt to the customer's email.
      2. New appointment notification to physio.rehab.guj@gmail.com (& active clinic recipients).
    Prevents duplicate messages if a request is retried.
    """
    try:
        req_obj = PublicAppointmentRequest.objects.get(id=public_request_id)
    except PublicAppointmentRequest.DoesNotExist:
        logger.warning(f"PublicAppointmentRequest ID {public_request_id} not found during post-commit notification.")
        return False

    from .email_utils import send_public_appointment_request_notification

    # Idempotency check key
    idempotency_key = f"public_booking_{req_obj.reference_id}_created"
    if EmailLog.objects.filter(message_id=idempotency_key, status="sent").exists():
        logger.info(f"Public booking {req_obj.reference_id} created notification already sent. Skipping duplicate.")
        return True

    success = False
    try:
        success = bool(send_public_appointment_request_notification(req_obj))
        req_obj.email_notification_status = "sent" if success else "failed"
        req_obj.save(update_fields=["email_notification_status", "updated_at"])
    except Exception as exc:
        logger.error(f"Error in post-commit send_public_appointment_request_notification: {exc}")
        req_obj.email_notification_status = "failed"
        req_obj.notification_error = str(exc)[:200]
        req_obj.save(update_fields=["email_notification_status", "notification_error", "updated_at"])

    return success


def dispatch_appointment_created_notifications_post_commit(appointment_id: int):
    """
    Executed exclusively AFTER database transaction commits for internal Appointment creation.
    Dispatches:
      1. Appointment confirmation to patient.
      2. Alert to clinic recipients.
    Prevents duplicate messages if request is retried.
    """
    try:
        appt = Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        return False

    from .email_utils import (
        send_appointment_confirmation,
        send_appointment_status_update,
        send_admin_new_appointment_alert,
    )

    idempotency_key = f"appointment_{appt.id}_created"
    if EmailLog.objects.filter(message_id=idempotency_key, status="sent").exists():
        logger.info(f"Appointment {appt.id} created notification already sent. Skipping duplicate.")
        return True

    try:
        if appt.status == "pending":
            send_appointment_confirmation(appt)
        else:
            send_appointment_status_update(appt)
    except Exception as exc:
        logger.error(f"Post-commit appointment confirmation failed for appt {appt.id}: {exc}")

    try:
        send_admin_new_appointment_alert(appt)
    except Exception as exc:
        logger.error(f"Post-commit clinic alert failed for appt {appt.id}: {exc}")

    return True


def dispatch_appointment_status_notifications_post_commit(appointment_id: int, new_status: str):
    """
    Executed exclusively AFTER database transaction commits when appointment status changes.
    Only dispatches for actions and status changes supported by existing app requirements:
    'confirmed', 'completed', 'cancelled'.
    """
    try:
        appt = Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        return False

    if new_status not in ("confirmed", "completed", "cancelled"):
        return False

    from .email_utils import send_appointment_status_update

    idempotency_key = f"appointment_{appt.id}_status_{new_status}"
    if EmailLog.objects.filter(message_id=idempotency_key, status="sent").exists():
        logger.info(f"Appointment {appt.id} status notification for '{new_status}' already sent. Skipping duplicate.")
        return True

    try:
        return bool(send_appointment_status_update(appt))
    except Exception as exc:
        logger.error(f"Post-commit appointment status update failed for appt {appt.id} ({new_status}): {exc}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# 5. INBOUND GMAIL SYNCHRONIZATION ENGINE (REQUIREMENT 6)
# ═════════════════════════════════════════════════════════════════════════════

def _extract_header(headers_list: List[Dict[str, str]], header_name: str) -> str:
    """Extract a header value from a Gmail message payload headers list."""
    target = header_name.lower()
    for h in headers_list:
        if h.get("name", "").lower() == target:
            return h.get("value", "").strip()
    return ""


def _parse_gmail_payload_body(payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Recursively parse a Gmail message payload to extract body text, HTML, and attachment metadata."""
    body_text = ""
    body_html = ""
    attachments: List[Dict[str, Any]] = []

    def _walk(part: Dict[str, Any]):
        nonlocal body_text, body_html
        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")
        body = part.get("body", {})

        if filename:
            attachments.append({
                "filename": filename,
                "size": body.get("size", 0),
                "content_type": mime_type,
                "attachment_id": body.get("attachmentId", ""),
            })

        data_b64 = body.get("data")
        if data_b64:
            try:
                padded_b64 = data_b64 + "=" * (-len(data_b64) % 4)
                decoded = base64.urlsafe_b64decode(padded_b64.encode("ASCII")).decode("utf-8", errors="replace")
                if mime_type == "text/html":
                    if not body_html:
                        body_html = decoded
                else:
                    if not body_text:
                        body_text = decoded
            except Exception as e:
                logger.debug(f"Failed to decode part data: {e}")

        for subpart in part.get("parts", []):
            _walk(subpart)

    _walk(payload)
    return body_text, body_html, attachments


def sync_gmail_messages(
    mailbox: Optional[str] = None,
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Synchronize incoming emails from the selected Gmail mailbox via the Gmail API.
    Persists messages in PostgreSQL InboundEmail via process_inbound_email_payload().
    Guarantees idempotency and duplicate detection via RFC Message-ID.
    """
    target_email = (mailbox or get_shared_mailbox_address()).strip().lower()
    creds, credential = get_gmail_credentials(mailbox=target_email)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    synced_count = 0
    duplicate_count = 0
    error_count = 0

    message_ids: List[str] = []
    latest_history_id = credential.history_id

    # Try delta history sync if history_id is available
    if credential.history_id:
        try:
            history_resp = service.users().history().list(
                userId="me",
                startHistoryId=credential.history_id,
                historyTypes=["messageAdded"],
                maxResults=max_results,
            ).execute()

            for h_record in history_resp.get("history", []):
                for m_added in h_record.get("messagesAdded", []):
                    m_id = m_added.get("message", {}).get("id")
                    if m_id and m_id not in message_ids:
                        message_ids.append(m_id)

            latest_history_id = str(history_resp.get("historyId", latest_history_id))
        except HttpError as http_err:
            if http_err.resp.status == 404:
                logger.info(f"Gmail history ID {credential.history_id} expired. Falling back to query list.")
                message_ids = []
            else:
                logger.warning(f"Gmail history list error: {http_err}")

    # Fallback: query recent messages if history returned empty or expired
    if not message_ids:
        try:
            list_resp = service.users().messages().list(
                userId="me",
                q=f"to:{target_email} OR label:INBOX",
                maxResults=min(max_results, 25),
            ).execute()
            for m in list_resp.get("messages", []):
                m_id = m.get("id")
                if m_id and m_id not in message_ids:
                    message_ids.append(m_id)
        except Exception as exc:
            logger.error(f"Failed to query Gmail messages: {exc}")
            return {"status": "error", "error": str(exc)[:200]}

    # Process each message
    for msg_id in message_ids:
        try:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full",
            ).execute()

            if msg_data.get("historyId"):
                latest_history_id = str(msg_data.get("historyId"))

            payload = msg_data.get("payload", {})
            headers_list = payload.get("headers", [])
            headers_dict = {h.get("name", ""): h.get("value", "") for h in headers_list}

            msg_rfc_id = _extract_header(headers_list, "Message-ID") or f"gmail_{msg_id}"
            from_raw = _extract_header(headers_list, "From")
            to_raw = target_email

            import email.utils
            _, sender = email.utils.parseaddr(from_raw)
            if not sender:
                sender = from_raw

            _, recipient = email.utils.parseaddr(to_raw)
            if not recipient:
                recipient = target_email

            subject = _extract_header(headers_list, "Subject")
            in_reply_to = _extract_header(headers_list, "In-Reply-To")
            references = _extract_header(headers_list, "References")
            thread_id = msg_data.get("threadId", "")

            body_text, body_html, attachments = _parse_gmail_payload_body(payload)

            payload_dict = {
                "message_id": msg_rfc_id,
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "in_reply_to": in_reply_to,
                "references": references,
                "thread_id": thread_id,
                "attachments": attachments,
            }

            res = process_inbound_email_payload(payload_dict, raw_headers=headers_dict, mailbox=target_email)
            if res.get("status") == "duplicate":
                duplicate_count += 1
            elif res.get("status") == "processed":
                synced_count += 1
            else:
                error_count += 1

        except Exception as item_err:
            logger.error(f"Error syncing Gmail message ID {msg_id}: {item_err}")
            error_count += 1

    # Update sync timestamp and history ID
    credential.history_id = latest_history_id
    credential.last_sync_at = timezone.now()
    credential.save(update_fields=["history_id", "last_sync_at", "updated_at"])

    logger.info(
        f"Gmail sync completed for {mask_email_for_logging(target_email)}: "
        f"{synced_count} synced, {duplicate_count} duplicates skipped, {error_count} errors."
    )
    return {
        "status": "success",
        "synced": synced_count,
        "duplicates": duplicate_count,
        "errors": error_count,
        "history_id": latest_history_id,
    }


def setup_gmail_watch(topic_name: Optional[str] = None, mailbox: Optional[str] = None) -> Dict[str, Any]:
    """
    Configure Gmail watch on the selected mailbox to push notifications to Google Cloud Pub/Sub.
    """
    effective_topic = (topic_name or getattr(settings, "GOOGLE_PUBSUB_TOPIC", "")).strip()
    if not effective_topic:
        raise GmailServiceError("Google Cloud Pub/Sub topic name is not configured (GOOGLE_PUBSUB_TOPIC).")

    creds, credential = get_gmail_credentials(mailbox=mailbox)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    try:
        watch_resp = service.users().watch(
            userId="me",
            body={
                "topicName": effective_topic,
                "labelIds": ["INBOX"],
            },
        ).execute()

        new_history_id = str(watch_resp.get("historyId", ""))
        if new_history_id:
            credential.history_id = new_history_id
            credential.save(update_fields=["history_id", "updated_at"])

        logger.info(f"Gmail watch configured for topic '{effective_topic}' [History ID: {new_history_id}]")
        return watch_resp
    except Exception as exc:
        clean_err = str(exc)[:250]
        logger.error(f"Failed to setup Gmail watch: {clean_err}")
        raise GmailServiceError(f"Gmail watch configuration failed: {clean_err}") from exc
