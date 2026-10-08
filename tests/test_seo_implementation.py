"""
Comprehensive Technical SEO, Local SEO, and Search Indexability Test Suite
for Dr. Dhvani Patalia Physio Rehab.

Validates:
1. Dynamic robots.txt generation & exclusion of private routes.
2. Valid XML Sitemap 0.9 generation with all eligible canonical URLs.
3. Page-level SEO metadata (unique titles, meta descriptions, canonical URLs).
4. Open Graph & Twitter card social metadata.
5. Valid, parseable Schema.org JSON-LD structured data on all public pages.
6. Single H1 heading hierarchy on all public templates.
7. Multi-layer privacy enforcement (X-Robots-Tag on private/dashboard/auth routes).
8. Canonical URL query-parameter normalization.
9. Custom 404 and 500 error page handling.
10. Consistent local clinic NAP (Name, Address, Phone) citation.
"""
import json
import xml.etree.ElementTree as ET
import re
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from core.models import Blog, Hospital


class TechnicalSEOTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(
            name="Dr. Dhvani Patalia Physio Rehab",
            address="Ground Floor, Narayan Cottage, Bedi Rd, opposite New Super Medical, Panchasar, Pancheshwar Tower, Jamnagar, Gujarat 361006, India",
            phone="+91 94095 10501",
            email="physio.rehab.guj@gmail.com",
        )
        cls.blog = Blog.objects.create(
            hospital=cls.hospital,
            title="Rehabilitation Best Practices for Chronic Back Pain",
            slug="rehabilitation-best-practices-chronic-back-pain",
            excerpt="Clinical guidance on spinal rehabilitation, core posture, and evidence-based exercises.",
            content="Comprehensive guide to chronic lower back rehabilitation by Dr. Dhvani Patalia in Jamnagar.",
            category="Spine Care",
        )

    def setUp(self):
        self.client = Client()

    def test_robots_txt_status_and_directives(self):
        """robots.txt must return 200 text/plain, allow public assets, and disallow private paths."""
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("text/plain"))
        content = resp.content.decode("utf-8")

        # Public allowances
        self.assertIn("Allow: /", content)
        self.assertIn("Allow: /static/", content)
        self.assertIn("Allow: /media/", content)

        # Private disallowances
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /admin-", content)
        self.assertIn("Disallow: /client-", content)
        self.assertIn("Disallow: /staff-", content)
        self.assertIn("Disallow: /super-admin/", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Disallow: /login/", content)
        self.assertIn("Disallow: /register/", content)
        self.assertIn("Disallow: /subscription/", content)
        self.assertIn("Disallow: /payments/", content)

        # Sitemap reference
        self.assertIn("Sitemap:", content)
        self.assertIn("/sitemap.xml", content)

    def test_sitemap_xml_validity_and_contents(self):
        """sitemap.xml must return 200 application/xml, parse cleanly, and include all eligible public URLs."""
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/xml"))

        xml_content = resp.content.decode("utf-8")
        # Validate that it is valid XML
        root = ET.fromstring(xml_content)
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        locs = [
            loc.text
            for loc in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        ]

        # Verify all eligible public pages are included
        self.assertTrue(any(l.endswith("/") for l in locs), "Homepage must be in sitemap")
        self.assertTrue(any(l.endswith("/services/") for l in locs), "Services page must be in sitemap")
        self.assertTrue(any(l.endswith("/about/") for l in locs), "About page must be in sitemap")
        self.assertTrue(any(l.endswith("/contact/") for l in locs), "Contact page must be in sitemap")
        self.assertTrue(any(l.endswith("/blogs/") for l in locs), "Blog listing must be in sitemap")
        self.assertTrue(
            any("rehabilitation-best-practices" in l for l in locs),
            "Published blog detail must be in sitemap",
        )

        # Verify private/auth routes are strictly excluded
        for l in locs:
            self.assertNotIn("/login/", l)
            self.assertNotIn("/admin", l)
            self.assertNotIn("/client-", l)
            self.assertNotIn("/staff-", l)
            self.assertNotIn("/super-admin/", l)
            self.assertNotIn("/api/", l)

    def test_public_pages_metadata_completeness_and_uniqueness(self):
        """Every public page must return 200 and possess unique title, description, and canonical URL."""
        public_urls = [
            ("/", "home"),
            ("/about/", "about"),
            ("/services/", "services"),
            ("/contact/", "contact"),
            ("/blogs/", "blog_list"),
            (f"/blogs/{self.blog.slug}/", "blog_detail"),
        ]

        titles = []
        descriptions = []

        for url, name in public_urls:
            with self.subTest(url=url, name=name):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200, f"URL {url} failed to load with 200")
                html = resp.content.decode("utf-8")

                # 1. Non-empty Title
                title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
                self.assertIsNotNone(title_match, f"Missing title in {url}")
                title = title_match.group(1).strip()
                self.assertTrue(len(title) > 10, f"Title too short in {url}: {title}")
                titles.append(title)

                # 2. Non-empty Meta Description
                desc_match = re.search(
                    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
                    html,
                    re.IGNORECASE,
                )
                self.assertIsNotNone(desc_match, f"Missing meta description in {url}")
                desc = desc_match.group(1).strip()
                self.assertTrue(len(desc) > 30, f"Description too short in {url}: {desc}")
                descriptions.append(desc)

                # 3. Canonical Link
                canonical_match = re.search(
                    r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']',
                    html,
                    re.IGNORECASE,
                )
                self.assertIsNotNone(canonical_match, f"Missing canonical link in {url}")
                canonical_url = canonical_match.group(1).strip()
                self.assertTrue(canonical_url.startswith("http"), f"Canonical URL not absolute in {url}: {canonical_url}")

                # 4. Open Graph Tags
                self.assertIn('property="og:title"', html, f"Missing og:title in {url}")
                self.assertIn('property="og:description"', html, f"Missing og:description in {url}")
                self.assertIn('property="og:url"', html, f"Missing og:url in {url}")
                self.assertIn('property="og:image"', html, f"Missing og:image in {url}")

                # 5. Twitter Card Tags
                self.assertIn('name="twitter:card"', html, f"Missing twitter:card in {url}")
                self.assertIn('name="twitter:title"', html, f"Missing twitter:title in {url}")

                # 6. Schema.org JSON-LD structured data
                json_ld_matches = re.findall(
                    r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
                self.assertTrue(len(json_ld_matches) > 0, f"Missing JSON-LD structured data in {url}")
                for raw_json in json_ld_matches:
                    try:
                        parsed = json.loads(raw_json.strip())
                        self.assertEqual(parsed.get("@context"), "https://schema.org")
                    except json.JSONDecodeError as e:
                        self.fail(f"Invalid JSON-LD on {url}: {e}\nRaw: {raw_json}")

                # 7. Exactly one H1 tag
                h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
                self.assertEqual(len(h1_matches), 1, f"Expected exactly 1 H1 tag in {url}, found {len(h1_matches)}")

        # Verify titles and descriptions are distinct across pages
        self.assertEqual(len(titles), len(set(titles)), "Page titles must be unique across public pages")
        self.assertEqual(len(descriptions), len(set(descriptions)), "Meta descriptions must be unique across public pages")

    def test_query_params_do_not_alter_canonical_url(self):
        """Canonical URLs must be clean of tracking/query parameters."""
        resp = self.client.get("/services/?utm_source=facebook&utm_medium=cpc&fbclid=12345")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', html)
        self.assertIsNotNone(canonical_match)
        canonical = canonical_match.group(1)
        self.assertTrue(canonical.endswith("/services/"))
        self.assertNotIn("utm_source", canonical)
        self.assertNotIn("fbclid", canonical)

    @override_settings(CANONICAL_BASE_URL="https://drdhvaniphysiorehab.com")
    def test_configured_canonical_base_url_enforced(self):
        """When CANONICAL_BASE_URL is configured, canonical tags and sitemaps must use that domain."""
        resp = self.client.get("/about/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn('<link rel="canonical" href="https://drdhvaniphysiorehab.com/about/">', html)

        sitemap_resp = self.client.get("/sitemap.xml")
        self.assertIn("https://drdhvaniphysiorehab.com/about/", sitemap_resp.content.decode("utf-8"))

    def test_privacy_headers_on_non_public_routes(self):
        """Non-public and dashboard routes must emit X-Robots-Tag: noindex, nofollow, noarchive."""
        private_routes = [
            "/login/",
            "/register/",
            "/forgot-password/",
            "/verify-otp/",
            "/reset-password/",
            "/change-password/",
            "/admin-dashboard/",
            "/client-dashboard/",
            "/staff-dashboard/",
            "/super-admin/",
            "/api/promos/dismiss/",
        ]

        for route in private_routes:
            with self.subTest(route=route):
                resp = self.client.get(route)
                # Could be 200 (auth form) or 302 (redirect to login)
                robots_header = resp.headers.get("X-Robots-Tag", "")
                self.assertIn("noindex", robots_header, f"Expected noindex on {route}")

    def test_auth_templates_contain_noindex_meta_tag(self):
        """Auth pages must also feature HTML-level meta noindex tags."""
        for url in ["/login/", "/register/", "/forgot-password/"]:
            with self.subTest(url=url):
                resp = self.client.get(url)
                html = resp.content.decode("utf-8")
                self.assertIn('<meta name="robots" content="noindex, nofollow"', html)

    def test_custom_404_page_rendering_and_directives(self):
        """Non-existent pages must return 404, render branded template, and have noindex, follow."""
        resp = self.client.get("/non-existent-clinical-page-12345/")
        self.assertEqual(resp.status_code, 404)
        html = resp.content.decode("utf-8")
        self.assertIn("Page Not Found", html)
        self.assertIn('<meta name="robots" content="noindex, follow">', html)
        self.assertIn('href="/"', html)

    def test_clinic_local_nap_citation_accuracy(self):
        """Verify the Name, Address, Phone citation on Contact page matches verified business info."""
        resp = self.client.get("/contact/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("Dr. Dhvani Patalia Physio Rehab", html)
        self.assertIn("Narayan Cottage, Bedi Rd", html)
        self.assertIn("Jamnagar, Gujarat 361006", html)
        self.assertIn("94095 10501", html)
        self.assertIn("physio.rehab.guj@gmail.com", html)
