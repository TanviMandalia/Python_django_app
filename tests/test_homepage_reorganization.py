import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from core.models import Hospital, Review, TreatmentCategory, Treatment


class HomepageReorganizationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.hospital, _ = Hospital.objects.get_or_create(
            name="Dr. Dhvani Patalia Physio Rehab",
            defaults={"is_active": True, "slug": "dr-dhvani-patalia-physio-rehab"},
        )
        self.category, _ = TreatmentCategory.objects.get_or_create(
            name="Orthopedic Therapy",
            slug="orthopedic-therapy",
            defaults={"order": 1, "is_active": True},
        )
        self.treatment, _ = Treatment.objects.get_or_create(
            name="Spine Alignment",
            slug="spine-alignment",
            defaults={
                "category": self.category,
                "short_description": "Targeted manual therapy for spinal mobility.",
                "order": 1,
                "is_active": True,
            },
        )

    def test_homepage_renders_concise_introductory_sections(self):
        """Homepage renders all required introductory sections without bloat."""
        res = self.client.get(reverse("home"))
        self.assertEqual(res.status_code, 200)

        # 1. Hero Section
        self.assertContains(res, "Dr. Dhvani Patalia Physio Rehab")
        self.assertContains(res, "Specialized Physiotherapy &amp; <span>Chiropractic Care</span>")
        self.assertContains(res, reverse("public_book_appointment"))
        self.assertContains(res, reverse("services"))

        # 2. Short Clinic Introduction
        self.assertContains(res, "Welcome to <span>Physio Rehab</span>")
        self.assertContains(res, "Root-Cause Focus")
        self.assertContains(res, "Hands-On Care")
        self.assertContains(res, "Lasting Mobility")
        self.assertContains(res, reverse("about"))
        self.assertContains(res, "Learn More About Us")

        # 3. Services Preview
        self.assertContains(res, "Featured <span>Clinical Services</span>")
        self.assertContains(res, "View All Services")

        # 4. Appointment Call to Action
        self.assertContains(res, "Ready to Restore Your Mobility?")
        self.assertContains(res, "tel:9409510501")

        # 5. Reviews Preview
        self.assertContains(res, "Patient <span>Feedback &amp; Google Reviews</span>")
        self.assertContains(res, reverse("public_review"))
        self.assertContains(res, "Write a Review on Google")
        self.assertContains(res, "View Clinic on Google")
        self.assertContains(res, "Read More Reviews")

        # 6. Contact Preview
        self.assertContains(res, "Get In <span>Touch</span>")
        self.assertContains(res, reverse("contact"))
        self.assertContains(res, "View Full Hours, Map &amp; Send Message")

    def test_homepage_does_not_contain_duplicated_page_content(self):
        """Homepage must not duplicate full content from About, Services, Reviews, or Contact."""
        res = self.client.get(reverse("home"))
        self.assertEqual(res.status_code, 200)

        # About Us specifics moved off homepage
        self.assertNotContains(res, "certificate_image.webp")
        self.assertNotContains(res, "Qualification Certificate")
        self.assertNotContains(res, "Documented Patient Milestones")

        # Reviews page specifics moved off homepage
        self.assertNotContains(res, "bar-track")
        self.assertNotContains(res, "reviewFilterChips")
        self.assertNotContains(res, "reviewSortSelect")

        # Contact page specifics moved off homepage (form, table, map)
        self.assertNotContains(res, "<form method=\"POST\" action=\"/contact/\">")
        self.assertNotContains(res, "Send Us a Message")

    def test_about_page_retains_full_clinic_information(self):
        """About Us page contains detailed credentials, certificate, clinic environment, and team."""
        res = self.client.get(reverse("about"))
        self.assertEqual(res.status_code, 200)

        # Full doctor credentials and certificate
        self.assertContains(res, "certificate_image.webp")
        self.assertContains(res, "Professional <span>Credentials</span>")
        self.assertContains(res, "Certified Chiropractor")
        self.assertContains(res, "Fellowship in Neuromusculoskeletal Techniques")

        # Clinic environment & facilities
        self.assertContains(res, "Our Clinic <span>Environment &amp; Facilities</span>")
        self.assertContains(res, "clinic_image_outdoor.webp")
        self.assertContains(res, "clinic_image.webp")

        # Clinical team
        self.assertContains(res, "Dedicated Clinical Team")

        # Documented patient milestones
        self.assertContains(res, "Documented <span>Patient Milestones</span>")
        self.assertContains(res, "Patient Privacy &amp; Consent Assurance")

    def test_services_page_retains_full_treatments_information(self):
        """Services page retains search, categories, and treatment cards."""
        res = self.client.get(reverse("services"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Evidence-Based <span>Treatments</span>")
        self.assertContains(res, "Treatment Categories")
        self.assertContains(res, "Spine Alignment")

    def test_reviews_page_retains_submission_form(self):
        """Review page retains interactive review form and submission logic."""
        res = self.client.get(reverse("public_review"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Share Your Clinical Experience")
        self.assertContains(res, "Prefer to Review on Google?")

    def test_contact_page_retains_full_contact_form_and_hours(self):
        """Contact page retains the message form and working hours schedule."""
        res = self.client.get(reverse("contact"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Send Us a Message")
        self.assertContains(res, "Working Hours")
