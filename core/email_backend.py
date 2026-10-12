"""
Production Transactional Email Backend using Resend HTTPS REST API.
Operates over HTTPS (Port 443), bypassing outbound SMTP port blocks
(ports 25, 465, 587) enforced by cloud providers such as Render Free.
"""
import base64
import email.message
import json
import logging
import os
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    """
    Transactional email backend dispatching messages via Resend's REST API over HTTPS.
    Works seamlessly in production environments where outbound SMTP ports are restricted.
    """

    def __init__(self, api_key=None, fail_silently=False, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (
            api_key
            or getattr(settings, "RESEND_API_KEY", None)
            or os.getenv("RESEND_API_KEY", "")
        ).strip()
        self.timeout = timeout or getattr(settings, "EMAIL_TIMEOUT", 15)

    def open(self):
        """No persistent connection needed for stateless HTTPS REST API."""
        return True

    def close(self):
        """No persistent connection to terminate."""
        pass

    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage instances via Resend API.
        Returns the number of successfully delivered email messages.
        """
        if not email_messages:
            return 0

        if not self.api_key:
            err_msg = "Resend API key is not configured. Set RESEND_API_KEY in environment variables."
            logger.error(err_msg)
            if not self.fail_silently:
                raise ImproperlyConfigured(err_msg)
            return 0

        sent_count = 0
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "PhysioRehab-EmailClient/1.0",
        }

        for message in email_messages:
            try:
                payload = self._build_payload(message)
                response = requests.post(
                    RESEND_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code in (200, 201):
                    res_data = response.json() if response.content else {}
                    msg_id = res_data.get("id", "resend_ok")
                    logger.info(
                        f"Email sent successfully via Resend API to {self._mask_recipients(message.to)} (ID: {msg_id})"
                    )
                    sent_count += 1
                else:
                    error_detail = response.text[:200]
                    logger.error(
                        f"Resend API rejected email to {self._mask_recipients(message.to)}: "
                        f"HTTP {response.status_code} - {error_detail}"
                    )
                    if not self.fail_silently:
                        response.raise_for_status()
            except Exception as exc:
                logger.error(
                    f"Resend delivery failed for {self._mask_recipients(message.to)}: {exc.__class__.__name__} - {exc}"
                )
                if not self.fail_silently:
                    raise

        return sent_count

    def _build_payload(self, message):
        """Serialize a Django EmailMessage or EmailMultiAlternatives to Resend JSON payload."""
        from_email = (
            message.from_email
            or getattr(settings, "DEFAULT_FROM_EMAIL", "")
            or "PhysioRehab Clinic <onboarding@resend.dev>"
        )

        recipients = list(message.to) if message.to else []
        if not recipients:
            raise ValueError("No recipient specified in email message.")

        payload = {
            "from": from_email,
            "to": recipients,
            "subject": message.subject or "(No Subject)",
        }

        # Body (plain text)
        if message.body:
            payload["text"] = message.body

        # HTML body (if EmailMultiAlternatives or HTML message)
        html_content = None
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in getattr(message, "alternatives", []):
                if mimetype == "text/html":
                    html_content = content
                    break

        if not html_content and hasattr(message, "content_subtype") and message.content_subtype == "html":
            html_content = message.body

        if html_content:
            payload["html"] = html_content
        elif "text" not in payload:
            payload["text"] = ""

        # CC / BCC
        if getattr(message, "cc", None):
            payload["cc"] = list(message.cc)
        if getattr(message, "bcc", None):
            payload["bcc"] = list(message.bcc)

        # Reply-To
        if getattr(message, "reply_to", None):
            payload["reply_to"] = list(message.reply_to)

        # Custom Headers
        custom_headers = {}
        for h_key, h_val in getattr(message, "extra_headers", {}).items():
            if h_key.lower() not in ("from", "to", "subject", "content-type", "content-transfer-encoding"):
                custom_headers[h_key] = str(h_val)
        if custom_headers:
            payload["headers"] = custom_headers

        # Attachments
        if getattr(message, "attachments", None):
            resend_attachments = []
            for attachment in message.attachments:
                if isinstance(attachment, tuple):
                    # Tuple form: (filename, content, mimetype)
                    att_name = attachment[0]
                    att_content = attachment[1]
                    if isinstance(att_content, str):
                        b64_content = base64.b64encode(att_content.encode("utf-8")).decode("ascii")
                    elif isinstance(att_content, (bytes, bytearray)):
                        b64_content = base64.b64encode(att_content).decode("ascii")
                    else:
                        b64_content = base64.b64encode(str(att_content).encode("utf-8")).decode("ascii")
                    resend_attachments.append({"filename": att_name, "content": b64_content})
                elif isinstance(attachment, email.message.Message):
                    att_name = attachment.get_filename() or "attachment.dat"
                    payload_data = attachment.get_payload(decode=True)
                    if payload_data:
                        b64_content = base64.b64encode(payload_data).decode("ascii")
                        resend_attachments.append({"filename": att_name, "content": b64_content})

            if resend_attachments:
                payload["attachments"] = resend_attachments

        return payload

    @staticmethod
    def _mask_recipients(recipients):
        """Safely mask recipient emails for production logs."""
        if not recipients:
            return "[]"
        masked = []
        for r in recipients:
            r_str = str(r)
            if "@" in r_str:
                local, domain = r_str.split("@", 1)
                m_local = local[:2] + "***" if len(local) > 2 else "***"
                masked.append(f"{m_local}@{domain}")
            else:
                masked.append("***")
        return ", ".join(masked)
