"""Regression coverage for Google Maps review redirects and review navigation."""

from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from core.google_reviews import is_safe_google_review_url


class GoogleReviewRedirectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.review_url = reverse("review_google_redirect")

    def test_legacy_review_paths_redirect_to_configured_google_maps_reviews(self):
        """All public review entry points forward to the selected clinic Reviews tab."""
        expected = settings.GOOGLE_REVIEW_URL
        self.assertTrue(is_safe_google_review_url(expected))

        for route in ("public_review", "public_reviews_alias", "review_google_redirect"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], expected)

    def test_google_maps_reviews_link_is_explicitly_safe(self):
        self.assertTrue(is_safe_google_review_url(settings.GOOGLE_REVIEW_URL))
        self.assertFalse(is_safe_google_review_url("http://maps.google.com/"))
        self.assertFalse(is_safe_google_review_url("https://maps.google.com.evil.example/"))
        self.assertFalse(is_safe_google_review_url("javascript:alert(1)"))

    def test_safe_google_target_is_allowed(self):
        target = "https://g.page/r/Cd12345/review"
        response = self.client.get(f"{self.review_url}?target={target}", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], target)

    def test_untrusted_target_is_ignored_and_uses_clinic_destination(self):
        response = self.client.get(
            f"{self.review_url}?target=https://malicious-attacker.example/steal",
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.GOOGLE_REVIEW_URL)
        self.assertNotIn("malicious-attacker", response["Location"])

    def test_unconfigured_destination_returns_clear_setup_error(self):
        with patch.dict("os.environ", {"GOOGLE_REVIEW_URL": ""}):
            with patch("django.conf.settings.GOOGLE_REVIEW_URL", ""):
                response = self.client.get(self.review_url, follow=False)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Get more reviews", status_code=503)

    def test_public_navigation_keeps_review_links(self):
        home = self.client.get(reverse("home"))
        contact = self.client.get(reverse("contact"))
        self.assertContains(home, reverse("review_google_redirect"))
        self.assertContains(home, "Review Us")
        self.assertContains(contact, reverse("review_google_redirect"))

    def test_sitemap_omits_redirect_only_review_routes(self):
        response = self.client.get(reverse("sitemap_xml"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/review/")

    def test_login_and_booking_routes_remain_available(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("public_book_appointment")).status_code, 200)
