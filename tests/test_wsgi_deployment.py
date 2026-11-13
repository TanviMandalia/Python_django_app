"""Smoke tests for the standard Django WSGI deployment entrypoints."""

from django.test import TestCase


class WsgiDeploymentTests(TestCase):
    """Verify the WSGI callable and public pages work with the test database."""

    def test_wsgi_entrypoint_exposes_application(self):
        from myproject import wsgi

        self.assertTrue(callable(wsgi.application))

    def test_render_gunicorn_compatibility_module(self):
        import app

        self.assertIs(app.application, app.app)
        self.assertTrue(callable(app.app))

    def test_public_pages_render(self):
        for path in ("/", "/about/", "/services/", "/contact/", "/book-appointment/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="localhost")
                self.assertEqual(response.status_code, 200)
