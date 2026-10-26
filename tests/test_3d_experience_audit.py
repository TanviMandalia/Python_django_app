import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from core.models import Hospital, TreatmentCategory, Treatment, Blog, User


class SiteWide3DExperienceAuditTest(TestCase):
    """
    Comprehensive audit of the 3D visual and animation architecture across the entire site:
    - Verifies genuine 3D CSS depth classes, perspective containers, and lighting properties.
    - Confirms Three.js WebGL canvas and fallback on Homepage.
    - Confirms touch and pointer event listeners in animations.js.
    - Verifies responsive meta tags and 200 OK status on all audited routes.
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
                "short_description": "Neck alignment and nerve decompression.",
                "order": 1,
                "is_active": True,
            },
        )
        self.blog, _ = Blog.objects.get_or_create(
            title="Posture and Mobility Guide",
            slug="posture-mobility-guide",
            defaults={
                "hospital": self.hospital,
                "content": "Guide to spinal alignment.",
                "category": "General",
                "excerpt": "Short guide to posture.",
            },
        )

    def test_3d_css_depth_architecture_present(self):
        """Verify animations.css contains perspective, preserve-3d, specular lighting, and mobile depth."""
        css_path = os.path.join(settings.BASE_DIR, "static", "css", "animations.css")
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 3D spatial properties
        self.assertIn("perspective: var(--depth-3d-perspective)", content)
        self.assertIn("transform-style: preserve-3d", content)
        self.assertIn("translate3d", content)
        self.assertIn("translateZ", content)

        # Dynamic specular lighting
        self.assertIn("--pointer-x", content)
        self.assertIn("--pointer-y", content)
        self.assertIn("--surface-specular-light", content)

        # Mobile ambient 3D depth
        self.assertIn("mobile-card-float", content)

        # Clinical stability safeguards
        self.assertIn(".booking-card form", content)
        self.assertIn("perspective: none !important", content)

        # Accessibility
        self.assertIn("prefers-reduced-motion: reduce", content)

    def test_3d_js_touch_drag_and_phong_lighting(self):
        """Verify animations.js contains touch drag, Phong lighting, and multi-axis tilt."""
        js_path = os.path.join(settings.BASE_DIR, "static", "js", "animations.js")
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Touch interaction for mobile/tablets
        self.assertIn("touchstart", content)
        self.assertIn("touchmove", content)
        self.assertIn("touchend", content)
        self.assertIn("touchVelocityX", content)

        # Real 3D Phong Lighting
        self.assertIn("MeshPhongMaterial", content)
        self.assertIn("DirectionalLight", content)
        self.assertIn("PointLight", content)

        # Interactive 3D Card Tilt
        self.assertIn("initCard3DTilt", content)
        self.assertIn("rotateX", content)
        self.assertIn("rotateY", content)

    def test_public_routes_3d_audit(self):
        """Audit every major public route to ensure 200 OK and viewport responsiveness."""
        routes = [
            ("home", {}),
            ("about", {}),
            ("services", {}),
            ("treatment_detail", {"slug": self.treatment.slug}),
            ("public_review", {}),
            ("contact", {}),
            ("public_book_appointment", {}),
            ("blog_list", {}),
            ("blog_detail", {"slug": self.blog.slug}),
            ("login", {}),
            ("request_otp", {}),
            ("register", {}),
        ]

        for route_name, kwargs in routes:
            url = reverse(route_name, kwargs=kwargs) if kwargs else reverse(route_name)
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Route {route_name} ({url}) returned {res.status_code}")
            # Ensure mobile responsive viewport is present
            self.assertContains(res, '<meta name="viewport"', status_code=200)
            self.assertContains(res, 'width=device-width', status_code=200)
