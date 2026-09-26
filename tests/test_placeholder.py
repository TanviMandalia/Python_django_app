"""
Placeholder test to confirm both pytest and Django test runner work properly.
"""
from django.conf import settings
from django.test import SimpleTestCase


def test_basic_math():
    """Simple passing test function for pytest."""
    assert 1 + 1 == 2


class PlaceholderTestCase(SimpleTestCase):
    """Simple test case for Django test runner and pytest."""

    def test_settings_loaded(self):
        self.assertTrue(settings.configured)
        self.assertIn("core.apps.CoreConfig", settings.INSTALLED_APPS)
