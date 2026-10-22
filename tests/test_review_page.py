"""
Unit, integration, and security tests for the dedicated Physio Rehab Review Page (/review/):
1. Public accessibility (HTTP 200 without login)
2. Alias redirect (/reviews/ -> /review/)
3. Clinic branding and logo presence
4. Required welcoming heading and thank you message
5. Absence of Google Maps embeds or iframes
6. In-app review form submission, moderation (is_approved=False), and consent handling
7. Anti-spam honeypot defense
8. Open redirect prevention on /review/google/
9. Safe handling when Google Review URL is unconfigured vs configured
10. Footer and mobile navigation links
11. Dynamic inclusion in sitemap.xml
12. Preservation of existing login, logout, and booking flows
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from unittest.mock import patch
from core.models import Review, Hospital, Treatment, TreatmentCategory
from core.google_reviews import is_safe_google_review_url


class PublicReviewPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.hospital = Hospital.objects.create(
            name="Dr. Dhvani Patalia Physio Rehab",
            slug="dhvani-physio",
        )
        self.category = TreatmentCategory.objects.create(
            name="Chiropractic",
            slug="chiropractic",
            is_active=True,
        )
        self.treatment = Treatment.objects.create(
            category=self.category,
            name="Spine Alignment",
            slug="spine-alignment",
            is_active=True,
        )

    def test_review_page_accessible_without_login(self):
        """GET /review/ returns HTTP 200 without requiring user authentication."""
        response = self.client.get(reverse("public_review"))
        self.assertEqual(response.status_code, 200)

    def test_reviews_plural_alias_redirects_to_review(self):
        """GET /reviews/ permanently redirects to /review/."""
        response = self.client.get("/reviews/")
        self.assertRedirects(response, reverse("public_review"), status_code=301)

    def test_review_page_displays_clinic_branding_and_logo(self):
        """Review page displays actual clinic name and logo asset."""
        response = self.client.get(reverse("public_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dr. Dhvani Patalia Physio Rehab")
        self.assertContains(response, "Dhvani_Patalia.jpeg")

    def test_review_page_contains_required_heading_and_gratitude_copy(self):
        """Page includes welcoming heading and patient gratitude message."""
        response = self.client.get(reverse("public_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How was your experience with")
        self.assertContains(response, "Physio Rehab?")
        self.assertContains(response, "Thank you for trusting Dr. Dhvani Patalia Physio Rehab")

    def test_review_page_contains_no_google_maps_embed(self):
        """Page contains our own design without any Google Maps iframe or embed."""
        response = self.client.get(reverse("public_review"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<iframe")
        self.assertNotContains(response, "maps.google.com/maps/embed")

    def test_review_page_has_secondary_navigation_to_home(self):
        """Page provides clear secondary option to return to homepage and book appointment."""
        response = self.client.get(reverse("public_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("home"))
        self.assertContains(response, "Return to Homepage")
        self.assertContains(response, reverse("public_book_appointment"))

    def test_submit_valid_review_creates_unapproved_moderated_record(self):
        """Submitting a valid review creates a Review with is_approved=False and consent_to_publish=True."""
        payload = {
            "reviewer_name": "Rohan Shah",
            "rating": 5,
            "treatment": self.treatment.id,
            "message": "Outstanding recovery and professional chiropractic treatment by Dr. Dhvani.",
            "consent_to_publish": "on",
            "website": "",  # Empty honeypot
        }
        response = self.client.post(reverse("public_review"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you for sharing your experience!")

        # Verify DB entry
        rev = Review.objects.filter(reviewer_name="Rohan Shah").first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.rating, 5)
        self.assertEqual(rev.treatment, self.treatment)
        self.assertFalse(rev.is_approved)  # Must be moderated first
        self.assertTrue(rev.consent_to_publish)
        self.assertEqual(rev.source, "Website Review")

    def test_submit_review_with_empty_name_defaults_to_verified_patient(self):
        """If patient leaves name blank, it safely defaults to 'Verified Patient' for anonymity."""
        payload = {
            "reviewer_name": "",
            "rating": 4,
            "message": "Very thorough diagnosis and clear exercises prescribed for home recovery.",
            "consent_to_publish": "on",
            "website": "",
        }
        response = self.client.post(reverse("public_review"), payload, follow=True)
        self.assertEqual(response.status_code, 200)

        rev = Review.objects.filter(rating=4, message__startswith="Very thorough").first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.reviewer_name, "Verified Patient")

    def test_submit_review_without_public_consent_stores_private_feedback(self):
        """Submitting review without consent_to_publish saves consent_to_publish=False."""
        payload = {
            "reviewer_name": "Private Patient",
            "rating": 5,
            "message": "Private therapy feedback for internal clinic quality improvement.",
            "website": "",
            # consent_to_publish omitted / unchecked
        }
        response = self.client.post(reverse("public_review"), payload, follow=True)
        self.assertEqual(response.status_code, 200)

        rev = Review.objects.filter(reviewer_name="Private Patient").first()
        self.assertIsNotNone(rev)
        self.assertFalse(rev.consent_to_publish)

    def test_honeypot_bot_spam_is_rejected(self):
        """Spam bots populating the hidden website field are rejected without creating a DB record."""
        payload = {
            "reviewer_name": "Spam Bot",
            "rating": 5,
            "message": "Visit my spam casino website right now for free tokens!",
            "website": "http://spambot.xyz",
        }
        initial_count = Review.objects.count()
        response = self.client.post(reverse("public_review"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), initial_count)
        self.assertContains(response, "Please review the highlighted fields below")

    def test_invalid_rating_rejected(self):
        """Rating outside 1-5 range is rejected."""
        payload = {
            "reviewer_name": "Test User",
            "rating": 10,
            "message": "Testing out-of-bounds rating validation.",
            "website": "",
        }
        initial_count = Review.objects.count()
        response = self.client.post(reverse("public_review"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), initial_count)


class GoogleReviewRedirectAndSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_is_safe_google_review_url_helper(self):
        """is_safe_google_review_url correctly validates legitimate Google URLs and rejects malicious targets."""
        # Valid Google review destinations
        self.assertTrue(is_safe_google_review_url("https://search.google.com/local/writereview?placeid=ChIJ12345"))
        self.assertTrue(is_safe_google_review_url("https://g.page/r/Cd12345/review"))
        self.assertTrue(is_safe_google_review_url("https://maps.google.com/?cid=123456"))
        self.assertTrue(is_safe_google_review_url("https://business.google.com/review"))

        # Invalid / insecure / phishing destinations
        self.assertFalse(is_safe_google_review_url("http://search.google.com/local/writereview?placeid=123"))  # Non-HTTPS
        self.assertFalse(is_safe_google_review_url("https://evil-google.com/review"))
        self.assertFalse(is_safe_google_review_url("https://search.google.com.evil.com/"))
        self.assertFalse(is_safe_google_review_url("javascript:alert(1)"))
        self.assertFalse(is_safe_google_review_url(""))
        self.assertFalse(is_safe_google_review_url(None))

    def test_google_redirect_unconfigured_safely_redirects_to_review_page(self):
        """When no Google review URL is configured, /review/google/ safely redirects to /review/ with info message."""
        with patch.dict("os.environ", {"GOOGLE_REVIEW_URL": "", "GOOGLE_PLACE_ID": ""}):
            with patch("django.conf.settings.GOOGLE_REVIEW_URL", ""):
                with patch("django.conf.settings.GOOGLE_PLACE_ID", ""):
                    response = self.client.get(reverse("review_google_redirect"), follow=True)
                    self.assertRedirects(response, reverse("public_review"))
                    self.assertContains(response, "Our direct Google Review link is currently being connected")

    def test_google_redirect_with_configured_url(self):
        """When GOOGLE_REVIEW_URL is configured with a valid destination, redirects with 302."""
        valid_url = "https://search.google.com/local/writereview?placeid=ChIJ_TEST_PLACE"
        with patch.dict("os.environ", {"GOOGLE_REVIEW_URL": valid_url}):
            with patch("django.conf.settings.GOOGLE_REVIEW_URL", valid_url):
                response = self.client.get(reverse("review_google_redirect"), follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], valid_url)

    def test_google_redirect_rejects_open_redirect_manipulation(self):
        """Passing an unauthorized target query param is rejected and redirects back to /review/."""
        response = self.client.get(
            reverse("review_google_redirect") + "?target=https://malicious-attacker.com/steal-creds",
            follow=True,
        )
        self.assertRedirects(response, reverse("public_review"))
        self.assertContains(response, "Invalid external destination")


class NavigationAndRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_footer_contains_review_us_link(self):
        """Footer Quick Links across public pages includes Review Us linking to /review/."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("public_review"))
        self.assertContains(response, "Review Us")

    def test_contact_page_contains_review_link(self):
        """Contact page includes Review Dr. Dhvani Patalia link."""
        response = self.client.get(reverse("contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("public_review"))

    def test_sitemap_includes_public_review(self):
        """Dynamic sitemap.xml includes /review/."""
        response = self.client.get(reverse("sitemap_xml"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/review/")

    def test_existing_login_and_booking_routes_unaffected(self):
        """Regression test: Existing login and booking pages load and function as expected."""
        login_res = self.client.get(reverse("login"))
        self.assertEqual(login_res.status_code, 200)

        book_res = self.client.get(reverse("public_book_appointment"))
        self.assertEqual(book_res.status_code, 200)
