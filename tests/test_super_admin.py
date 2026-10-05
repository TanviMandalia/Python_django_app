"""
Comprehensive Super Admin Test Suite.
Covers:
  - Super Admin Dashboard & System-wide Metrics
  - Hospital CRUD (Create, Read, Update, Delete) & Validation
  - Clinic Admin provisioning & duplicate checks
  - Subscription Plans & Clinic Subscription Management
  - Subscription Payment confirmation & rejection workflow
  - System-wide Analytics & Financial Reports
  - All Payments aggregation & filtering
  - Support Tickets inspection & replies
"""
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    ClinicAdmin,
    SubscriptionPlan,
    HospitalSubscription,
    ClinicSubscriptionPayment,
    SupportTicket,
    SupportReply,
    PaymentRecord,
)


class SuperAdminTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        self.super_admin = self.create_super_admin(
            username="super_chief", email="chief@platform.com"
        )
        self.hospital = self.create_hospital(
            name="Alpha Metro Clinic", email="alpha@clinic.com"
        )
        self.clinic_admin = self.create_clinic_admin(
            self.hospital, username="alpha_admin", email="alpha_admin@clinic.com"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="premium",
            price_monthly=Decimal("4999.00"),
            max_staff=25,
            max_patients=2000,
            features="Full clinic suite, analytics, chat, backups",
        )
        self.subscription = HospitalSubscription.objects.create(
            hospital=self.hospital,
            plan=self.plan,
            status="active",
            started_at=timezone.now().date() - timedelta(days=5),
            expires_at=timezone.now().date() + timedelta(days=25),
        )
        self.client.force_login(self.super_admin)

    # ── Dashboard & Hospital Management ──────────────────────────

    def test_super_admin_dashboard_metrics(self):
        """TC-SA-001: Super admin dashboard renders metrics and platform stats."""
        response = self.client.get(reverse("super_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Metro Clinic")

    def test_super_admin_hospitals_listing(self):
        """TC-SA-002: Super admin hospitals listing renders all registered clinics."""
        response = self.client.get(reverse("super_admin_hospitals"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Metro Clinic")

    def test_super_admin_create_hospital_success(self):
        """TC-SA-003: Super admin creates a new clinic with valid details and admin."""
        payload = {
            "name": "Beta Health Center",
            "city": "Bengaluru",
            "address": "12th Cross, Indiranagar",
            "phone": "9887766554",
            "email": "contact@betahealth.com",
            "admin_first": "Bob",
            "admin_last": "Beta",
            "admin_username": "beta_admin",
            "admin_email": "admin@betahealth.com",
            "admin_password": "BetaSecurePassword123!",
            "plan": self.plan.id,
        }
        response = self.client.post(reverse("super_admin_add_hospital"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("super_admin_hospitals"))

        # Verify hospital and clinic admin exist
        new_hospital = Hospital.objects.filter(name="Beta Health Center").first()
        self.assertIsNotNone(new_hospital)
        admin_user = User.objects.filter(username="beta_admin").first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(ClinicAdmin.objects.filter(user=admin_user, hospital=new_hospital).exists())

    def test_super_admin_create_hospital_duplicate_username_fails(self):
        """TC-SA-004: Creating hospital with already existing admin username fails."""
        payload = {
            "name": "Gamma Health Clinic",
            "city": "Chennai",
            "email": "gamma@clinic.com",
            "admin_username": "alpha_admin",  # Duplicate username
            "admin_email": "new_gamma@clinic.com",
            "admin_password": "GammaPassword123!",
        }
        response = self.client.post(reverse("super_admin_add_hospital"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already taken")
        self.assertFalse(Hospital.objects.filter(name="Gamma Health Clinic").exists())

    def test_super_admin_create_hospital_missing_fields_fails(self):
        """TC-SA-005: Creating hospital with empty required fields fails validation."""
        payload = {
            "name": "",  # Empty name
            "admin_username": "",
            "admin_email": "",
            "admin_password": "",
        }
        response = self.client.post(reverse("super_admin_add_hospital"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hospital name is required")

    def test_super_admin_edit_hospital(self):
        """TC-SA-006: Super admin updates hospital name, city, and active status."""
        payload = {
            "name": "Alpha Metro Clinic Updated",
            "city": "New Delhi",
            "address": "Connaught Place",
            "phone": "9998887776",
            "email": "updated_alpha@clinic.com",
            "is_active": "on",
            "plan": self.plan.id,
            "sub_status": "active",
        }
        response = self.client.post(
            reverse("super_admin_edit_hospital", args=[self.hospital.id]),
            payload,
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.hospital.refresh_from_db()
        self.assertEqual(self.hospital.name, "Alpha Metro Clinic Updated")
        self.assertEqual(self.hospital.city, "New Delhi")

    def test_super_admin_delete_hospital(self):
        """TC-SA-007: Super admin deletes a hospital."""
        temp_hospital = self.create_hospital(name="Deletable Clinic", email="del@clinic.com")
        response = self.client.post(
            reverse("super_admin_delete_hospital", args=[temp_hospital.id]),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Hospital.objects.filter(id=temp_hospital.id).exists())

    # ── Subscriptions & Payments Workflow ─────────────────────────

    def test_super_admin_subscriptions_view(self):
        """TC-SA-008: Super admin subscriptions page lists active and trial subscriptions."""
        response = self.client.get(reverse("super_admin_subscriptions"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Metro Clinic")
        self.assertContains(response, "premium")

    def test_super_admin_confirm_sub_payment(self):
        """TC-SA-009: Super admin confirms pending subscription payment and activates hospital subscription."""
        pending_sub_pay = ClinicSubscriptionPayment.objects.create(
            hospital=self.hospital,
            plan=self.plan,
            amount=Decimal("4999.00"),
            method="upi",
            status="pending",
            duration_months=3,
        )
        response = self.client.get(
            reverse("super_admin_confirm_sub_payment", args=[pending_sub_pay.id]),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        pending_sub_pay.refresh_from_db()
        self.assertEqual(pending_sub_pay.status, "paid")
        self.assertIsNotNone(pending_sub_pay.paid_at)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, "active")

    def test_super_admin_reject_sub_payment(self):
        """TC-SA-010: Super admin marks invalid subscription payment as failed."""
        pending_sub_pay = ClinicSubscriptionPayment.objects.create(
            hospital=self.hospital,
            plan=self.plan,
            amount=Decimal("4999.00"),
            method="cash",
            status="pending",
        )
        response = self.client.get(
            reverse("super_admin_reject_sub_payment", args=[pending_sub_pay.id]),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        pending_sub_pay.refresh_from_db()
        self.assertEqual(pending_sub_pay.status, "failed")

    def test_super_admin_manage_plans(self):
        """TC-SA-011: Super admin creates/updates subscription plan details."""
        payload = {
            "action": "save_plan",
            "plan_id": self.plan.id,
            "plan_name": "premium",
            "price_monthly": "5999.00",
            "max_staff": "30",
            "max_patients": "3000",
            "features": "Updated feature list",
        }
        response = self.client.post(reverse("super_admin_subscriptions"), payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price_monthly, Decimal("5999.00"))
        self.assertEqual(self.plan.max_staff, 30)

    # ── Platform Analytics & Financial Overview ────────────────────

    def test_super_admin_analytics_view(self):
        """TC-SA-012: Analytics computes aggregate platform metrics."""
        response = self.client.get(reverse("super_admin_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clinics Enrolled")
        self.assertContains(response, "Active Subscriptions")

    def test_super_admin_all_payments_view(self):
        """TC-SA-013: All payments overview lists patient payments with filters."""
        # Create sample patient payment
        patient = self.create_patient(self.hospital)
        PaymentRecord.objects.create(
            hospital=self.hospital,
            patient=patient,
            amount=Decimal("1500.00"),
            method="upi",
            status="paid",
            transaction_id="TXN12345678",
        )
        response = self.client.get(reverse("super_admin_all_payments"), {"status": "paid"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TXN12345678")

    # ── Support Tickets & Communication ───────────────────────────

    def test_super_admin_support_tickets_view(self):
        """TC-SA-014: Super admin support ticket listing displays tickets."""
        ticket = SupportTicket.objects.create(
            hospital=self.hospital,
            submitted_by=self.clinic_admin,
            subject="Help with SMS notifications",
            message="We need assistance configuring SMS alerts.",
            status="open",
        )
        response = self.client.get(reverse("super_admin_support"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Help with SMS notifications")

    def test_super_admin_reply_support_ticket(self):
        """TC-SA-015: Super admin submits reply to support ticket and updates status."""
        ticket = SupportTicket.objects.create(
            hospital=self.hospital,
            submitted_by=self.clinic_admin,
            subject="Need staff account increase",
            message="Please increase staff limit.",
            status="open",
        )
        payload = {
            "message": "Staff limit has been upgraded for your clinic.",
            "status": "resolved",
        }
        response = self.client.post(
            reverse("super_admin_support_reply", args=[ticket.id]),
            payload,
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "resolved")
        self.assertTrue(SupportReply.objects.filter(ticket=ticket, replier=self.super_admin).exists())
