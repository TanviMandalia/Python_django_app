from django.test import TestCase, RequestFactory
from django.conf import settings
from django.urls import reverse
from core.views import csrf_failure_view
import json

class CSRFResilienceTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_csrf_failure_view_renders_branded_template(self):
        """CSRF failure view should return 403 with clinic-branded template."""
        request = self.factory.post("/book-appointment/")
        response = csrf_failure_view(request, reason="CSRF token from POST incorrect.")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Security Verification Notice", status_code=403)
        self.assertContains(response, "Refresh & Try Again", status_code=403)

    def test_csrf_failure_view_json_for_ajax(self):
        """AJAX/fetch requests rejected by CSRF receive structured JSON with csrf_refresh flag."""
        request = self.factory.post(
            "/api/chat/send/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        response = csrf_failure_view(request, reason="CSRF token from POST incorrect.")
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content.decode("utf-8"))
        self.assertTrue(data.get("csrf_refresh"))
        self.assertIn("error", data)

    def test_csrf_settings_configured(self):
        """Verify CSRF_FAILURE_VIEW and CSRF_COOKIE_HTTPONLY settings are properly configured."""
        self.assertEqual(settings.CSRF_FAILURE_VIEW, "core.views.csrf_failure_view")
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)
        self.assertIn("https://*.onrender.com", settings.CSRF_TRUSTED_ORIGINS)
        self.assertIn("http://localhost:8000", settings.CSRF_TRUSTED_ORIGINS)
