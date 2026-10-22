import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from core.models import Hospital, TreatmentCategory, Treatment, Blog, User


class PublicAnimationsTestSuite(TestCase):
    """
    Automated verification of GSAP + Three.js animation architecture across all public pages:
    - Zero broken routes or template crashes.
    - Presence of animations.css and animations.js.
    - Vendor bundle presence (gsap.min.js, ScrollTrigger.min.js, three.min.js).
    - Three.js isolation strictly to the Homepage hero canvas with fallback.
    - Reduced motion and WebGL resilience in CSS & JS assets.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.hospital, _ = Hospital.objects.get_or_create(
            name="Dr. Dhvani Patalia Physio Rehab",
            defaults={"is_active": True, "slug": "dr-dhvani-patalia-physio-rehab"},
        )
        self.category, _ = TreatmentCategory.objects.get_or_create(
            name="Chiropractic Care",
            slug="chiropractic-care",
            defaults={"order": 1, "is_active": True},
        )
        self.treatment, _ = Treatment.objects.get_or_create(
            name="Cervical Alignment",
            slug="cervical-alignment",
            defaults={
                "category": self.category,
                "short_description": "Precise neck alignment and nerve decompression.",
                "order": 1,
                "is_active": True,
            },
        )
        self.blog, _ = Blog.objects.get_or_create(
            title="Posture and Mobility Guide",
            slug="posture-mobility-guide",
            defaults={
                "hospital": self.hospital,
                "content": "Comprehensive guide to maintaining spinal alignment.",
                "category": "General",
                "excerpt": "Short guide to posture and spine health.",
            },
        )

    def test_static_animation_assets_exist_and_non_empty(self):
        """Ensure all local vendor scripts and animation assets are locally bundled and populated."""
        static_dir = os.path.join(settings.BASE_DIR, "static")
        expected_files = [
            os.path.join(static_dir, "css", "animations.css"),
            os.path.join(static_dir, "js", "animations.js"),
            os.path.join(static_dir, "js", "vendor", "gsap.min.js"),
            os.path.join(static_dir, "js", "vendor", "ScrollTrigger.min.js"),
            os.path.join(static_dir, "js", "vendor", "three.min.js"),
        ]
        for fpath in expected_files:
            self.assertTrue(os.path.exists(fpath), f"Required file missing: {fpath}")
            self.assertGreater(os.path.getsize(fpath), 1000, f"File {fpath} is suspiciously empty or truncated")

    def test_css_contains_reduced_motion_and_fail_safe_rules(self):
        """Verify CSS contains prefers-reduced-motion media query and progressive enhancement rules."""
        css_path = os.path.join(settings.BASE_DIR, "static", "css", "animations.css")
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("prefers-reduced-motion: reduce", content)
        self.assertIn(".gsap-ready", content)
        self.assertIn(".three-hero-container", content)
        self.assertIn(".three-hero-canvas", content)
        self.assertIn(".three-hero-fallback", content)
        self.assertIn(".btn-interactive", content)

    def test_js_contains_lifecycle_guards_and_reduced_motion_handling(self):
        """Verify animations.js includes WebGL check, reduced motion detection, and canvas cleanup."""
        js_path = os.path.join(settings.BASE_DIR, "static", "js", "animations.js")
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("isReducedMotion", content)
        self.assertIn("isWebGLAvailable", content)
        self.assertIn("initThreeHero", content)
        self.assertIn("initPageEntrance", content)
        self.assertIn("initScrollReveals", content)
        self.assertIn("IntersectionObserver", content)
        self.assertIn("visibilitychange", content)
        self.assertIn("webglcontextlost", content)

    def test_homepage_includes_threejs_and_gsap(self):
        """Homepage hero renders Three.js canvas container and loads Three.js + GSAP scripts."""
        res = self.client.get(reverse("home"))
        self.assertEqual(res.status_code, 200)

        # 3D canvas container and fallback
        self.assertContains(res, 'id="threeHeroContainer"')
        self.assertContains(res, 'id="threeHeroCanvas"')
        self.assertContains(res, 'id="threeHeroFallback"')

        # CSS and JS asset links
        self.assertContains(res, "animations.css")
        self.assertContains(res, "three.min.js")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")

    def test_about_page_includes_gsap_and_no_unnecessary_threejs(self):
        """About Us page uses GSAP for editorial reveals without bloating with Three.js."""
        res = self.client.get(reverse("about"))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")

    def test_services_page_includes_gsap(self):
        """Services page uses GSAP for category chips and card reveals."""
        res = self.client.get(reverse("services"))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")

    def test_treatment_detail_page_includes_gsap(self):
        """Treatment landing page has animations.css and GSAP scripts loaded."""
        res = self.client.get(reverse("treatment_detail", kwargs={"slug": self.treatment.slug}))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")

    def test_review_page_includes_gsap(self):
        """Public review page includes animations.css and GSAP scripts."""
        res = self.client.get(reverse("public_review"))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")

    def test_contact_page_includes_gsap(self):
        """Contact page includes animations.css and GSAP scripts."""
        res = self.client.get(reverse("contact"))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")

    def test_public_book_appointment_page_includes_gsap(self):
        """Book appointment page includes animations.css and GSAP scripts without breaking forms."""
        res = self.client.get(reverse("public_book_appointment"))
        self.assertEqual(res.status_code, 200)

        self.assertContains(res, "animations.css")
        self.assertContains(res, "gsap.min.js")
        self.assertContains(res, "ScrollTrigger.min.js")
        self.assertContains(res, "animations.js")
        self.assertNotContains(res, "three.min.js")
        # Ensure form inputs and CSRF remain intact
        self.assertContains(res, 'id="publicBookingForm"')
        self.assertContains(res, 'id="id_preferred_date"')

    def test_blog_list_and_detail_include_gsap(self):
        """Blog list and article detail pages include animations.css and GSAP scripts."""
        res_list = self.client.get(reverse("blog_list"))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, "animations.css")
        self.assertContains(res_list, "gsap.min.js")
        self.assertContains(res_list, "animations.js")

        res_detail = self.client.get(reverse("blog_detail", kwargs={"slug": self.blog.slug}))
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "animations.css")
        self.assertContains(res_detail, "gsap.min.js")
        self.assertContains(res_detail, "animations.js")
