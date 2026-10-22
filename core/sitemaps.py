import os
from urllib.parse import urlparse
from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from core.models import Treatment, Blog


class CanonicalSitemapMixin:
    """
    Ensures sitemap entries use the canonical HTTPS production domain.
    Reads CANONICAL_BASE_URL from settings or environment, gracefully
    falling back to request site domain in local development.
    """
    protocol = "https"

    def get_domain(self, site=None):
        configured = (
            getattr(settings, "CANONICAL_BASE_URL", "").strip().rstrip("/")
            or os.environ.get("CANONICAL_BASE_URL", "").strip().rstrip("/")
        )
        if configured:
            parsed = urlparse(configured)
            domain = parsed.netloc or configured.replace("https://", "").replace("http://", "")
            if domain:
                return domain

        if site is not None:
            return site.domain

        return getattr(settings, "DEFAULT_DOMAIN", "physio-rehab-app.onrender.com")

    def get_protocol(self, protocol=None):
        configured = (
            getattr(settings, "CANONICAL_BASE_URL", "").strip().rstrip("/")
            or os.environ.get("CANONICAL_BASE_URL", "").strip().rstrip("/")
        )
        if configured and configured.startswith("http://"):
            return "http"
        return "https"


class StaticViewSitemap(CanonicalSitemapMixin, Sitemap):
    """
    Sitemap for core public static pages (Home, Services, About, Contact, Blog list).
    Strictly excludes login, registration, auth, dashboards, and private views.
    """
    def items(self):
        return ["home", "services", "about", "contact", "public_book_appointment", "public_review", "blog_list"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        priorities = {
            "home": 1.0,
            "services": 0.9,
            "about": 0.8,
            "contact": 0.8,
            "public_book_appointment": 0.9,
            "public_review": 0.8,
            "blog_list": 0.7,
        }
        return priorities.get(item, 0.7)

    def changefreq(self, item):
        freqs = {
            "home": "weekly",
            "services": "weekly",
            "about": "monthly",
            "contact": "monthly",
            "public_book_appointment": "weekly",
            "public_review": "monthly",
            "blog_list": "weekly",
        }
        return freqs.get(item, "monthly")


class TreatmentSitemap(CanonicalSitemapMixin, Sitemap):
    """
    Sitemap for published, active clinical treatments and rehabilitation service details.
    """
    priority = 0.8
    changefreq = "monthly"

    def items(self):
        try:
            return Treatment.objects.filter(is_active=True, slug__isnull=False).exclude(slug="").order_by("order")
        except Exception:
            return []

    def lastmod(self, item):
        return getattr(item, "updated_at", None) or getattr(item, "created_at", None)

    def location(self, item):
        return reverse("treatment_detail", kwargs={"slug": item.slug})


class BlogSitemap(CanonicalSitemapMixin, Sitemap):
    """
    Sitemap for published public healthcare and physiotherapy blog articles.
    """
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        try:
            return Blog.objects.filter(slug__isnull=False).exclude(slug="").order_by("-created_at")
        except Exception:
            return []

    def lastmod(self, item):
        return getattr(item, "created_at", None)

    def location(self, item):
        return reverse("blog_detail", kwargs={"slug": item.slug})


sitemaps = {
    "static": StaticViewSitemap,
    "treatments": TreatmentSitemap,
    "blogs": BlogSitemap,
}
