import xml.etree.ElementTree as ET
from django.test import TestCase, override_settings
from django.urls import reverse
from core.models import TreatmentCategory, Treatment, Blog


class GoogleSEOSitemapTests(TestCase):
    """
    Automated test suite verifying complete Google SEO Sitemap,
    Robots.txt, Canonical URL, and Google Search Console readiness.
    """

    def setUp(self):
        # Create category, treatment, and blog for test verification
        self.category = TreatmentCategory.objects.create(
            name="Spine & Joint Care",
            slug="spine-joint-care",
            is_active=True,
        )
        self.treatment = Treatment.objects.create(
            category=self.category,
            name="Lumbar Spine Alignment",
            slug="lumbar-spine-alignment",
            short_description="Targeted physiotherapy for lower back and disc herniation recovery.",
            full_description="Comprehensive spinal rehabilitation therapy.",
            is_active=True,
            order=1,
        )
        self.blog = Blog.objects.create(
            title="Evidence-Based Posture Correction for Work From Home",
            slug="posture-correction-wfh",
            excerpt="Simple ergonomic adjustments and spinal mobility exercises to alleviate back pain.",
            content="Full guide on maintaining spine health during desk work.",
        )

    def test_sitemap_xml_returns_200_and_correct_content_type(self):
        """GET /sitemap.xml must return 200 OK with application/xml content type."""
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))

    def test_sitemap_xml_follows_valid_sitemap_protocol(self):
        """sitemap.xml must parse as valid XML adhering to the Sitemap 0.9 protocol."""
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        xml_content = response.content.decode("utf-8")

        # Root must be <urlset> with sitemap 0.9 namespace
        root = ET.fromstring(xml_content)
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        # Must contain child <url> elements with <loc>
        urls = root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        self.assertTrue(len(urls) >= 5, f"Expected at least 5 public URLs, found {len(urls)}")

        for u in urls:
            loc = u.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            self.assertIsNotNone(loc, "Each <url> in sitemap must have a <loc>")
            self.assertTrue(loc.text.startswith("http://") or loc.text.startswith("https://"),
                            f"Location must be an absolute URL: {loc.text}")

    @override_settings(CANONICAL_BASE_URL="https://physio-rehab-app.onrender.com")
    def test_sitemap_includes_canonical_production_domain_and_routes(self):
        """Sitemap must include all public indexable routes using the canonical domain."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")

        expected_routes = [
            "https://physio-rehab-app.onrender.com/",
            "https://physio-rehab-app.onrender.com/services/",
            "https://physio-rehab-app.onrender.com/about/",
            "https://physio-rehab-app.onrender.com/contact/",
            "https://physio-rehab-app.onrender.com/blogs/",
            "https://physio-rehab-app.onrender.com/services/lumbar-spine-alignment/",
            "https://physio-rehab-app.onrender.com/blogs/posture-correction-wfh/",
        ]
        for expected in expected_routes:
            self.assertIn(expected, content, f"Missing expected public route in sitemap: {expected}")

    @override_settings(CANONICAL_BASE_URL="https://physio-rehab-app.onrender.com")
    def test_sitemap_strictly_excludes_private_and_authenticated_endpoints(self):
        """Sitemap must never expose login, register, dashboards, patient data, or APIs."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")

        prohibited_fragments = [
            "/login/",
            "/register/",
            "/logout/",
            "/forgot-password/",
            "/reset-password/",
            "/verify-otp/",
            "/admin/",
            "/admin-",
            "/super-admin/",
            "/staff-",
            "/client-",
            "/dashboard/",
            "/profile/",
            "/subscription/",
            "/payments/",
            "/api/",
            "/healthz",
            "/media/",
        ]
        for prohibited in prohibited_fragments:
            self.assertNotIn(f"onrender.com{prohibited}", content,
                             f"Prohibited private fragment found in sitemap: {prohibited}")

    @override_settings(CANONICAL_BASE_URL="https://physio-rehab-app.onrender.com")
    def test_robots_txt_returns_plain_text_and_declares_sitemap(self):
        """GET /robots.txt must return plain text with sitemap and private disallows."""
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        content = response.content.decode("utf-8")

        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Allow: /static/", content)
        self.assertIn("Allow: /media/", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /super-admin/", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Disallow: /login/", content)
        self.assertIn("Disallow: /register/", content)
        self.assertIn("Disallow: /subscription/", content)
        self.assertIn("Disallow: /payments/", content)
        self.assertIn("Disallow: /dashboard/", content)
        self.assertIn("Sitemap: https://physio-rehab-app.onrender.com/sitemap.xml", content)

    def test_seo_robots_tag_middleware_public_vs_private(self):
        """Public pages must NOT have noindex; private pages must have noindex."""
        # Public treatment detail must be indexable
        pub_resp = self.client.get(f"/services/{self.treatment.slug}/")
        self.assertEqual(pub_resp.status_code, 200)
        self.assertNotIn("noindex", pub_resp.headers.get("X-Robots-Tag", ""))

        # Public blog detail must be indexable
        blog_resp = self.client.get(f"/blogs/{self.blog.slug}/")
        self.assertEqual(blog_resp.status_code, 200)
        self.assertNotIn("noindex", blog_resp.headers.get("X-Robots-Tag", ""))

        # Private routes must emit noindex
        for priv in ["/login/", "/register/", "/forgot-password/"]:
            resp = self.client.get(priv)
            self.assertIn("noindex", resp.headers.get("X-Robots-Tag", ""))

    @override_settings(GOOGLE_SITE_VERIFICATION_TOKEN="google_abc123_test_token")
    def test_google_site_verification_meta_tag_when_configured(self):
        """When GOOGLE_SITE_VERIFICATION_TOKEN is set, meta tag must appear on homepage."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('<meta name="google-site-verification" content="google_abc123_test_token">', content)

    @override_settings(GOOGLE_SITE_VERIFICATION_TOKEN="")
    def test_google_site_verification_meta_tag_absent_when_unconfigured(self):
        """When GOOGLE_SITE_VERIFICATION_TOKEN is not set, meta tag must not be rendered."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertNotIn('name="google-site-verification"', content)

    @override_settings(GOOGLE_SITE_VERIFICATION_TOKEN="xyz987token")
    def test_google_verification_file_route(self):
        """GET /googlexyz987token.html returns 200 with required verification text."""
        response = self.client.get("/googlexyz987token.html")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/html"))
        self.assertEqual(response.content.decode("utf-8").strip(),
                         "google-site-verification: googlexyz987token.html")

        # Wrong token must return 404
        bad_response = self.client.get("/googlewrongtoken456.html")
        self.assertEqual(bad_response.status_code, 404)

    def test_sitemap_handles_empty_treatments_and_blogs_safely(self):
        """Sitemap generation must succeed even when treatments or blogs are empty."""
        Treatment.objects.all().delete()
        Blog.objects.all().delete()

        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', content)
        self.assertIn("/about/", content)
        self.assertIn("/contact/", content)
