"""
Tests for Vercel serverless deployment resilience, entrypoint routing, and production settings.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from io import BytesIO


class VercelServerlessDeploymentTests(SimpleTestCase):
    """Verify production settings, entrypoint exports, and cold start resilience on Vercel."""

    def test_wsgi_entrypoint_exposes_application_and_app(self):
        """Confirm myproject.wsgi exposes both standard application and Vercel app alias."""
        from myproject import wsgi
        self.assertTrue(hasattr(wsgi, "application"))
        self.assertTrue(hasattr(wsgi, "app"))
        self.assertIs(wsgi.application, wsgi.app)

    def test_app_py_compatibility_module(self):
        """Confirm root app.py exposes app and application."""
        import app
        self.assertTrue(hasattr(app, "application"))
        self.assertTrue(hasattr(app, "app"))
        self.assertIs(app.application, app.app)

    @override_settings(
        SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
        ALLOWED_HOSTS=["hospital-managemant-drdhvani.vercel.app", ".vercel.app", "localhost", "127.0.0.1"]
    )
    def test_public_routes_cold_start_resilience(self):
        """
        Verify that public routes (/, /about/, /services/, /contact/, /book-appointment/)
        render without crashing even when models are empty or database queries encounter cold tables.
        """
        app = get_wsgi_application()

        routes = ["/", "/about/", "/services/", "/contact/", "/book-appointment/"]
        for path in routes:
            environ = {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path,
                "SERVER_NAME": "hospital-managemant-drdhvani.vercel.app",
                "SERVER_PORT": "443",
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": "https",
                "wsgi.input": BytesIO(b""),
                "wsgi.errors": BytesIO(),
                "wsgi.multithread": False,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False,
                "HTTP_HOST": "hospital-managemant-drdhvani.vercel.app",
                "HTTP_COOKIE": "sessionid=test_cookie_session_123",
            }
            status_holder = []
            headers_holder = []

            def start_response(status, headers, exc_info=None):
                status_holder.append(status)
                headers_holder.append(headers)

            response_body = b"".join(app(environ, start_response))
            self.assertTrue(len(status_holder) > 0, f"No status returned for {path}")
            self.assertEqual(
                status_holder[0].split()[0],
                "200",
                f"Expected 200 OK for {path}, got {status_holder[0]}. Body: {response_body[:200]}"
            )
            self.assertTrue(len(response_body) > 1000, f"Response too small for {path}")


from django.test import TestCase


class VercelMigratedDatabaseTests(TestCase):
    """Verify that public routes render properly when models and database tables exist."""

    @override_settings(
        SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
        ALLOWED_HOSTS=["hospital-managemant-drdhvani.vercel.app", ".vercel.app", "localhost", "127.0.0.1"]
    )
    def test_public_routes_with_database_tables(self):
        """Confirm all public pages return 200 OK with active database."""
        routes = ["/", "/about/", "/services/", "/contact/", "/book-appointment/"]
        for path in routes:
            response = self.client.get(path, HTTP_HOST="hospital-managemant-drdhvani.vercel.app")
            self.assertEqual(response.status_code, 200, f"Failed for {path}")

