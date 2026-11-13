"""
Automated Test Suite for Gmail API (OAuth 2.0) Integration.

Verifies:
1. OAuth 2.0 Web Server authorization flow & minimal scope enforcement.
2. Refresh token Fernet encryption at rest in PostgreSQL.
3. Credentials building, auto-refresh, and revoked authorization ('invalid_grant') handling.
4. Outgoing email delivery via Gmail API with EmailLog persistence and sanitized error tracking.
5. Idempotent delivery (preventing duplicate sends on retries).
6. Post-transaction commit notification triggers for public bookings and appointment status updates.
7. Inbound email synchronization persisting into PostgreSQL via InboundEmail/EmailLog.
8. Google Cloud Pub/Sub webhook endpoint processing.
9. Admin settings display (shared mailbox, connection status, no manual send/receive buttons).
"""
import base64
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from googleapiclient.errors import HttpError

from core.models import (
    EmailAccount,
    Hospital,
    ClinicSettings,
    ClinicNotificationRecipient,
    PublicAppointmentRequest,
    Appointment,
    EmailLog,
    InboundEmail,
    GmailOAuthCredential,
)
from core.gmail_service import (
    GMAIL_SEND_SCOPE,
    GMAIL_READONLY_SCOPE,
    SHARED_GMAIL_MAILBOX,
    get_authorization_url,
    get_configured_mailboxes,
    get_mailboxes_for_user,
    user_can_manage_mailbox,
    exchange_code_for_tokens,
    get_gmail_credentials,
    build_gmail_client,
    send_gmail_message,
    sync_gmail_messages,
    setup_gmail_watch,
    dispatch_booking_created_notifications_post_commit,
    dispatch_appointment_created_notifications_post_commit,
    dispatch_appointment_status_notifications_post_commit,
    GmailAuthError,
    GmailConfigError,
)
from core.email_service import EmailContext, resolve_email_account
from tests.test_helpers import BaseHospitalTestCase


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="mock-client-id.apps.googleusercontent.com",
    GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret-12345",
    GOOGLE_OAUTH_REDIRECT_URI="http://testserver/admin-settings/gmail/callback/",
    GMAIL_SHARED_MAILBOX="physio.rehab.guj@gmail.com",
    GMAIL_INBOUND_MAILBOXES="techcraft1215@gmail.com,physio.rehab.guj@gmail.com",
    GOOGLE_PUBSUB_TOPIC="projects/mock-gcp/topics/gmail-notifications",
    GOOGLE_PUBSUB_VERIFICATION_TOKEN="secure-webhook-token-xyz",
    FIELD_ENCRYPTION_KEY="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class GmailApiIntegrationTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        mail.outbox.clear()
        EmailLog.objects.all().delete()
        InboundEmail.objects.all().delete()
        GmailOAuthCredential.objects.all().delete()

        self.hospital = self.create_hospital(
            name="PhysioRehab Clinic",
            email="physio.rehab.guj@gmail.com",
            slug="physiorehab-clinic",
        )
        self.clinic_settings, _ = ClinicSettings.objects.get_or_create(
            hospital=self.hospital,
            defaults={
                "clinic_name": "PhysioRehab Clinic",
                "phone": "+91 94095 10501",
                "email": "physio.rehab.guj@gmail.com",
                "primary_doctor_email": "physio.rehab.guj@gmail.com",
                "appointment_notification_enabled": True,
            },
        )
        self.admin_user = self.create_clinic_admin(
            hospital=self.hospital,
            username="clinic_admin_gmail",
            email="admin@physiorehab.com",
        )

    def test_oauth_flow_authorization_url_and_minimal_scopes(self):
        """Web server OAuth flow generates correct URL with minimal scopes (send, readonly)."""
        request = MagicMock()
        request.build_absolute_uri.return_value = "http://testserver/admin-settings/gmail/callback/"
        request.session = {}

        auth_url, state = get_authorization_url(request)
        self.assertTrue(auth_url.startswith("https://accounts.google.com/o/oauth2"))
        self.assertIn("client_id=mock-client-id.apps.googleusercontent.com", auth_url)
        self.assertIn("access_type=offline", auth_url)
        self.assertIn("prompt=consent", auth_url)
        self.assertTrue(len(state) >= 16)

        # Scopes must be minimal: gmail.send and gmail.readonly
        self.assertIn("gmail.send", auth_url)
        self.assertIn("gmail.readonly", auth_url)
        # Must NOT request full gmail access or compose
        self.assertNotIn("https://mail.google.com/", auth_url)

        platform_url, _ = get_authorization_url(request, mailbox="techcraft1215@gmail.com")
        self.assertIn("login_hint=techcraft1215%40gmail.com", platform_url)

    def test_two_configured_inboxes_are_available_for_sync(self):
        self.assertEqual(
            get_configured_mailboxes(),
            ["techcraft1215@gmail.com", "physio.rehab.guj@gmail.com"],
        )

    def test_token_encryption_at_rest_in_postgresql(self):
        """Refresh token must be stored encrypted with Fernet and never stored as plaintext."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_authorized=True,
        )
        raw_refresh_token = "1//04mock_refresh_token_very_secret_xyz"
        raw_access_token = "ya29.mock_access_token_123"

        cred.set_refresh_token(raw_refresh_token)
        cred.set_access_token(raw_access_token)
        cred.save()

        # Reload directly from database
        cred.refresh_from_db()
        self.assertNotEqual(cred.refresh_token_encrypted, raw_refresh_token)
        self.assertNotEqual(cred.access_token_encrypted, raw_access_token)
        self.assertNotIn("secret", cred.refresh_token_encrypted)

        # Decrypt via accessor
        self.assertEqual(cred.get_refresh_token(), raw_refresh_token)
        self.assertEqual(cred.get_access_token(), raw_access_token)

    @patch("core.gmail_service.google_auth_oauthlib.flow.Flow")
    @patch("core.gmail_service.build")
    def test_exchange_code_for_tokens(self, mock_build, mock_flow_cls):
        """Exchanging auth code stores encrypted tokens and marks credential authorized."""
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow

        mock_credentials = MagicMock()
        mock_credentials.token = "ya29.new_access_token"
        mock_credentials.refresh_token = "1//new_refresh_token"
        mock_credentials.expiry = timezone.now() + timedelta(hours=1)
        mock_credentials.scopes = [GMAIL_SEND_SCOPE, GMAIL_READONLY_SCOPE]
        mock_flow.credentials = mock_credentials
        mock_build.return_value.users.return_value.getProfile.return_value.execute.return_value = {
            "emailAddress": "physio.rehab.guj@gmail.com",
            "historyId": "12345",
        }

        request = MagicMock()
        request.build_absolute_uri.return_value = "http://testserver/admin-settings/gmail/callback/"

        cred = exchange_code_for_tokens(request, code="test-auth-code-123")
        self.assertEqual(cred.email_address, "physio.rehab.guj@gmail.com")
        self.assertTrue(cred.is_authorized)
        self.assertTrue(cred.is_active)
        self.assertEqual(cred.get_refresh_token(), "1//new_refresh_token")
        self.assertEqual(cred.get_access_token(), "ya29.new_access_token")

    @patch("core.gmail_service.google_auth_oauthlib.flow.Flow")
    @patch("core.gmail_service.build")
    def test_oauth_rejects_google_account_other_than_selected_mailbox(self, mock_build, mock_flow_cls):
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.credentials = MagicMock(
            token="access-token",
            refresh_token="refresh-token",
            expiry=None,
            scopes=[GMAIL_SEND_SCOPE, GMAIL_READONLY_SCOPE],
        )
        mock_build.return_value.users.return_value.getProfile.return_value.execute.return_value = {
            "emailAddress": "techcraft1215@gmail.com",
            "historyId": "1",
        }
        with self.assertRaises(GmailAuthError):
            exchange_code_for_tokens("test-code", expected_email="physio.rehab.guj@gmail.com")
        self.assertFalse(GmailOAuthCredential.objects.filter(email="techcraft1215@gmail.com").exists())

    def test_revoked_grant_marks_credential_inactive_safely(self):
        """When Google reports invalid_grant, credential is marked inactive and error recorded."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_authorized=True,
        )
        cred.set_refresh_token("1//revoked_token")
        cred.set_access_token("ya29.expired_token")
        cred.token_expiry = timezone.now() - timedelta(minutes=10)
        cred.save()

        with patch("google.auth.transport.requests.Request") as mock_req:
            with patch("google.oauth2.credentials.Credentials.refresh") as mock_refresh:
                from google.auth.exceptions import RefreshError
                mock_refresh.side_effect = RefreshError("invalid_grant: Token has been expired or revoked.")

                with self.assertRaises(GmailAuthError):
                    get_gmail_credentials("physio.rehab.guj@gmail.com")

        cred.refresh_from_db()
        self.assertFalse(cred.is_active)
        self.assertIn("expired or revoked", cred.last_error)

    @patch("core.gmail_service.build")
    def test_send_gmail_message_success_and_email_log(self, mock_build):
        """Sending via Gmail API creates an EmailLog record with message_id and provider=gmail_api."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_authorized=True,
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        cred.set_refresh_token("1//valid_token")
        cred.set_access_token("ya29.valid_token")
        cred.save()

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_messages = mock_service.users.return_value.messages.return_value
        mock_messages.send.return_value.execute.return_value = {
            "id": "gmail_msg_12345",
            "threadId": "thread_abc",
        }

        res = send_gmail_message(
            to_email="patient@example.com",
            subject="Your Appointment Confirmation",
            body_text="Your appointment is confirmed.",
            idempotency_key="test_booking_123_created",
            hospital=self.hospital,
        )

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("message_id"), "gmail_msg_12345")
        self.assertFalse(res.get("duplicate"))

        # Verify EmailLog created
        log = EmailLog.objects.filter(recipient_email="patient@example.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.recipient_email, "patient@example.com")
        self.assertEqual(log.message_id, "test_booking_123_created")

    @patch("core.gmail_service.build")
    def test_send_gmail_message_idempotent_duplicate_suppression(self, mock_build):
        """Repeated sends with same idempotency key are skipped without calling Gmail API again."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_authorized=True,
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        cred.set_refresh_token("1//valid_token")
        cred.set_access_token("ya29.valid_token")
        cred.save()

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_messages = mock_service.users.return_value.messages.return_value
        mock_messages.send.return_value.execute.return_value = {"id": "gmail_msg_first"}

        # First send
        res1 = send_gmail_message(
            to_email="patient@example.com",
            subject="Booking Confirmation",
            body_text="Hello",
            idempotency_key="booking_dup_key",
            hospital=self.hospital,
        )
        self.assertTrue(res1.get("success"))
        self.assertFalse(res1.get("duplicate"))
        self.assertEqual(mock_messages.send.call_count, 1)

        # Second send with same idempotency key
        res2 = send_gmail_message(
            to_email="patient@example.com",
            subject="Booking Confirmation",
            body_text="Hello",
            idempotency_key="booking_dup_key",
            hospital=self.hospital,
        )
        self.assertTrue(res2.get("success"))
        self.assertTrue(res2.get("duplicate"))
        # Gmail API must NOT have been called a second time
        self.assertEqual(mock_messages.send.call_count, 1)

    @patch("core.gmail_service.send_gmail_message")
    def test_post_commit_booking_created_dispatches_patient_and_clinic(self, mock_send):
        """Public booking dispatch notifies customer and physio.rehab.guj@gmail.com."""
        mock_send.return_value = {"success": True, "message_id": "gmail_test_id"}

        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
        )
        cred.set_refresh_token("1//mock_valid_refresh_token")
        cred.save()
        EmailAccount.objects.create(
            name="Clinic Gmail API Sender",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            provider="gmail_api",
            host="smtp.gmail.com",
            port=587,
            username="physio.rehab.guj@gmail.com",
            from_email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_default=True,
        )

        req_obj = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            patient_name="Rahul Sharma",
            email="rahul.sharma@example.com",
            phone="+91 98765 43210",
            service_or_reason="Physiotherapy Initial Assessment",
            preferred_date=timezone.now().date() + timedelta(days=2),
            preferred_time="10:00 AM",
            status="pending",
        )

        dispatch_booking_created_notifications_post_commit(req_obj.id)

        # Expect 2 calls: one to patient rahul.sharma@example.com, one to clinic physio.rehab.guj@gmail.com
        self.assertEqual(mock_send.call_count, 2)
        called_recipients = [call.kwargs.get("to_email") for call in mock_send.call_args_list]
        self.assertIn("rahul.sharma@example.com", called_recipients)
        self.assertIn("physio.rehab.guj@gmail.com", called_recipients)

    @patch("core.gmail_service.send_gmail_message")
    def test_post_commit_appointment_status_dispatches_update(self, mock_send):
        """Appointment status change dispatches update email to patient."""
        mock_send.return_value = {"success": True, "message_id": "gmail_status_id"}

        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
        )
        cred.set_refresh_token("1//mock_valid_refresh_token")
        cred.save()
        EmailAccount.objects.create(
            name="Clinic Gmail API Sender",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            provider="gmail_api",
            host="smtp.gmail.com",
            port=587,
            username="physio.rehab.guj@gmail.com",
            from_email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_default=True,
        )

        appt = Appointment.objects.create(
            hospital=self.hospital,
            name="Priya Patel",
            email="priya.patel@example.com",
            phone="+91 98765 11111",
            service="Physiotherapy",
            date=timezone.now().date() + timedelta(days=3),
            time="11:00 AM",
            status="confirmed",
        )

        dispatch_appointment_status_notifications_post_commit(appt.id, "confirmed")
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.kwargs.get("to_email"), "priya.patel@example.com")
        self.assertIn("Confirmed", mock_send.call_args.kwargs.get("subject"))

    @patch("core.gmail_service.build")
    def test_inbound_gmail_sync_persists_inbound_email(self, mock_build):
        """sync_gmail_messages fetches incoming email and creates InboundEmail and EmailLog."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            is_active=True,
            is_authorized=True,
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        cred.set_refresh_token("1//valid_token")
        cred.set_access_token("ya29.valid_token")
        cred.save()

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        users = mock_service.users.return_value

        # Mock list response
        users.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "inbound_msg_001", "threadId": "t001"}],
        }

        # Mock get message response
        encoded_body = base64.urlsafe_b64encode(b"I need to reschedule my session.").decode("utf-8")
        users.messages.return_value.get.return_value.execute.return_value = {
            "id": "inbound_msg_001",
            "threadId": "t001",
            "historyId": "98765",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender <sender@example.com>"},
                    {"name": "To", "value": "physio.rehab.guj@gmail.com"},
                    {"name": "Subject", "value": "Reschedule Inquiry"},
                    {"name": "Message-ID", "value": "<inbound_msg_001@example.com>"},
                    {"name": "Date", "value": "Mon, 02 Nov 2026 10:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": encoded_body},
                "parts": [],
            },
        }

        result = sync_gmail_messages(mailbox="physio.rehab.guj@gmail.com")
        self.assertEqual(result.get("synced"), 1)
        self.assertEqual(result.get("history_id"), "98765")

        # Verify InboundEmail record created in PostgreSQL
        inbound = InboundEmail.objects.filter(message_id="inbound_msg_001@example.com").first()
        self.assertIsNotNone(inbound)
        self.assertEqual(inbound.sender, "sender@example.com")
        self.assertEqual(inbound.subject, "Reschedule Inquiry")
        self.assertIn("reschedule", inbound.body_text)

    def test_pubsub_webhook_verification_and_sync(self):
        """Google Pub/Sub webhook endpoint validates token, decodes payload, and returns HTTP 200."""
        pubsub_data = json.dumps({
            "emailAddress": "physio.rehab.guj@gmail.com",
            "historyId": 123456
        })
        b64_data = base64.b64encode(pubsub_data.encode("utf-8")).decode("utf-8")

        payload = {
            "message": {
                "data": b64_data,
                "messageId": "pubsub_msg_999",
                "publishTime": "2026-11-02T10:00:00Z",
            },
            "subscription": "projects/mock-gcp/subscriptions/gmail-sub",
        }

        # 1. Invalid verification token -> 403 Forbidden
        bad_resp = self.client.post(
            reverse("api_gmail_pubsub_webhook") + "?token=invalid-token",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(bad_resp.status_code, 403)

        with override_settings(GOOGLE_PUBSUB_VERIFICATION_TOKEN=""):
            unconfigured_resp = self.client.post(
                reverse("api_gmail_pubsub_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
            )
        self.assertEqual(unconfigured_resp.status_code, 403)

        # 2. Valid token -> 200 OK and triggers sync
        with patch("core.gmail_service.sync_gmail_messages") as mock_sync:
            mock_sync.return_value = {"synced": 0, "duplicates": 0, "errors": 0}
            valid_resp = self.client.post(
                reverse("api_gmail_pubsub_webhook") + "?token=secure-webhook-token-xyz",
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(valid_resp.status_code, 200)
            mock_sync.assert_called_once()

    def test_admin_settings_displays_configured_gmail_inbox_controls(self):
        """Clinic admin sees its inbox connection controls without platform mailbox access."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin_settings"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Clinic admins can connect and manually sync the clinic inbox only.
        self.assertIn("Gmail inbox connections", content)
        self.assertIn("physio.rehab.guj@gmail.com", content)
        self.assertIn("Connect Google inbox", content)
        self.assertNotIn("techcraft1215@gmail.com", content)
        self.assertNotIn("Sync now", content)  # Sync appears after mailbox authorization.

    def test_platform_admin_sees_only_the_platform_inbox(self):
        self.client.force_login(self.create_super_admin(
            username="platform_admin_mail",
            email="techcraft1215@gmail.com",
        ))
        response = self.client.get(reverse("admin_settings"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        inbox_panel = content.split("Gmail inbox connections", 1)[1].split(
            "<!-- Gmail inbox controls are rendered once", 1
        )[0]
        self.assertIn("techcraft1215@gmail.com", inbox_panel)
        self.assertNotIn("physio.rehab.guj@gmail.com", inbox_panel)

    def test_platform_admin_does_not_see_clinic_inbound_message_content(self):
        InboundEmail.objects.create(
            message_id="private-clinic-message@example.com",
            sender="patient@example.com",
            recipient="physio.rehab.guj@gmail.com",
            subject="Private clinic appointment details",
            body_text="Private patient information",
        )
        self.client.force_login(self.create_super_admin(
            username="platform_admin_inbox_privacy",
            email="techcraft1215@gmail.com",
        ))

        response = self.client.get(reverse("admin_email_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Private clinic appointment details")
        self.assertNotContains(response, "Private patient information")

    def test_admins_cannot_manage_the_other_role_mailbox(self):
        self.client.force_login(self.admin_user)
        clinic_response = self.client.get(
            reverse("admin_gmail_oauth_start"),
            {"mailbox": "techcraft1215@gmail.com"},
        )
        self.assertEqual(clinic_response.status_code, 302)
        self.assertNotIn("accounts.google.com", clinic_response.url)

        platform_user = self.create_super_admin(
            username="platform_mail_owner",
            email="techcraft1215@gmail.com",
        )
        self.client.force_login(platform_user)
        platform_response = self.client.get(
            reverse("admin_gmail_oauth_start"),
            {"mailbox": "physio.rehab.guj@gmail.com"},
        )
        self.assertEqual(platform_response.status_code, 302)
        self.assertNotIn("accounts.google.com", platform_response.url)

    def test_mailbox_access_is_limited_to_admin_roles(self):
        platform_admin = self.create_super_admin(
            username="mailbox_platform_owner",
            email="techcraft1215@gmail.com",
        )
        staff = self.create_staff(
            self.hospital,
            username="mailbox_staff_member",
            email="mailbox-staff@example.com",
        )
        patient = self.create_patient(
            self.hospital,
            username="mailbox_patient",
            email="mailbox-patient@example.com",
        )

        self.assertEqual(
            get_mailboxes_for_user(platform_admin),
            ["techcraft1215@gmail.com"],
        )
        self.assertEqual(
            get_mailboxes_for_user(self.admin_user),
            ["physio.rehab.guj@gmail.com"],
        )
        self.assertEqual(get_mailboxes_for_user(staff), [])
        self.assertEqual(get_mailboxes_for_user(patient), [])
        self.assertFalse(user_can_manage_mailbox(staff, "physio.rehab.guj@gmail.com"))
        self.assertFalse(user_can_manage_mailbox(patient, "physio.rehab.guj@gmail.com"))

    def test_role_mailbox_setup_is_idempotent_and_preserves_smtp_secret(self):
        account = EmailAccount.objects.create(
            name="Old platform mailer",
            account_type="PLATFORM",
            scope_type="platform",
            provider="gmail",
            host="old.smtp.example.com",
            port=25,
            username="old@example.com",
            from_email="old@example.com",
            encrypted_password="",
            is_default=True,
        )
        account.set_password("existing-secret")
        account.save()

        call_command("configure_role_mailboxes", stdout=MagicMock())
        call_command("configure_role_mailboxes", stdout=MagicMock())

        account.refresh_from_db()
        self.assertEqual(account.host, "smtp.gmail.com")
        self.assertEqual(account.port, 587)
        self.assertTrue(account.use_tls)
        self.assertEqual(account.username, "techcraft1215@gmail.com")
        self.assertEqual(account.get_password(), "existing-secret")
        self.assertTrue(EmailAccount.objects.filter(
            scope_type="hospital",
            hospital=self.hospital,
            from_email="physio.rehab.guj@gmail.com",
            is_default=True,
        ).exists())

    @override_settings(EMAIL_BACKEND="core.email_backend.ResendEmailBackend")
    @patch("django.core.mail.get_connection")
    def test_gmail_account_uses_smtp_connection_when_global_backend_is_resend(self, mock_get_connection):
        account = EmailAccount(
            provider="gmail",
            host="smtp.gmail.com",
            port=587,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            encrypted_password="",
            use_tls=True,
        )
        account.get_connection()
        self.assertEqual(
            mock_get_connection.call_args.kwargs["backend"],
            "django.core.mail.backends.smtp.EmailBackend",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    @patch("django.core.mail.get_connection")
    def test_gmail_account_uses_smtp_connection_when_global_backend_is_console(self, mock_get_connection):
        account = EmailAccount(
            provider="gmail",
            host="smtp.gmail.com",
            port=587,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            encrypted_password="",
            use_tls=True,
        )
        account.get_connection()
        self.assertEqual(
            mock_get_connection.call_args.kwargs["backend"],
            "django.core.mail.backends.smtp.EmailBackend",
        )

    @override_settings(
        PLATFORM_SMTP_PASSWORD="platform-app-password",
        CLINIC_SMTP_PASSWORD="clinic-app-password",
        PLATFORM_SMTP_USER="techcraft1215@gmail.com",
        CLINIC_SMTP_USER="physio.rehab.guj@gmail.com",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_role_fallbacks_keep_platform_and_clinic_smtp_credentials_separate(self):
        platform_account = resolve_email_account(context=EmailContext.PLATFORM)
        clinic_account = resolve_email_account(
            hospital=self.hospital,
            context=EmailContext.CLINIC,
        )
        self.assertEqual(platform_account.username, "techcraft1215@gmail.com")
        self.assertEqual(platform_account.get_password(), "platform-app-password")
        self.assertEqual(clinic_account.username, "physio.rehab.guj@gmail.com")
        self.assertEqual(clinic_account.get_password(), "clinic-app-password")
        self.assertEqual((platform_account.host, platform_account.port), ("smtp.gmail.com", 587))
        self.assertEqual((clinic_account.host, clinic_account.port), ("smtp.gmail.com", 587))

    @override_settings(
        PLATFORM_SMTP_PASSWORD="platform-app-password",
        CLINIC_SMTP_PASSWORD="clinic-app-password",
        PLATFORM_SMTP_USER="techcraft1215@gmail.com",
        CLINIC_SMTP_USER="physio.rehab.guj@gmail.com",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_environment_passwords_override_provisioned_secrets_without_storing_them(self):
        platform_account = EmailAccount.objects.create(
            name="Platform Gmail",
            account_type="PLATFORM",
            scope_type="platform",
            provider="gmail",
            host="smtp.gmail.com",
            port=587,
            username="techcraft1215@gmail.com",
            from_email="techcraft1215@gmail.com",
            encrypted_password="",
            is_default=True,
        )
        clinic_account = EmailAccount.objects.create(
            name="Clinic Gmail",
            account_type="CLINIC",
            scope_type="hospital",
            hospital=self.hospital,
            provider="gmail",
            host="smtp.gmail.com",
            port=587,
            username="physio.rehab.guj@gmail.com",
            from_email="physio.rehab.guj@gmail.com",
            encrypted_password="",
            is_default=True,
        )
        platform_account.set_password("old-platform-password")
        platform_account.save()
        clinic_account.set_password("old-clinic-password")
        clinic_account.save()

        resolved_platform = resolve_email_account(context=EmailContext.PLATFORM)
        resolved_clinic = resolve_email_account(
            hospital=self.hospital,
            context=EmailContext.CLINIC,
        )

        self.assertEqual(resolved_platform.get_password(), "platform-app-password")
        self.assertEqual(resolved_clinic.get_password(), "clinic-app-password")
        platform_account.refresh_from_db()
        clinic_account.refresh_from_db()
        self.assertEqual(platform_account.get_password(), "old-platform-password")
        self.assertEqual(clinic_account.get_password(), "old-clinic-password")

    @patch("core.gmail_service.build")
    def test_inbound_customer_reply_links_to_public_appointment_request_and_dashboard(self, mock_build):
        """Customer email reply is synced, linked to booking request, creates notification, and appears on dashboards."""
        cred = GmailOAuthCredential.objects.create(
            email="physio.rehab.guj@gmail.com",
            hospital=self.hospital,
            scopes=[GMAIL_SEND_SCOPE, GMAIL_READONLY_SCOPE],
            is_active=True,
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        cred.set_refresh_token("1//mock_refresh_token")
        cred.set_access_token("ya29.mock_access_token")
        cred.save()

        # 1. Create a PublicAppointmentRequest
        req_obj = PublicAppointmentRequest.objects.create(
            hospital=self.hospital,
            reference_id="PAR-20261103-CUST",
            patient_name="Rahul Verma",
            email="rahul.verma@example.com",
            phone="+91 98765 43210",
            preferred_date=timezone.now().date(),
            preferred_time="10:00 AM",
            status="pending",
        )

        # 2. Mock incoming reply from the customer
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        users = mock_service.users.return_value
        users.history.return_value.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b"History expired"
        )
        users.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "reply_msg_101"}]
        }
        encoded_body = base64.urlsafe_b64encode("Can we reschedule to 11 AM instead please?".encode("utf-8")).decode("utf-8")
        users.messages.return_value.get.return_value.execute.return_value = {
            "id": "reply_msg_101",
            "threadId": "thread_cust_101",
            "historyId": "99999",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Rahul Verma <rahul.verma@example.com>"},
                    {"name": "To", "value": "physio.rehab.guj@gmail.com"},
                    {"name": "Subject", "value": "Re: [Dr. Dhvani Patalia Physio Rehab] Appointment Request Received [Ref: PAR-20261103-CUST]"},
                    {"name": "Message-ID", "value": "<reply_msg_101@mail.gmail.com>"},
                    {"name": "Date", "value": "Tue, 03 Nov 2026 10:30:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": encoded_body},
                "parts": [],
            },
        }

        # 3. Synchronize incoming messages
        result = sync_gmail_messages(mailbox="physio.rehab.guj@gmail.com")
        self.assertEqual(result.get("synced"), 1)

        # 4. Verify InboundEmail in PostgreSQL
        inbound = InboundEmail.objects.filter(message_id="reply_msg_101@mail.gmail.com").first()
        self.assertIsNotNone(inbound)
        self.assertEqual(inbound.sender, "rahul.verma@example.com")
        self.assertIn("11 AM", inbound.body_text)

        # 5. Verify PublicAppointmentRequest.latest_customer_reply property
        req_obj.refresh_from_db()
        self.assertIsNotNone(req_obj.latest_customer_reply)
        self.assertEqual(req_obj.latest_customer_reply.id, inbound.id)

        # 6. Verify dashboard displays customer reply in /admin-appointments/
        self.client.force_login(self.admin_user)
        resp_appt = self.client.get(reverse("admin_appointments"))
        self.assertEqual(resp_appt.status_code, 200)
        self.assertIn("Customer Reply:", resp_appt.content.decode("utf-8"))
        self.assertIn("11 AM", resp_appt.content.decode("utf-8"))

        # 7. Verify dashboard displays inbound table in /admin-email-settings/
        resp_email = self.client.get(reverse("admin_email_settings"))
        self.assertEqual(resp_email.status_code, 200)
        email_content = resp_email.content.decode("utf-8")
        self.assertIn("Synchronized Incoming Messages &amp; Customer Replies", email_content)
        self.assertIn("rahul.verma@example.com", email_content)
        self.assertIn("PAR-20261103-CUST", email_content)
