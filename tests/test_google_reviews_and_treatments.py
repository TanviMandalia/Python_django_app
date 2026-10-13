"""
Unit and integration tests for:
1. Dynamic Google Reviews Integration & Fallback Handling
2. Public Treatments Page & Category Filter Chips
3. Individual Treatment Landing Pages & SEO Metadata
4. Sitemap.xml & Robots.txt Dynamic Inclusion
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.core.management import call_command
from core.models import TreatmentCategory, Treatment, Review, Hospital
from core.google_reviews import (
    get_google_config,
    fetch_google_place_details,
    sync_google_reviews_to_db,
    get_public_reviews_summary,
    DEFAULT_CLINIC_NAME,
    CACHE_KEY_GOOGLE_DATA,
)


class GoogleReviewsIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_get_google_config_unconfigured(self):
        """When GOOGLE_MAPS_API_KEY is unset, config safely flags is_configured as False."""
        with patch.dict('os.environ', {'GOOGLE_MAPS_API_KEY': '', 'GOOGLE_PLACE_ID': ''}):
            with patch('django.conf.settings.GOOGLE_MAPS_API_KEY', ''):
                with patch('django.conf.settings.GOOGLE_PLACE_ID', ''):
                    config = get_google_config()
                    self.assertFalse(config['is_configured'])

    def test_fetch_google_place_details_unconfigured_graceful_fallback(self):
        """Unconfigured credentials return graceful NOT_CONFIGURED status without crashing."""
        with patch.dict('os.environ', {'GOOGLE_MAPS_API_KEY': '', 'GOOGLE_PLACE_ID': ''}):
            with patch('django.conf.settings.GOOGLE_MAPS_API_KEY', ''):
                with patch('django.conf.settings.GOOGLE_PLACE_ID', ''):
                    result = fetch_google_place_details()
                    self.assertEqual(result['status'], 'NOT_CONFIGURED')
                    self.assertIsNone(result['data'])

    @patch('core.google_reviews.requests.get')
    def test_fetch_google_place_details_success_and_caching(self, mock_get):
        """Valid Google Places API response is parsed, cached, and returned properly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "result": {
                "name": "Dr. Dhvani Patalia Physio Rehab",
                "rating": 5.0,
                "user_ratings_total": 314,
                "url": "https://maps.google.com/?cid=12345",
                "reviews": [
                    {
                        "author_name": "Ramesh Kumar",
                        "rating": 5,
                        "text": "Excellent physiotherapy care and rapid relief for back pain.",
                        "relative_time_description": "2 weeks ago",
                        "profile_photo_url": "https://lh3.googleusercontent.com/test",
                        "time": 1700000000,
                    }
                ]
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with patch.dict('os.environ', {'GOOGLE_MAPS_API_KEY': 'TEST_KEY', 'GOOGLE_PLACE_ID': 'TEST_PLACE_ID'}):
            res = fetch_google_place_details(force_refresh=True)
            self.assertEqual(res['status'], 'OK')
            self.assertIsNotNone(res['data'])
            self.assertEqual(res['data']['rating'], 5.0)
            self.assertEqual(res['data']['user_ratings_total'], 314)
            self.assertEqual(len(res['data']['reviews']), 1)
            self.assertEqual(res['data']['reviews'][0]['author_name'], "Ramesh Kumar")

            # Check cache hit on subsequent call without network request
            mock_get.reset_mock()
            cached_res = fetch_google_place_details(force_refresh=False)
            self.assertEqual(cached_res['status'], 'OK_CACHED')
            mock_get.assert_not_called()

    @patch('core.google_reviews.requests.get')
    def test_sync_google_reviews_management_command(self, mock_get):
        """Management command sync_google_reviews runs and imports new reviews safely."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "OK",
            "result": {
                "name": "Dr. Dhvani Patalia Physio Rehab",
                "rating": 5.0,
                "user_ratings_total": 20,
                "url": "https://maps.google.com/test",
                "reviews": [
                    {
                        "author_name": "Anjali Patel",
                        "rating": 5,
                        "text": "Great posture correction and friendly clinic environment.",
                        "relative_time_description": "1 month ago",
                        "profile_photo_url": "",
                        "time": 1700000001,
                    }
                ]
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with patch.dict('os.environ', {'GOOGLE_MAPS_API_KEY': 'TEST_KEY', 'GOOGLE_PLACE_ID': 'TEST_PLACE_ID'}):
            call_command('sync_google_reviews', force=True)
            review = Review.objects.filter(reviewer_name="Anjali Patel").first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 5)
            self.assertEqual(review.source, "Google Review")

    def test_public_reviews_api_endpoint(self):
        """API endpoint GET /api/reviews/ returns valid JSON with rating statistics."""
        response = self.client.get(reverse('public_reviews_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('average_rating', data)
        self.assertIn('rating_breakdown', data)
        self.assertIn('reviews', data)


class TreatmentPageAndFilterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

        # Create sample categories
        self.cat_back = TreatmentCategory.objects.create(
            name="Back Pain Treatment",
            slug="back-pain-treatment",
            order=1,
            is_active=True,
            description="Targeted back pain treatment in Jamnagar."
        )
        self.cat_knee = TreatmentCategory.objects.create(
            name="Knee Pain Treatment",
            slug="knee-pain-treatment",
            order=2,
            is_active=True,
            description="Rehabilitation for knee osteoarthritis and ligament sprains."
        )

        # Create sample treatments
        self.treatment_back = Treatment.objects.create(
            category=self.cat_back,
            name="Lumbar Spine Alignment & Disc Decompression",
            slug="lumbar-spine-alignment",
            short_description="Advanced spinal mobilization for disc bulge and lower back stiffness.",
            full_description="Detailed physical assessment and spinal adjustments to restore lumbar posture.",
            symptoms="Lower back stiffness, radiating leg pain, disc herniation",
            techniques="Chiropractic adjustments, Traction, Manual therapy",
            duration="45 Mins",
            is_active=True,
            seo_title="Lumbar Spine Alignment in Jamnagar | Dr. Dhvani Patalia",
            seo_meta_description="Certified chiropractic lumbar decompression in Jamnagar for disc bulges and back pain."
        )
        self.treatment_knee = Treatment.objects.create(
            category=self.cat_knee,
            name="Knee Osteoarthritis Rehabilitation",
            slug="knee-osteoarthritis-rehab",
            short_description="Targeted strengthening for knee joint mobility.",
            full_description="Comprehensive physical rehab program for osteoarthritis patients.",
            symptoms="Knee stiffness, joint crepitus, walking discomfort",
            techniques="Therapeutic ultrasound, Quadriceps activation, Gait retraining",
            duration="40 Mins",
            is_active=True
        )

    def test_services_page_renders_all_treatments_by_default(self):
        """GET /services/ returns 200 and renders both category chips and treatments."""
        response = self.client.get(reverse('services'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Back Pain Treatment")
        self.assertContains(response, "Knee Pain Treatment")
        self.assertContains(response, "Lumbar Spine Alignment")
        self.assertContains(response, "Knee Osteoarthritis Rehabilitation")
        self.assertEqual(response.context['displayed_count'], 2)

    def test_services_page_category_filtering(self):
        """GET /services/?category=back-pain-treatment returns only back pain treatments."""
        response = self.client.get(reverse('services'), {'category': 'back-pain-treatment'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lumbar Spine Alignment")
        self.assertNotContains(response, "Knee Osteoarthritis Rehabilitation")
        self.assertEqual(response.context['active_category_slug'], 'back-pain-treatment')
        self.assertEqual(response.context['displayed_count'], 1)

    def test_services_page_search_filtering(self):
        """GET /services/?q=Lumbar returns matching treatments and highlights query."""
        response = self.client.get(reverse('services'), {'q': 'Lumbar'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lumbar Spine Alignment")
        self.assertNotContains(response, "Knee Osteoarthritis Rehabilitation")

    def test_services_page_empty_state_when_no_match(self):
        """GET /services/?q=NonExistentTreatment renders accessible empty state."""
        response = self.client.get(reverse('services'), {'q': 'NonExistentConditionXYZ'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Treatments Found")
        self.assertContains(response, "Reset Filter")

    def test_treatment_detail_page_renders_cleanly(self):
        """GET /services/<slug>/ returns 200 with full details, symptoms, and JSON-LD."""
        url = reverse('treatment_detail', kwargs={'slug': self.treatment_back.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lumbar Spine Alignment")
        self.assertContains(response, "Disc Decompression")
        self.assertContains(response, "Lower back stiffness")
        self.assertContains(response, "Chiropractic adjustments")
        self.assertContains(response, "MedicalProcedure")
        self.assertContains(response, "BreadcrumbList")

    def test_inactive_treatment_returns_404(self):
        """Inactive treatments must not be publicly viewable."""
        self.treatment_back.is_active = False
        self.treatment_back.save()
        url = reverse('treatment_detail', kwargs={'slug': self.treatment_back.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_treatments_alias_redirects_to_services(self):
        """GET /treatments/ permanently redirects to canonical /services/ route."""
        response = self.client.get('/treatments/')
        self.assertRedirects(response, reverse('services'), status_code=301)


class WebsiteWideSEOTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_homepage_status_and_reviews_rendering(self):
        """Homepage returns 200 and displays review summary panel safely."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback &amp; Google Reviews")
        self.assertContains(response, "Write a Review on Google")
        self.assertContains(response, "View Clinic on Google")

    def test_sitemap_xml_includes_canonical_public_routes_and_treatments(self):
        """GET /sitemap.xml returns valid XML containing treatments and static pages."""
        # Ensure at least one treatment exists
        cat = TreatmentCategory.objects.first() or TreatmentCategory.objects.create(name="Sample", slug="sample")
        t = Treatment.objects.first() or Treatment.objects.create(category=cat, name="Sample T", slug="sample-t")

        response = self.client.get(reverse('sitemap_xml'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml; charset=utf-8')
        content = response.content.decode('utf-8')
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', content)
        self.assertIn('/services/', content)
        self.assertIn(f'/services/{t.slug}/', content)
        self.assertIn('/about/', content)
        self.assertIn('/contact/', content)

    def test_robots_txt_disallows_private_endpoints(self):
        """GET /robots.txt blocks private paths and points to sitemap."""
        response = self.client.get(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        content = response.content.decode('utf-8')
        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Allow: /static/", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /super-admin/", content)
        self.assertIn("Disallow: /login/", content)
        self.assertIn("Sitemap: ", content)


class WebsiteCreatorCreditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.category = TreatmentCategory.objects.create(name="Rehabilitation", slug="rehabilitation")
        self.treatment = Treatment.objects.create(
            category=self.category,
            name="Spine Therapy",
            slug="spine-therapy",
            short_description="Targeted physiotherapy for spinal health.",
            full_description="Evidence-based care for neck and back conditions.",
            is_active=True,
        )

    def test_creator_credit_present_across_public_pages(self):
        """The exact text 'Created by Tanvi Mandaliya' appears in the footer across all public pages."""
        public_urls = [
            reverse('home'),
            reverse('services'),
            reverse('about'),
            reverse('contact'),
            reverse('treatment_detail', kwargs={'slug': self.treatment.slug}),
        ]
        for url in public_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Created by Tanvi Mandaliya")
                self.assertContains(response, "creator-credit")
                # Clinic branding must remain preserved
                self.assertContains(response, "Dr. Dhvani Patalia Physio Rehab")

    def test_login_page_keeps_clean_layout(self):
        """Login page maintains clean, uncluttered layout without extraneous footer."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # Login has its own minimal layout and doesn't load the public main-footer
        self.assertNotContains(response, "main-footer")

