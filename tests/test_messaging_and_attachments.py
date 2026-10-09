from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import Message
from tests.test_helpers import BaseHospitalTestCase

class MessagingAndAttachmentTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital_a = self.create_hospital(name="Alpha Clinic", slug="alpha-clinic")
        self.hospital_b = self.create_hospital(name="Beta Clinic", slug="beta-clinic")

        # Clinic A Admin & Patient
        self.admin_a = self.create_clinic_admin(hospital=self.hospital_a, username="admin_a", email="admin_a@test.com")
        self.patient_a = self.create_patient(hospital=self.hospital_a, username="patient_a", email="patient_a@test.com")

        # Clinic B Admin & Patient (Cross-clinic test)
        self.admin_b = self.create_clinic_admin(hospital=self.hospital_b, username="admin_b", email="admin_b@test.com")
        self.patient_b = self.create_patient(hospital=self.hospital_b, username="patient_b", email="patient_b@test.com")

    def test_client_chat_view_renders_single_conversation(self):
        self.client.force_login(self.patient_a)
        response = self.client.get(reverse("client_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Direct Consultation')
        self.assertContains(response, 'chatArea')
        self.assertContains(response, 'filePreviewPill')

    def test_admin_chat_detail_view_renders(self):
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_chat_detail", args=[self.patient_a.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chatArea')
        self.assertContains(response, 'attachmentPreviewPill')

    def test_send_valid_text_message(self):
        self.client.force_login(self.patient_a)
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.admin_a.id,
            "content": "Hello Doctor, reporting on my exercise routine."
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("content"), "Hello Doctor, reporting on my exercise routine.")

        # Check DB
        msg = Message.objects.filter(sender=self.patient_a, receiver=self.admin_a).first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.hospital, self.hospital_a)

    def test_reject_empty_message_without_attachment(self):
        self.client.force_login(self.patient_a)
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.admin_a.id,
            "content": "   "
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_send_message_with_valid_pdf_attachment(self):
        self.client.force_login(self.patient_a)
        pdf_file = SimpleUploadedFile("report.pdf", b"%PDF-1.4 simulated pdf content", content_type="application/pdf")
        
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.admin_a.id,
            "content": "Here is my blood work PDF report.",
            "attachment": pdf_file
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("attachment_name"), "report.pdf")
        self.assertTrue(data.get("has_attachment"))

        # Verify DB
        msg = Message.objects.get(id=data["id"])
        self.assertTrue(bool(msg.attachment))
        self.assertEqual(msg.attachment_name, "report.pdf")

    def test_send_message_with_valid_image_attachment(self):
        import io
        from PIL import Image
        self.client.force_login(self.admin_a)
        
        img_io = io.BytesIO()
        Image.new('RGB', (20, 20), color='green').save(img_io, format='PNG')
        img_file = SimpleUploadedFile("scan.png", img_io.getvalue(), content_type="image/png")
        
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.patient_a.id,
            "content": "Here is the ultrasound image.",
            "attachment": img_file
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("has_attachment"))
        self.assertEqual(data.get("attachment_name"), "scan.png")

    def test_reject_disallowed_file_extension(self):
        self.client.force_login(self.patient_a)
        script_file = SimpleUploadedFile("malicious.exe", b"MZ executable content", content_type="application/x-msdownload")
        
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.admin_a.id,
            "content": "Check this file",
            "attachment": script_file
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertTrue("prohibited" in data["error"].lower() or "not permitted" in data["error"].lower())

    def test_reject_oversized_file(self):
        self.client.force_login(self.patient_a)
        big_file = SimpleUploadedFile("large_mri.pdf", b"0" * (11 * 1024 * 1024), content_type="application/pdf")
        
        response = self.client.post(reverse("api_chat_send"), {
            "receiver_id": self.admin_a.id,
            "content": "Check large scan",
            "attachment": big_file
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("10MB", data["error"])

    def test_authorized_attachment_download(self):
        pdf_file = SimpleUploadedFile("clinical_notes.pdf", b"%PDF-1.4 test notes", content_type="application/pdf")
        msg = Message.objects.create(
            sender=self.admin_a,
            receiver=self.patient_a,
            hospital=self.hospital_a,
            content="Clinical notes attached",
            attachment=pdf_file,
            attachment_name="clinical_notes.pdf",
            attachment_size=18,
            attachment_type="document"
        )

        self.client.force_login(self.patient_a)
        dl_url = reverse("download_chat_attachment", args=[msg.id])
        response = self.client.get(dl_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn('attachment; filename="clinical_notes.pdf"', response["Content-Disposition"])

    def test_unauthorized_user_cannot_download_private_attachment(self):
        pdf_file = SimpleUploadedFile("private_chart.pdf", b"%PDF-1.4 private patient chart", content_type="application/pdf")
        msg = Message.objects.create(
            sender=self.admin_a,
            receiver=self.patient_a,
            hospital=self.hospital_a,
            content="Private chart",
            attachment=pdf_file,
            attachment_name="private_chart.pdf",
            attachment_size=25,
            attachment_type="document"
        )

        # Patient B from Clinic B tries to download Clinic A patient's attachment
        self.client.force_login(self.patient_b)
        dl_url = reverse("download_chat_attachment", args=[msg.id])
        response = self.client.get(dl_url)
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_download_attachment(self):
        pdf_file = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 doc", content_type="application/pdf")
        msg = Message.objects.create(
            sender=self.admin_a,
            receiver=self.patient_a,
            hospital=self.hospital_a,
            attachment=pdf_file,
            attachment_name="doc.pdf",
            attachment_type="document"
        )

        self.client.logout()
        dl_url = reverse("download_chat_attachment", args=[msg.id])
        response = self.client.get(dl_url)
        self.assertEqual(response.status_code, 302)

    def test_admin_chat_list_renders_instagram_dm_layout(self):
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chat-dm-container')
        self.assertContains(response, 'chat-mode-list')
        self.assertContains(response, 'chat-inbox-panel')
        self.assertContains(response, 'patientChatSearch')
        self.assertContains(response, 'Your Messages')

    def test_admin_chat_detail_renders_two_panel_workspace(self):
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse("admin_chat_detail", args=[self.patient_a.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chat-dm-container')
        self.assertContains(response, 'chat-mode-detail')
        self.assertContains(response, 'chat-inbox-panel')
        self.assertContains(response, 'chat-conversation-panel')
        self.assertContains(response, 'chat-back-btn')
        self.assertContains(response, 'chat-attach-btn')

    def test_admin_doctor_chat_and_detail_render_instagram_layout(self):
        staff = self.create_staff(hospital=self.hospital_a, username="dr_staff_a", email="dr_a@test.com")
        self.client.force_login(self.admin_a)

        # Doctor chat list
        response = self.client.get(reverse("admin_doctor_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chat-dm-container')
        self.assertContains(response, 'doctorChatSearch')

        # Doctor chat detail
        response_detail = self.client.get(reverse("admin_doctor_chat_detail", args=[staff.id]))
        self.assertEqual(response_detail.status_code, 200)
        self.assertContains(response_detail, 'chat-dm-container')
        self.assertContains(response_detail, 'chat-conversation-panel')
        self.assertContains(response_detail, 'chat-back-btn')
        self.assertContains(response_detail, 'chat-attach-btn')
