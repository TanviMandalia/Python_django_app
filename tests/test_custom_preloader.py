import os
from django.urls import reverse
from django.conf import settings
from tests.test_helpers import BaseHospitalTestCase


class CustomLoadingScreenTests(BaseHospitalTestCase):
    """
    Test suite for the Premium Custom Loading Screen across public pages,
    authentication views, and role-based portal dashboards.
    """

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Alpha Care Clinic", email="contact@alphacare.com")
        self.admin_user = self.create_clinic_admin(self.hospital, username="test_clinic_admin")
        self.patient_user = self.create_patient(self.hospital, username="test_patient")
        self.staff_user = self.create_staff(self.hospital, username="test_staff")
        self.super_user = self.create_super_admin(username="test_super_admin")

    def test_preloader_rendered_on_homepage(self):
        """Home page must render the branded preloader and critical CSS immediately."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Must have preloader element
        self.assertIn('id="clinic-preloader"', content)
        # Must have accessible status attributes
        self.assertIn('role="status"', content)
        self.assertIn('aria-live="polite"', content)
        # Must contain clinic branding
        self.assertIn("Dr. Dhvani Patalia", content)
        # Must contain indeterminate progress bar
        self.assertIn("clinic-preloader-progress-bar", content)
        # Must include critical inline CSS
        self.assertIn("clinic-preloader-critical-css", content)
        # Must include preloader.js
        self.assertIn("preloader.js", content)
        # Must include fallback retry card
        self.assertIn("clinic-preloader-fallback", content)
        self.assertIn("Continue to Site", content)

    def test_preloader_on_public_pages(self):
        """Preloader must be present on Services, About, Contact, and Blogs."""
        for url_name in ["services", "about", "contact", "blog_list"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, f"Failed for {url_name}")
            content = response.content.decode("utf-8")
            self.assertIn('id="clinic-preloader"', content, f"Preloader missing on {url_name}")
            self.assertIn("preloader.js", content, f"preloader.js missing on {url_name}")

    def test_preloader_on_auth_pages(self):
        """Login and Register pages must render the preloader cleanly."""
        for url_name in ["login", "register", "request_otp"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, f"Failed for {url_name}")
            content = response.content.decode("utf-8")
            self.assertIn('id="clinic-preloader"', content, f"Preloader missing on {url_name}")
            self.assertIn("preloader.js", content, f"preloader.js missing on {url_name}")

    def test_preloader_on_clinic_admin_dashboard(self):
        """Clinic Admin dashboard must include preloader with admin-specific context."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="clinic-preloader"', content)
        self.assertIn("Clinic Administration Portal", content)
        self.assertIn("Loading clinical workspace", content)
        self.assertIn("preloader.js", content)

    def test_preloader_on_patient_dashboard(self):
        """Patient portal dashboard must include preloader with patient-specific context."""
        self.client.force_login(self.patient_user)
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="clinic-preloader"', content)
        self.assertIn("Patient & Client Portal", content)
        self.assertIn("Preparing your patient care portal", content)
        self.assertIn("preloader.js", content)

    def test_preloader_on_staff_dashboard(self):
        """Staff portal dashboard must include preloader with staff-specific context."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="clinic-preloader"', content)
        self.assertIn("Clinical Staff Workspace", content)
        self.assertIn("Loading therapist workspace", content)
        self.assertIn("preloader.js", content)

    def test_preloader_on_super_admin_dashboard(self):
        """Super Admin dashboard must include preloader with platform control context."""
        self.client.force_login(self.super_user)
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="clinic-preloader"', content)
        self.assertIn("Platform Control Panel", content)
        self.assertIn("Loading system administration", content)
        self.assertIn("preloader.js", content)

    def test_preloader_critical_css_invariants(self):
        """Preloader critical CSS must contain reduced motion, no fake numbers, and scroll lock."""
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        # Scroll locking classes
        self.assertIn("clinic-preloader-locked", content)
        # Prefers-reduced-motion media query
        self.assertIn("@media (prefers-reduced-motion: reduce)", content)
        # Smooth fadeout class
        self.assertIn("clinic-preloader-fadeout", content)
        # Indeterminate shimmer animation
        self.assertIn("cp-shimmer", content)

    def test_service_worker_security_and_bypasses(self):
        """Service Worker must strictly bypass all private portals and authentication endpoints."""
        sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
        self.assertTrue(os.path.exists(sw_path), "static/sw.js must exist")

        with open(sw_path, "r", encoding="utf-8") as f:
            sw_content = f.read()

        # Invariant checks: Must bypass private endpoints
        self.assertIn("url.pathname.startsWith('/admin')", sw_content)
        self.assertIn("url.pathname.startsWith('/client')", sw_content)
        self.assertIn("url.pathname.startsWith('/staff')", sw_content)
        self.assertIn("url.pathname.startsWith('/super-admin')", sw_content)
        self.assertIn("url.pathname.startsWith('/api')", sw_content)
        self.assertIn("url.pathname.startsWith('/login')", sw_content)
        self.assertIn("url.pathname.startsWith('/media')", sw_content)
        # Must only cache static assets
        self.assertIn("url.pathname.startsWith('/static/')", sw_content)

    def test_healthz_remains_lightweight(self):
        """Health check endpoint must remain ultra lightweight and return HTTP 200 with status ok."""
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_standalone_gateway_html_exists_and_valid(self):
        """Standalone static preloader gateway must exist and contain branded elements."""
        gateway_path = os.path.join(settings.BASE_DIR, "public_gateway", "index.html")
        self.assertTrue(os.path.exists(gateway_path), "public_gateway/index.html must exist")

        with open(gateway_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Branding checks
        self.assertIn("Dr. Dhvani Patalia", content)
        self.assertIn("Physio Rehab &amp; Sports Medicine", content)
        # Probe & redirection checks
        self.assertIn("/healthz", content)
        self.assertIn("status: 'ok'", content)
        # Accessibility
        self.assertIn('role="status"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn("@media (prefers-reduced-motion: reduce)", content)
        # No fake percentage indicators
        self.assertNotIn("90% loaded", content)
        self.assertNotIn("99% loaded", content)
        self.assertNotIn("progress-percent", content)


    def test_cloudflare_worker_exists_and_valid(self):
        """Cloudflare Worker script must exist and contain intercept and polling logic."""
        worker_path = os.path.join(settings.BASE_DIR, "cloudflare_worker", "worker.js")
        self.assertTrue(os.path.exists(worker_path), "cloudflare_worker/worker.js must exist")

        with open(worker_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("SERVICE WAKING UP", content)
        self.assertIn("serveBrandedLoader", content)
        self.assertIn("/healthz", content)
        self.assertIn("Dr. Dhvani Patalia", content)

    def test_keep_alive_workflow_exists(self):
        """Render Keep-Alive GitHub Actions workflow must be configured."""
        workflow_path = os.path.join(settings.BASE_DIR, ".github", "workflows", "render_keep_alive.yml")
        self.assertTrue(os.path.exists(workflow_path), "render_keep_alive.yml must exist")

        with open(workflow_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Render Service Keep-Alive", content)
        self.assertIn("*/10 * * * *", content)
        self.assertIn("/healthz", content)

