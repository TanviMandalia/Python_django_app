import io
import json
from decimal import Decimal
from PIL import Image
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from core.models import (
    Hospital,
    ClinicAdmin,
    StaffProfile,
    PatientProfile,
    Appointment,
    SessionNote,
    ClinicSettings,
    ClinicPromo,
    DailyTask,
    LeaveApplication,
    Message,
)

User = get_user_model()


class SecurityAuditRemediationTests(TestCase):
    def setUp(self):
        # Hospital A
        self.hospital_a = Hospital.objects.create(
            name="Clinic Alpha",
            slug="clinic-alpha",
            email="admin@alpha.com",
            phone="9000000001",
            address="Alpha Street, Mumbai",
            is_active=True,
        )
        self.admin_a = User.objects.create_user(
            username="admin_alpha",
            email="admin@alpha.com",
            password="AdminAlphaPass123!",
            is_staff=True,
        )
        self.clinic_admin_a = ClinicAdmin.objects.create(
            user=self.admin_a,
            hospital=self.hospital_a,
        )
        self.patient_a = User.objects.create_user(
            username="patient_alpha",
            email="patient.alpha@example.com",
            password="PatientAlphaPass123!",
        )
        self.patient_profile_a = PatientProfile.objects.create(
            user=self.patient_a,
            hospital=self.hospital_a,
        )
        self.appt_a = Appointment.objects.create(
            hospital=self.hospital_a,
            patient=self.patient_a,
            name="Patient Alpha",
            email="patient.alpha@example.com",
            phone="9000000011",
            service="orthopedic",
            date=timezone.now().date(),
            time="10:00 AM",
            status="confirmed",
        )
        self.note_a = SessionNote.objects.create(
            hospital=self.hospital_a,
            staff=self.admin_a,
            patient=self.patient_a,
            appointment=self.appt_a,
            diagnosis="Lumbar strain",
            treatment="Spinal decompression",
            next_session="Friday 10am",
        )

        # Hospital B
        self.hospital_b = Hospital.objects.create(
            name="Clinic Beta",
            slug="clinic-beta",
            email="admin@beta.com",
            phone="9000000002",
            address="Beta Road, Pune",
            is_active=True,
        )
        self.admin_b = User.objects.create_user(
            username="admin_beta",
            email="admin@beta.com",
            password="AdminBetaPass123!",
            is_staff=True,
        )
        self.clinic_admin_b = ClinicAdmin.objects.create(
            user=self.admin_b,
            hospital=self.hospital_b,
        )
        self.patient_b = User.objects.create_user(
            username="patient_beta",
            email="patient.beta@example.com",
            password="PatientBetaPass123!",
        )
        self.patient_profile_b = PatientProfile.objects.create(
            user=self.patient_b,
            hospital=self.hospital_b,
        )
        self.appt_b = Appointment.objects.create(
            hospital=self.hospital_b,
            patient=self.patient_b,
            name="Patient Beta",
            email="patient.beta@example.com",
            phone="9000000022",
            service="neurological",
            date=timezone.now().date(),
            time="11:00 AM",
            status="confirmed",
        )

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="platform_root",
            email="root@platform.com",
            password="PlatformRootPass123!",
        )

        self.client = Client()

    def test_three_previously_erroring_admin_pages_return_200(self):
        """
        Verify the 3 pages reported by the user:
        1. Session Notes (/admin-session-notes/)
        2. Patient Messages (/admin-chat/)
        3. Admin Settings (/admin-settings/)
        All load with HTTP 200 without crashes or ValueError.
        """
        self.client.force_login(self.admin_a)

        # 1. Session Notes
        resp_notes = self.client.get("/admin-session-notes/")
        self.assertEqual(resp_notes.status_code, 200)

        # 2. Patient Messages (Admin Chat)
        resp_chat = self.client.get("/admin-chat/")
        self.assertEqual(resp_chat.status_code, 200)

        # 2b. Patient Message Detail
        resp_chat_det = self.client.get(f"/admin-chat/{self.patient_a.id}/")
        self.assertEqual(resp_chat_det.status_code, 200)

        # 3. Admin Settings
        resp_settings = self.client.get("/admin-settings/")
        self.assertEqual(resp_settings.status_code, 200)

    def test_admin_settings_post_update_no_unpacking_error(self):
        """
        Test that POST to /admin-settings/ works seamlessly without
        'cannot unpack non-iterable bool object' error.
        """
        self.client.force_login(self.admin_a)
        post_data = {
            "clinic_name": "Clinic Alpha Updated",
            "phone": "9998887776",
            "email": "alpha.updated@clinic.com",
            "address": "456 New Road",
            "opening_hours": "9 AM - 7 PM",
            "primary_color": "#2563EB",
            "upi_id": "alpha@okhdfcbank",
        }
        resp = self.client.post("/admin-settings/", data=post_data)
        self.assertEqual(resp.status_code, 302)  # Successful redirect to admin_settings
        self.assertEqual(resp.url, "/admin-settings/")

    def test_reports_analytics_multi_tenant_isolation(self):
        """
        Ensure clinic A's reports_analytics only includes Clinic A data,
        never leaking Clinic B data.
        """
        self.client.force_login(self.admin_a)
        resp = self.client.get("/analytics/")
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx["total_appointments"], 1)  # Only Appt A
        self.assertEqual(ctx["total_patients"], 1)      # Only Patient A
        self.assertEqual(ctx["total_notes"], 1)         # Only Note A

    def test_export_patients_multi_tenant_isolation(self):
        """
        Ensure export_patients_excel and export_patients_pdf only contain
        patients from the admin's clinic.
        """
        self.client.force_login(self.admin_a)

        # Excel Export
        resp_excel = self.client.get("/export/patients/excel/")
        self.assertEqual(resp_excel.status_code, 200)
        self.assertEqual(
            resp_excel["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # PDF Export
        resp_pdf = self.client.get("/export/patients/pdf/")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf["Content-Type"], "application/pdf")

    def test_export_appointments_multi_tenant_isolation(self):
        """
        Ensure export_appointments_excel and export_appointments_pdf only
        contain appointments from the admin's clinic.
        """
        self.client.force_login(self.admin_a)

        resp_excel = self.client.get("/export/appointments/excel/")
        self.assertEqual(resp_excel.status_code, 200)

        resp_pdf = self.client.get("/export/appointments/pdf/")
        self.assertEqual(resp_pdf.status_code, 200)

    def test_export_analytics_pdf_multi_tenant_isolation(self):
        """
        Ensure export_analytics_pdf executes cleanly with scoped metrics.
        """
        self.client.force_login(self.admin_a)
        resp = self.client.get("/export/analytics/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_admin_promos_multi_tenant_isolation(self):
        """
        Ensure clinic promos are scoped to the creator clinic and deleted only by owner.
        """
        self.client.force_login(self.admin_a)
        add_resp = self.client.post("/admin-promos/add/", data={
            "title": "Summer Rehab Discount",
            "message": "20% off all consultations",
        })
        self.assertEqual(add_resp.status_code, 302)

        promo = ClinicPromo.objects.filter(title="Summer Rehab Discount").first()
        self.assertIsNotNone(promo)
        self.assertEqual(promo.hospital, self.hospital_a)

        # Clinic B admin attempts to delete Clinic A promo -> 404
        self.client.force_login(self.admin_b)
        del_resp = self.client.get(f"/admin-promos/delete/{promo.id}/")
        self.assertEqual(del_resp.status_code, 404)
        self.assertTrue(ClinicPromo.objects.filter(id=promo.id).exists())

    def test_send_exercise_reminder_cross_tenant_prevention(self):
        """
        Clinic A admin cannot trigger reminders to Clinic B's patients.
        """
        self.client.force_login(self.admin_a)
        # Attempt to send reminder to patient_b
        resp = self.client.get(f"/send-exercise-reminder/{self.patient_b.id}/")
        self.assertEqual(resp.status_code, 302)
        # Follow redirect and check message
        follow_resp = self.client.get(resp.url)
        self.assertContains(follow_resp, "Access denied: Patient does not belong to your clinic")

    def test_ajax_chat_authorization_and_xss_sanitization(self):
        """
        Test api_chat_send and api_chat_fetch:
        1. Unauthorized cross-clinic chatting returns 403.
        2. Authorized communication strips XSS scripts.
        """
        # Patient A chatting with Admin A is authorized
        self.client.force_login(self.patient_a)
        msg_payload = {
            "receiver_id": self.admin_a.id,
            "content": "Hello Doctor <script>alert('xss')</script> I feel better!",
        }
        resp = self.client.post(
            "/api/chat/send/",
            data=json.dumps(msg_payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotIn("<script>", data["content"])
        self.assertIn("Hello Doctor", data["content"])

        # Patient A trying to chat with Admin B (unrelated clinic) returns 403
        bad_payload = {
            "receiver_id": self.admin_b.id,
            "content": "Sneaking into Beta clinic",
        }
        resp_bad = self.client.post(
            "/api/chat/send/",
            data=json.dumps(bad_payload),
            content_type="application/json",
        )
        self.assertEqual(resp_bad.status_code, 403)
