"""
Automated Test Suite for Platform Super Admin, Clinic Admin, Multi-Email Configuration,
and Appointment Notifications.

Verifies:
1. Platform Super Admin identity separation & protection of platform settings.
2. Clinic Admin settings isolation & notification preferences.
3. Multi-email notification recipient management (add, validate, deduplicate, toggle, delete, cross-clinic isolation).
4. Appointment booking notification workflow (pending state, dispatch to all active clinic recipients, Super Admin exclusion).
5. Safe delivery failure (appointment persistence guaranteed when email dispatch fails).
"""
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.test import override_settings

from core.models import (
    Hospital,
    ClinicSettings,
    ClinicNotificationRecipient,
    PlatformSettings,
    PublicAppointmentRequest,
    Appointment,
)
from tests.test_helpers import BaseHospitalTestCase


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PLATFORM_SUPERADMIN_EMAIL="techcraft1215@gmail.com",
    CLINIC_NOTIFICATION_EMAIL="physio.rehab.guj@gmail.com",
)
class MultiEmailNotificationArchitectureTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        mail.outbox.clear()

        # Clinic A: Dr. Dhvani Patalia Physio Rehab
        self.hospital_a = self.create_hospital(
            name="Dr. Dhvani Patalia Physio Rehab",
            email="physio.rehab.guj@gmail.com",
            slug="dr-dhvani-patalia-physio-rehab",
        )
        self.clinic_settings_a, _ = ClinicSettings.objects.get_or_create(
            hospital=self.hospital_a,
            defaults={
                "clinic_name": "Dr. Dhvani Patalia Physio Rehab",
                "phone": "+91 94095 10501",
                "email": "physio.rehab.guj@gmail.com",
                "primary_doctor_email": "physio.rehab.guj@gmail.com",
                "appointment_notification_enabled": True,
                "lead_notification_enabled": True,
            },
        )
        self.admin_a = self.create_clinic_admin(
            hospital=self.hospital_a,
            username="clinic_admin_a",
            email="admin.a@physiorehab.com",
        )

        # Clinic B: Second tenant clinic for cross-tenant isolation testing
        self.hospital_b = self.create_hospital(
            name="Apex Wellness Clinic",
            email="contact@apexwellness.com",
            slug="apex-wellness-clinic",
        )
        self.clinic_settings_b, _ = ClinicSettings.objects.get_or_create(
            hospital=self.hospital_b,
            defaults={
                "clinic_name": "Apex Wellness Clinic",
                "phone": "+91 98765 00000",
                "email": "contact@apexwellness.com",
                "primary_doctor_email": "doctor@apexwellness.com",
                "appointment_notification_enabled": True,
                "lead_notification_enabled": True,
            },
        )
        self.admin_b = self.create_clinic_admin(
            hospital=self.hospital_b,
            username="clinic_admin_b",
            email="admin.b@apexwellness.com",
        )

        # Super Admin (Platform Owner)
        self.superadmin = self.create_super_admin(
            username="techcraft1215",
            email="techcraft1215@gmail.com",
        )

        # URLs
        self.admin_settings_url = reverse("admin_settings")
        self.add_recipient_url = reverse("admin_add_notification_recipient")
        self.platform_settings_url = reverse("super_admin_platform_settings")
        self.booking_url = reverse("public_book_appointment")

    def _get_future_date(self, days=3):
        target = timezone.now().date() + timedelta(days=days)
        if target.weekday() == 6:  # Skip Sunday
            target += timedelta(days=1)
        return target

    # =========================================================================
    # 1. SUPER ADMIN IDENTITY & PLATFORM SETTINGS SEPARATION
    # =========================================================================

    def test_superadmin_can_access_and_update_platform_settings(self):
        """Platform Super Admin has exclusive access to configure platform settings."""
        self.client.force_login(self.superadmin)
        response = self.client.get(self.platform_settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Settings &amp; Super Admin Identity")

        # Update platform settings
        update_payload = {
            "platform_name": "TechCraft Healthcare Cloud",
            "super_admin_username": "techcraft1215",
            "super_admin_email": "techcraft1215@gmail.com",
            "system_alert_email": "security@techcraft.io",
            "support_email": "support@techcraft.io",
            "enable_registration": "on",
            "maintenance_mode": "",
            "maintenance_message": "Scheduled upgrades tonight.",
        }
        post_resp = self.client.post(self.platform_settings_url, update_payload, follow=True)
        self.assertEqual(post_resp.status_code, 200)

        # Verify DB updated
        ps = PlatformSettings.get_settings()
        self.assertEqual(ps.platform_name, "TechCraft Healthcare Cloud")
        self.assertEqual(ps.system_alert_email, "security@techcraft.io")
        self.assertEqual(ps.super_admin_email, "techcraft1215@gmail.com")

    def test_clinic_admin_cannot_access_or_modify_platform_settings(self):
        """Clinic Admin has zero permission to view or modify platform Super Admin settings."""
        self.client.force_login(self.admin_a)
        response = self.client.get(self.platform_settings_url, follow=True)
        # Must be redirected away with error message
        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertContains(response, "Access restricted to Platform Super Admin")

        # Attempt unauthorized POST
        post_resp = self.client.post(
            self.platform_settings_url,
            {"platform_name": "Hacked Platform Name"},
            follow=True,
        )
        self.assertRedirects(post_resp, reverse("admin_dashboard"))
        # Settings remain unchanged
        ps = PlatformSettings.get_settings()
        self.assertNotEqual(ps.platform_name, "Hacked Platform Name")

    def test_unauthenticated_visitor_blocked_from_platform_settings(self):
        """Anonymous visitor is redirected to login when trying to access platform settings."""
        self.client.logout()
        response = self.client.get(self.platform_settings_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    # =========================================================================
    # 2. CLINIC ADMIN SETTINGS & PREFERENCES
    # =========================================================================

    def test_clinic_admin_can_view_and_update_clinic_settings(self):
        """Clinic Admin can update their clinic's primary doctor email and notification preferences."""
        self.client.force_login(self.admin_a)
        response = self.client.get(self.admin_settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clinic Appointment Notification Recipients")
        self.assertContains(response, "Primary Doctor / Appointment Alert Email")

        # Update primary doctor email and mute appointment notifications
        payload = {
            "clinic_name": "Dr. Dhvani Patalia Physio Rehab",
            "phone": "+91 94095 10501",
            "email": "physio.rehab.guj@gmail.com",
            "primary_doctor_email": "dr.dhvani.direct@gmail.com",
            "address": "Ground Floor, Narayan Cottage, Jamnagar",
            # appointment_notification_enabled left unchecked (muted)
            "lead_notification_enabled": "on",
        }
        post_resp = self.client.post(self.admin_settings_url, payload, follow=True)
        self.assertEqual(post_resp.status_code, 200)

        self.clinic_settings_a.refresh_from_db()
        self.assertEqual(self.clinic_settings_a.primary_doctor_email, "dr.dhvani.direct@gmail.com")
        self.assertFalse(self.clinic_settings_a.appointment_notification_enabled)
        self.assertTrue(self.clinic_settings_a.lead_notification_enabled)

    # =========================================================================
    # 3. MULTIPLE NOTIFICATION RECIPIENTS MANAGEMENT
    # =========================================================================

    def test_add_valid_notification_recipients(self):
        """Clinic Admin can add multiple recipients (Doctor, Admin, Coordinator)."""
        self.client.force_login(self.admin_a)

        # Recipient 1: Doctor
        resp1 = self.client.post(self.add_recipient_url, {
            "name": "Dr. Dhvani Patalia",
            "email": "physio.rehab.guj@gmail.com",
            "recipient_type": "doctor",
            "notify_on_appointment": "on",
            "notify_on_contact_inquiry": "on",
            "is_active": "on",
        }, follow=True)
        self.assertContains(resp1, "added successfully")
        self.assertContains(resp1, "physio.rehab.guj@gmail.com")

        # Recipient 2: Appointment Coordinator
        resp2 = self.client.post(self.add_recipient_url, {
            "name": "Front Desk Coordinator",
            "email": "appointments@physiorehab.com",
            "recipient_type": "coordinator",
            "notify_on_appointment": "on",
            "notify_on_contact_inquiry": "",
            "is_active": "on",
        }, follow=True)
        self.assertEqual(resp2.status_code, 200)

        # Verify DB records
        recipients = self.hospital_a.notification_recipients.all()
        self.assertEqual(recipients.count(), 2)

        # Verify effective recipient emails
        effective = self.hospital_a.get_appointment_recipient_emails()
        self.assertIn("physio.rehab.guj@gmail.com", effective)
        self.assertIn("appointments@physiorehab.com", effective)
        self.assertNotIn("techcraft1215@gmail.com", effective)

    def test_reject_invalid_recipient_email(self):
        """Invalid email addresses are rejected with a clear validation error."""
        self.client.force_login(self.admin_a)
        resp = self.client.post(self.add_recipient_url, {
            "name": "Invalid Staff",
            "email": "not-an-email-address",
            "recipient_type": "general",
            "notify_on_appointment": "on",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "is not a valid email address")
        self.assertEqual(self.hospital_a.notification_recipients.count(), 0)

    def test_prevent_duplicate_recipient_email_in_same_clinic(self):
        """Attempting to add the same email twice to a clinic is safely rejected."""
        self.client.force_login(self.admin_a)
        # Add once
        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Dr. Dhvani",
            email="physio.rehab.guj@gmail.com",
            recipient_type="doctor",
        )
        # Try to add again
        resp = self.client.post(self.add_recipient_url, {
            "name": "Dr. Dhvani Duplicate",
            "email": "physio.rehab.guj@gmail.com",
            "recipient_type": "doctor",
            "notify_on_appointment": "on",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already exists for this clinic")
        self.assertEqual(self.hospital_a.notification_recipients.count(), 1)

    def test_prevent_clinic_admin_from_registering_superadmin_email(self):
        """Clinic Admin cannot configure the Super Admin's private email as a clinic recipient."""
        self.client.force_login(self.admin_a)
        resp = self.client.post(self.add_recipient_url, {
            "name": "Super Admin Spoof",
            "email": "techcraft1215@gmail.com",
            "recipient_type": "admin",
            "notify_on_appointment": "on",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Platform Super Admin email cannot be registered")
        self.assertEqual(self.hospital_a.notification_recipients.count(), 0)

    def test_toggle_and_delete_notification_recipient(self):
        """Clinic Admin can mute/activate and delete recipients."""
        self.client.force_login(self.admin_a)
        r = ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Coordinator",
            email="coord@physiorehab.com",
            recipient_type="coordinator",
            is_active=True,
        )

        # 1. Toggle active -> muted
        toggle_url = reverse("admin_toggle_notification_recipient", args=[r.id])
        t_resp = self.client.post(toggle_url, follow=True)
        self.assertEqual(t_resp.status_code, 200)
        r.refresh_from_db()
        self.assertFalse(r.is_active)
        self.assertContains(t_resp, "is now muted")

        # Muted recipient should not appear in active appointment recipients
        effective = self.hospital_a.get_appointment_recipient_emails()
        self.assertNotIn("coord@physiorehab.com", effective)

        # 2. Delete recipient
        del_url = reverse("admin_delete_notification_recipient", args=[r.id])
        d_resp = self.client.post(del_url, follow=True)
        self.assertEqual(d_resp.status_code, 200)
        self.assertFalse(ClinicNotificationRecipient.objects.filter(id=r.id).exists())

    def test_cross_clinic_recipient_isolation(self):
        """Clinic Admin A cannot modify, toggle, or delete Clinic B's notification recipient."""
        # Recipient belonging to Clinic B
        r_b = ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_b,
            name="Apex Specialist",
            email="specialist@apexwellness.com",
            recipient_type="doctor",
            is_active=True,
        )

        # Clinic Admin A logs in and attempts to delete r_b
        self.client.force_login(self.admin_a)
        del_url = reverse("admin_delete_notification_recipient", args=[r_b.id])
        resp = self.client.post(del_url)
        # Must return 404 because r_b belongs to Hospital B
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ClinicNotificationRecipient.objects.filter(id=r_b.id).exists())

        # Attempt to toggle r_b
        toggle_url = reverse("admin_toggle_notification_recipient", args=[r_b.id])
        t_resp = self.client.post(toggle_url)
        self.assertEqual(t_resp.status_code, 404)
        r_b.refresh_from_db()
        self.assertTrue(r_b.is_active)

    # =========================================================================
    # 4. APPOINTMENT NOTIFICATION DISPATCH TO MULTIPLE RECIPIENTS
    # =========================================================================

    def test_appointment_booking_dispatches_to_all_active_clinic_recipients(self):
        """
        When a visitor requests an appointment, email alerts are dispatched to ALL
        configured active recipients for that clinic, and never to the platform Super Admin.
        """
        # Configure multiple recipients for Hospital A
        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Dr. Dhvani Patalia",
            email="physio.rehab.guj@gmail.com",
            recipient_type="doctor",
            notify_on_appointment=True,
            is_active=True,
        )
        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Clinic Manager",
            email="manager@physiorehab.com",
            recipient_type="admin",
            notify_on_appointment=True,
            is_active=True,
        )
        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Receptionist",
            email="reception@physiorehab.com",
            recipient_type="coordinator",
            notify_on_appointment=True,
            is_active=True,
        )
        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Muted Staff",
            email="muted@physiorehab.com",
            recipient_type="general",
            notify_on_appointment=True,
            is_active=False,  # Muted - should NOT receive
        )

        future_date = self._get_future_date(4)
        payload = {
            "patient_name": "Rohan Patel",
            "email": "rohan.patel@example.com",
            "phone": "9876543210",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "11:00 AM",
            "service_or_reason": "Post-surgery knee rehabilitation",
            "preferred_contact_method": "phone",
            "consent": "on",
            "website": "",
        }

        response = self.client.post(self.booking_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request received, pending clinic confirmation")

        # 1. Verify Appointment Request record created with 'pending' status
        req_obj = PublicAppointmentRequest.objects.filter(email="rohan.patel@example.com").first()
        self.assertIsNotNone(req_obj)
        self.assertEqual(req_obj.status, "pending")
        self.assertEqual(req_obj.email_notification_status, "sent")
        self.assertEqual(req_obj.hospital, self.hospital_a)

        # 2. Verify Emails in outbox
        self.assertGreaterEqual(len(mail.outbox), 2)

        # Collect all recipient addresses across outbox
        all_to_emails = []
        for m in mail.outbox:
            all_to_emails.extend(m.to)

        # Active recipients must have received
        self.assertIn("physio.rehab.guj@gmail.com", all_to_emails)
        self.assertIn("manager@physiorehab.com", all_to_emails)
        self.assertIn("reception@physiorehab.com", all_to_emails)
        self.assertIn("rohan.patel@example.com", all_to_emails)  # Patient acknowledgment

        # Muted staff and Super Admin must NOT receive
        self.assertNotIn("muted@physiorehab.com", all_to_emails)
        self.assertNotIn("techcraft1215@gmail.com", all_to_emails)

    def test_appointment_notifications_respect_clinic_disabled_toggle(self):
        """When a clinic admin disables appointment notifications, team alerts are suppressed."""
        self.clinic_settings_a.appointment_notification_enabled = False
        self.clinic_settings_a.save()

        ClinicNotificationRecipient.objects.create(
            hospital=self.hospital_a,
            name="Dr. Dhvani Patalia",
            email="physio.rehab.guj@gmail.com",
            recipient_type="doctor",
            notify_on_appointment=True,
            is_active=True,
        )

        future_date = self._get_future_date(2)
        payload = {
            "patient_name": "Aarav Shah",
            "email": "aarav.shah@example.com",
            "phone": "9876543211",
            "preferred_date": future_date.strftime("%Y-%m-%d"),
            "preferred_time": "12:00 PM",
            "service_or_reason": "Neck stiffness",
            "preferred_contact_method": "email",
            "consent": "on",
            "website": "",
        }

        response = self.client.post(self.booking_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        req_obj = PublicAppointmentRequest.objects.filter(email="aarav.shah@example.com").first()
        self.assertIsNotNone(req_obj)
        self.assertEqual(req_obj.status, "pending")

        # Clinic team email should NOT be dispatched
        all_to_emails = [addr for m in mail.outbox for addr in m.to]
        self.assertNotIn("physio.rehab.guj@gmail.com", all_to_emails)

    # =========================================================================
    # 5. SAFE DELIVERY FAILURE & APPOINTMENT PERSISTENCE
    # =========================================================================

    def test_email_failure_does_not_lose_appointment_booking(self):
        """
        If the email backend encounters an exception (e.g. SMTP timeout), the
        appointment booking request is safely saved in the DB and marked failed.
        No data is lost and the visitor still receives a reassuring pending notice.
        """
        with patch("core.views.send_public_appointment_request_notification", side_effect=Exception("SMTP Connection Refused: port 587 unreachable")):
            future_date = self._get_future_date(5)
            payload = {
                "patient_name": "Pooja Mehta",
                "email": "pooja.mehta@example.com",
                "phone": "9876543212",
                "preferred_date": future_date.strftime("%Y-%m-%d"),
                "preferred_time": "04:30 PM",
                "service_or_reason": "Chronic shoulder pain",
                "preferred_contact_method": "phone",
                "consent": "on",
                "website": "",
            }

            response = self.client.post(self.booking_url, payload, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Request received, pending clinic confirmation")

            # Verify appointment record is preserved in database
            req_obj = PublicAppointmentRequest.objects.filter(email="pooja.mehta@example.com").first()
            self.assertIsNotNone(req_obj, "Appointment must not be deleted or lost on email failure!")
            self.assertEqual(req_obj.status, "pending")
            self.assertEqual(req_obj.email_notification_status, "failed")
            self.assertIn("SMTP Connection Refused", req_obj.notification_error)

            # Exactly one record was created (no duplicates)
            self.assertEqual(PublicAppointmentRequest.objects.filter(email="pooja.mehta@example.com").count(), 1)
