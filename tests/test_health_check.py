import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.db import OperationalError


class HealthCheckTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_healthz_success(self):
        """GET /healthz returns 200 OK and status 'ok' when database is healthy."""
        response = self.client.get("/healthz")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert "no-cache" in response["Cache-Control"]
        assert "no-store" in response["Cache-Control"]
        data = json.loads(response.content.decode("utf-8"))
        assert data == {"status": "ok"}

    def test_healthz_trailing_slash_success(self):
        """GET /healthz/ also resolves cleanly with 200 OK."""
        response = self.client.get("/healthz/")
        assert response.status_code == 200
        data = json.loads(response.content.decode("utf-8"))
        assert data == {"status": "ok"}

    def test_healthz_head_method_allowed(self):
        """HEAD /healthz is allowed for lightweight liveness probes."""
        response = self.client.head("/healthz")
        assert response.status_code == 200

    def test_healthz_disallowed_methods(self):
        """Disallowed methods return 405 Method Not Allowed."""
        for method in ["post", "put", "delete", "patch"]:
            client_method = getattr(self.client, method)
            response = client_method("/healthz")
            assert response.status_code == 405

    def test_healthz_database_failure_returns_503(self):
        """When database probe fails, returns 503 with safe 'unhealthy' payload."""
        with patch("django.db.connection.cursor", side_effect=OperationalError("DB Connection timeout")):
            response = self.client.get("/healthz")
            assert response.status_code == 503
            assert response["Content-Type"] == "application/json"
            assert "no-cache" in response["Cache-Control"]
            assert "no-store" in response["Cache-Control"]
            data = json.loads(response.content.decode("utf-8"))
            assert data == {"status": "unhealthy"}

    def test_healthz_does_not_leak_internals_on_error(self):
        """Ensure no stack trace, error message, or SQL string leaks in the response."""
        secret_leak_attempt = "CRITICAL_INTERNAL_DB_PASSWORD_12345"
        with patch("django.db.connection.cursor", side_effect=Exception(secret_leak_attempt)):
            response = self.client.get("/healthz")
            assert response.status_code == 503
            raw_body = response.content.decode("utf-8")
            assert secret_leak_attempt not in raw_body
            assert "Traceback" not in raw_body
            assert "SELECT" not in raw_body
