from django.urls import reverse
from tests.test_helpers import BaseHospitalTestCase

class SidebarNavigationTests(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Primary Care Clinic", slug="primary-care")
        self.superadmin = self.create_super_admin()
        self.admin = self.create_clinic_admin(hospital=self.hospital, username="admin_test", email="admin@test.com")
        self.staff = self.create_staff(hospital=self.hospital, username="staff_test", email="staff@test.com")
        self.patient = self.create_patient(hospital=self.hospital, username="patient_test", email="patient@test.com")

    def test_superadmin_sidebar_and_navigation(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="superAdminSidebar"')
        self.assertContains(response, 'SaaS Platform Control Panel')
        self.assertContains(response, 'Multi-Tenant Platform Owner')

    def test_admin_sidebar_and_navigation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="adminSidebar"')
        self.assertContains(response, 'id="menuToggle"')
        self.assertContains(response, 'Dashboard Overview')

    def test_staff_sidebar_and_navigation(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="staffSidebar"')
        self.assertContains(response, 'topbar-toggle-btn')
        self.assertContains(response, 'Staff Dashboard')

    def test_client_sidebar_and_navigation(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="clientSidebar"')
        self.assertContains(response, 'id="menuToggle"')
        self.assertContains(response, 'Patient Dashboard')

    def test_unauthenticated_sidebar_access_redirects(self):
        self.client.logout()
        for url_name in ["super_admin_dashboard", "admin_dashboard", "staff_dashboard", "client_dashboard"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)

    def test_chat_detail_controls_are_independent(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_chat_detail", args=[self.patient.id]))
        self.assertEqual(response.status_code, 200)

        # Back button is dedicated .chat-back-btn and points to admin_chat
        self.assertContains(response, 'class="chat-back-btn"')
        self.assertContains(response, f'href="{reverse("admin_chat")}"')
        
        # Attachment button is dedicated .chat-attach-btn with type="button"
        self.assertContains(response, 'class="chat-attach-btn"')
        self.assertContains(response, 'type="button"')

        # Verify that back button and attachment button do NOT have topbar-toggle-btn
        content = response.content.decode("utf-8")
        self.assertNotIn('class="topbar-toggle-btn" style="width: 36px; height: 36px;', content)
        self.assertNotIn('class="topbar-toggle-btn" onclick="document.getElementById(\'chatFileInput\')', content)

    def test_layout_js_does_not_attach_sidebar_toggle_to_generic_topbar_buttons(self):
        import os
        from django.conf import settings
        layout_js_path = os.path.join(settings.BASE_DIR, "static", "js", "layout.js")
        with open(layout_js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        # .topbar-toggle-btn must NOT be in the sidebar toggle selectors
        self.assertNotIn(".topbar-toggle-btn", js_content)
        self.assertIn("#menuToggle", js_content)
        self.assertIn("#mobileMenuBtn", js_content)
        self.assertIn(".sidebar-toggle-btn", js_content)
