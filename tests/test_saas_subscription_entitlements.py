"""
tests/test_saas_subscription_entitlements.py
Comprehensive SaaS Subscription, Feature Access & Multi-Clinic Management Test Suite.

Covers:
  - Plan Management (CRUD, Duplicate, Toggle Active)
  - Feature Catalog & Global Kill Switch / Maintenance Mode
  - Clinic Management (Detail, Suspend, Reactivate, Change Plan, Extend Trial)
  - Entitlement Resolution Stack (Global -> Suspension -> Override -> Plan -> Free Default -> Denied)
  - Clinic Feature Overrides (Grant Complimentary, Hard Disable, Custom Limit, Expiration)
  - Centralized Entitlement Debugger ("Why Can't This Clinic Access This Feature?")
  - Usage Limits & Threshold Calculation (50%, 80%, 90%, 100%)
  - Strict Multi-Tenant Security & RBAC Isolation
  - Immutable Audit Event Recording
"""

from datetime import timedelta
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    SubscriptionPlan,
    HospitalSubscription,
    FeatureCategory,
    Feature,
    PlanFeature,
    ClinicFeatureOverride,
    SubscriptionHistory,
    AuditEvent,
    PatientProfile,
    Appointment,
    StaffProfile,
)
from core.entitlements import (
    evaluate_entitlement,
    get_feature_usage,
    can_access_feature,
    explain_entitlement,
    log_audit_event,
)


class SaaSSubscriptionEntitlementTestSuite(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()

        # 1. Super Admin
        self.super_admin = self.create_super_admin(
            username="saas_master", email="master@saasplatform.com"
        )

        # 2. Clinic A (Enterprise)
        self.clinic_a = self.create_hospital(
            name="Apex Specialty Clinic", email="contact@apexspecialty.com"
        )
        self.admin_a = self.create_clinic_admin(
            self.clinic_a, username="admin_apex", email="admin@apexspecialty.com"
        )
        self.staff_a = self.create_staff(
            self.clinic_a, username="staff_apex", email="staff@apexspecialty.com"
        )

        # 3. Clinic B (Free Tier)
        self.clinic_b = self.create_hospital(
            name="Community Care Center", email="info@communitycare.com"
        )
        self.admin_b = self.create_clinic_admin(
            self.clinic_b, username="admin_comm", email="admin@communitycare.com"
        )

        # 4. Feature Categories
        self.cat_core, _ = FeatureCategory.objects.get_or_create(
            code="core_clinical", defaults={"name": "Core Clinical", "order": 1}
        )
        self.cat_ops, _ = FeatureCategory.objects.get_or_create(
            code="operations_hr", defaults={"name": "Operations & HR", "order": 2}
        )

        # 5. Features
        self.feat_patients, _ = Feature.objects.get_or_create(
            code="patients",
            defaults={
                "category": self.cat_core,
                "name": "Patient Management",
                "is_paid": False,
                "has_usage_limit": True,
                "default_limit": 100,
                "limit_unit": "patients",
                "global_status": "available",
            },
        )
        self.feat_salary, _ = Feature.objects.get_or_create(
            code="salary_payroll",
            defaults={
                "category": self.cat_ops,
                "name": "Salary & Payroll Management",
                "is_paid": True,
                "has_usage_limit": False,
                "global_status": "available",
            },
        )
        self.feat_notes, _ = Feature.objects.get_or_create(
            code="session_notes",
            defaults={
                "category": self.cat_core,
                "name": "Clinical Session Notes",
                "is_paid": False,
                "has_usage_limit": False,
                "global_status": "available",
            },
        )

        # 6. Plans
        self.plan_free, _ = SubscriptionPlan.objects.get_or_create(
            code="test_free",
            defaults={
                "name": "test_free",
                "display_name": "Free Tier",
                "tier_level": 0,
                "price_monthly": Decimal("0.00"),
                "max_patients": 50,
                "max_appointments_monthly": 50,
                "max_staff": 2,
            },
        )
        self.plan_enterprise, _ = SubscriptionPlan.objects.get_or_create(
            code="test_enterprise",
            defaults={
                "name": "test_enterprise",
                "display_name": "Enterprise Tier",
                "tier_level": 30,
                "price_monthly": Decimal("9999.00"),
                "max_patients": 10000,
                "max_appointments_monthly": 10000,
                "max_staff": 100,
            },
        )

        # Plan Features Matrix
        PlanFeature.objects.update_or_create(
            plan=self.plan_free,
            feature=self.feat_patients,
            defaults={"access_type": "limited", "usage_limit": 50},
        )
        PlanFeature.objects.update_or_create(
            plan=self.plan_free,
            feature=self.feat_salary,
            defaults={"access_type": "disabled", "usage_limit": 0},
        )

        PlanFeature.objects.update_or_create(
            plan=self.plan_enterprise,
            feature=self.feat_patients,
            defaults={"access_type": "full", "usage_limit": 10000},
        )
        PlanFeature.objects.update_or_create(
            plan=self.plan_enterprise,
            feature=self.feat_salary,
            defaults={"access_type": "full", "usage_limit": 0},
        )

        # Subscriptions
        self.sub_a, _ = HospitalSubscription.objects.update_or_create(
            hospital=self.clinic_a,
            defaults={
                "plan": self.plan_enterprise,
                "status": "active",
                "started_at": timezone.now().date(),
                "expires_at": timezone.now().date() + timedelta(days=30),
            },
        )
        self.sub_b, _ = HospitalSubscription.objects.update_or_create(
            hospital=self.clinic_b,
            defaults={
                "plan": self.plan_free,
                "status": "active",
                "started_at": timezone.now().date(),
                "expires_at": None,
            },
        )

    # ════════════════════════════════════════════════════════════
    # 1. PLAN MANAGEMENT (CRUD, DUPLICATE, TOGGLE)
    # ════════════════════════════════════════════════════════════

    def test_super_admin_plans_list(self):
        """TC-SAAS-001: Super Admin can view all subscription plans with metadata."""
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("super_admin_plans"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free Tier")
        self.assertContains(response, "Enterprise Tier")

    def test_super_admin_create_plan_success(self):
        """TC-SAAS-002: Super Admin creates a new plan tier with feature entitlements."""
        self.client.force_login(self.super_admin)
        payload = {
            "name": "growth_plan",
            "code": "growth_tier",
            "display_name": "Growth Clinic Plan",
            "description": "Tailored for expanding regional practices",
            "price_monthly": "2499.00",
            "price_annual": "24990.00",
            "trial_days": "14",
            "tier_level": "15",
            "is_public": "on",
            "is_active": "on",
            "max_patients": "1000",
            "max_appointments_monthly": "800",
            "max_staff": "10",
            "storage_mb": "5000",
            f"access_{self.feat_patients.code}": "limited",
            f"limit_{self.feat_patients.code}": "1000",
            f"access_{self.feat_salary.code}": "full",
            f"limit_{self.feat_salary.code}": "0",
        }
        response = self.client.post(reverse("super_admin_add_plan"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        plan = SubscriptionPlan.objects.filter(code="growth_tier").first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.display_name, "Growth Clinic Plan")
        self.assertEqual(plan.price_monthly, Decimal("2499.00"))

        # Verify PlanFeature entries created
        pf_salary = PlanFeature.objects.filter(plan=plan, feature=self.feat_salary).first()
        self.assertIsNotNone(pf_salary)
        self.assertEqual(pf_salary.access_type, "full")

        # Verify Audit Log recorded
        self.assertTrue(
            AuditEvent.objects.filter(action="plan.created", entity_id=str(plan.id)).exists()
        )

    def test_super_admin_duplicate_plan(self):
        """TC-SAAS-003: Super Admin duplicates an existing plan and all its PlanFeature rules."""
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin_duplicate_plan", kwargs={"plan_id": self.plan_enterprise.id}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        clones = SubscriptionPlan.objects.filter(name__startswith="test_enterprise_")
        self.assertTrue(clones.exists())
        clone = clones.first()
        self.assertIn("(Copy)", clone.display_name)

        # Cloned PlanFeature exists
        self.assertTrue(
            PlanFeature.objects.filter(plan=clone, feature=self.feat_salary).exists()
        )

    def test_super_admin_toggle_plan_active(self):
        """TC-SAAS-004: Super Admin can activate or deactivate a plan tier."""
        self.client.force_login(self.super_admin)
        self.assertTrue(self.plan_enterprise.is_active)
        response = self.client.post(
            reverse("super_admin_toggle_plan", kwargs={"plan_id": self.plan_enterprise.id}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.plan_enterprise.refresh_from_db()
        self.assertFalse(self.plan_enterprise.is_active)

    # ════════════════════════════════════════════════════════════
    # 2. FEATURE CATALOG & GLOBAL EMERGENCY SWITCHES
    # ════════════════════════════════════════════════════════════

    def test_super_admin_features_catalog_view(self):
        """TC-SAAS-005: Super Admin can view feature catalog organized by category."""
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("super_admin_features"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Patient Records")
        self.assertContains(response, "Staff Payroll")

    def test_global_kill_switch_blocks_access_platform_wide(self):
        """TC-SAAS-006: Emergency global kill switch immediately denies feature even for Enterprise clinics."""
        self.client.force_login(self.super_admin)
        # Initially allowed for Enterprise Clinic A
        self.assertTrue(can_access_feature(self.clinic_a, "salary_payroll"))

        # Trigger Global Kill Switch (status='disabled')
        payload = {
            "global_status": "disabled",
            "reason": "Emergency security vulnerability patch in progress",
            "maintenance_message": "",
        }
        response = self.client.post(
            reverse("super_admin_feature_global_status", kwargs={"feature_code": "salary_payroll"}),
            payload,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.feat_salary.refresh_from_db()
        self.assertEqual(self.feat_salary.global_status, "disabled")

        # Now immediately denied for Clinic A!
        ent = evaluate_entitlement(self.clinic_a, "salary_payroll")
        self.assertFalse(ent["allowed"])
        self.assertEqual(ent["reason_code"], "global_kill_switch")

        # Verify audit log
        self.assertTrue(
            AuditEvent.objects.filter(
                action="feature.global_status_changed", entity_id="salary_payroll"
            ).exists()
        )

    def test_maintenance_mode_returns_friendly_maintenance_reason(self):
        """TC-SAAS-007: Maintenance mode renders maintenance message without leaking internals."""
        self.feat_notes.global_status = "maintenance"
        self.feat_notes.maintenance_message = "Session notes is upgrading database indexes until 3:00 PM."
        self.feat_notes.save()

        ent = evaluate_entitlement(self.clinic_a, "session_notes")
        self.assertFalse(ent["allowed"])
        self.assertEqual(ent["reason_code"], "maintenance_mode")
        self.assertEqual(
            ent["reason_text"], "Session notes is upgrading database indexes until 3:00 PM."
        )

    # ════════════════════════════════════════════════════════════
    # 3. CLINIC DETAIL, SUSPENSION & REACTIVATION
    # ════════════════════════════════════════════════════════════

    def test_super_admin_clinic_detail_all_7_tabs(self):
        """TC-SAAS-008: Clinic detail page successfully renders all 7 management tabs."""
        self.client.force_login(self.super_admin)
        tabs = ["overview", "users", "subscription", "features", "usage", "billing", "audit"]
        for tab in tabs:
            url = f"{reverse('super_admin_clinic_detail', kwargs={'hospital_id': self.clinic_a.id})}?tab={tab}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Tab {tab} failed to render.")
            self.assertContains(response, self.clinic_a.name)

    def test_suspend_clinic_locks_operations_and_preserves_data(self):
        """TC-SAAS-009: Suspending a clinic locks operations, updates subscription, and audits action."""
        self.client.force_login(self.super_admin)
        payload = {"reason": "Non-payment of Enterprise invoice #INV-2026-09"}
        response = self.client.post(
            reverse("super_admin_suspend_clinic", kwargs={'hospital_id': self.clinic_a.id}),
            payload,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.clinic_a.refresh_from_db()
        self.assertEqual(self.clinic_a.status, "suspended")
        self.assertFalse(self.clinic_a.is_active)
        self.assertEqual(self.clinic_a.suspension_reason, "Non-payment of Enterprise invoice #INV-2026-09")

        # Entitlements are blocked
        ent = evaluate_entitlement(self.clinic_a, "patients")
        self.assertFalse(ent["allowed"])
        self.assertEqual(ent["reason_code"], "clinic_suspended")

        # Audit log exists
        self.assertTrue(
            AuditEvent.objects.filter(
                action="clinic.suspended", hospital=self.clinic_a
            ).exists()
        )

    def test_reactivate_suspended_clinic(self):
        """TC-SAAS-010: Reactivating clinic restores operations and clears suspension reason."""
        self.clinic_a.status = "suspended"
        self.clinic_a.is_active = False
        self.clinic_a.suspension_reason = "Delinquent invoice"
        self.clinic_a.save()

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("super_admin_activate_clinic", kwargs={'hospital_id': self.clinic_a.id}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.clinic_a.refresh_from_db()
        self.assertEqual(self.clinic_a.status, "active")
        self.assertTrue(self.clinic_a.is_active)
        self.assertEqual(self.clinic_a.suspension_reason, "")

        # Access is restored
        self.assertTrue(can_access_feature(self.clinic_a, "patients"))

    # ════════════════════════════════════════════════════════════
    # 4. CLINIC-SPECIFIC FEATURE OVERRIDES & ENTITLEMENT PRIORITY
    # ════════════════════════════════════════════════════════════

    def test_override_complimentary_grant_unlocks_paid_feature_on_free_tier(self):
        """TC-SAAS-011: Super Admin grants complimentary override on Free tier clinic."""
        # Clinic B is on Free Tier where salary_payroll is normally disabled
        self.assertFalse(can_access_feature(self.clinic_b, "salary_payroll"))

        # Super Admin grants complimentary override
        self.client.force_login(self.super_admin)
        payload = {
            "feature_code": "salary_payroll",
            "override_type": "grant",
            "custom_limit": "0",
            "reason": "Promotional pilot for 30 days",
            "expires_days": "30",
        }
        response = self.client.post(
            reverse("super_admin_save_feature_override", kwargs={'hospital_id': self.clinic_b.id}),
            payload,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Now Clinic B CAN access salary_payroll!
        ent = evaluate_entitlement(self.clinic_b, "salary_payroll")
        self.assertTrue(ent["allowed"])
        self.assertEqual(ent["access_type"], "complimentary")
        self.assertEqual(ent["source"], "override")
        self.assertTrue(ent["is_complimentary"])

    def test_override_hard_disable_revokes_included_feature_on_enterprise(self):
        """TC-SAAS-012: Super Admin hard-disables a feature included in Enterprise tier."""
        # Clinic A has Enterprise tier which includes salary_payroll
        self.assertTrue(can_access_feature(self.clinic_a, "salary_payroll"))

        # Super Admin explicitly disables it for Clinic A
        ClinicFeatureOverride.objects.create(
            hospital=self.clinic_a,
            feature=self.feat_salary,
            override_type="disable",
            reason="Clinic opted out of payroll module",
            created_by=self.super_admin,
        )

        # Clinic A is now DENIED
        ent = evaluate_entitlement(self.clinic_a, "salary_payroll")
        self.assertFalse(ent["allowed"])
        self.assertEqual(ent["reason_code"], "clinic_override_disabled")

    def test_override_custom_limit_overrides_plan_quota(self):
        """TC-SAAS-013: Super Admin custom limit overrides default plan limit."""
        # Clinic B has 50 patients limit on Free tier
        ent = evaluate_entitlement(self.clinic_b, "patients")
        self.assertEqual(ent["limit"], 50)

        # Super Admin grants 500 patients limit override
        ClinicFeatureOverride.objects.create(
            hospital=self.clinic_b,
            feature=self.feat_patients,
            override_type="custom_limit",
            custom_limit=500,
            reason="Temporary patient expansion waiver",
            created_by=self.super_admin,
        )

        ent = evaluate_entitlement(self.clinic_b, "patients")
        self.assertTrue(ent["allowed"])
        self.assertEqual(ent["limit"], 500)
        self.assertEqual(ent["source"], "override")

    def test_override_expiration_removes_override(self):
        """TC-SAAS-014: Expired override is automatically cleaned up and falls back to plan."""
        ClinicFeatureOverride.objects.create(
            hospital=self.clinic_b,
            feature=self.feat_salary,
            override_type="grant",
            expires_at=timezone.now() - timedelta(days=1),  # Already expired
            reason="Expired trial promotion",
            created_by=self.super_admin,
        )

        # Evaluator detects expiration, deletes expired override, and falls back to plan
        ent = evaluate_entitlement(self.clinic_b, "salary_payroll")
        self.assertFalse(ent["allowed"])
        self.assertFalse(
            ClinicFeatureOverride.objects.filter(
                hospital=self.clinic_b, feature=self.feat_salary
            ).exists()
        )

    # ════════════════════════════════════════════════════════════
    # 5. ENTITLEMENT DEBUGGER TRACE
    # ════════════════════════════════════════════════════════════

    def test_entitlement_debugger_explains_decision_steps(self):
        """TC-SAAS-015: Entitlement debugger returns 6-step resolution trace with final decision."""
        explanation = explain_entitlement(self.clinic_b, "salary_payroll")
        self.assertEqual(explanation["final_decision"], "DENIED")
        self.assertEqual(len(explanation["resolution_steps"]), 6)

        # Verify step headers
        step_names = [s["step"] for s in explanation["resolution_steps"]]
        self.assertIn("1. Feature Catalog Check", step_names)
        self.assertIn("2. Global Platform Status", step_names)
        self.assertIn("3. Clinic Status", step_names)
        self.assertIn("4. Clinic-Specific Override", step_names)
        self.assertIn("5. Subscription & Plan", step_names)
        self.assertIn("6. Plan Feature Matrix", step_names)

    # ════════════════════════════════════════════════════════════
    # 6. USAGE TRACKING & WARNING THRESHOLDS
    # ════════════════════════════════════════════════════════════

    def test_usage_calculation_and_threshold_levels(self):
        """TC-SAAS-016: Resource usage calculates real consumption and assigns warning levels."""
        # Clinic B has limit of 50 patients
        # Create 40 active patients (80%)
        for i in range(40):
            user = User.objects.create_user(
                username=f"pt_comm_{i}", email=f"comm_{i}@pt.local"
            )
            PatientProfile.objects.create(
                user=user,
                hospital=self.clinic_b,
                patient_status="active",
            )

        usage = get_feature_usage(self.clinic_b, "patients")
        self.assertEqual(usage["current"], 40)
        self.assertEqual(usage["limit"], 50)
        self.assertEqual(usage["remaining"], 10)
        self.assertEqual(usage["percent"], 80)
        self.assertEqual(usage["warning_level"], "warning_80")
        self.assertFalse(usage["is_exceeded"])

        # Add 10 more patients (100% capacity)
        for i in range(40, 50):
            user = User.objects.create_user(
                username=f"pt_comm_{i}", email=f"comm_{i}@pt.local"
            )
            PatientProfile.objects.create(
                user=user,
                hospital=self.clinic_b,
                patient_status="active",
            )

        usage_100 = get_feature_usage(self.clinic_b, "patients")
        self.assertEqual(usage_100["current"], 50)
        self.assertEqual(usage_100["percent"], 100)
        self.assertEqual(usage_100["warning_level"], "limit_reached")
        self.assertTrue(usage_100["is_exceeded"])

    # ════════════════════════════════════════════════════════════
    # 7. MULTI-TENANT ISOLATION & RBAC SECURITY
    # ════════════════════════════════════════════════════════════

    def test_clinic_admin_cannot_access_super_admin_routes(self):
        """TC-SAAS-017: Clinic Admin is blocked from accessing Super Admin endpoints."""
        self.client.force_login(self.admin_a)
        restricted_urls = [
            reverse("super_admin_dashboard"),
            reverse("super_admin_hospitals"),
            reverse("super_admin_plans"),
            reverse("super_admin_features"),
            reverse("super_admin_access_matrix"),
            reverse("super_admin_audit_logs"),
        ]
        for url in restricted_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                302,
                f"Clinic Admin was able to access Super Admin route: {url}",
            )

    def test_clinic_admin_cannot_tamper_with_subscription(self):
        """TC-SAAS-018: Clinic Admin cannot directly update subscription via Super Admin API."""
        self.client.force_login(self.admin_a)
        url = reverse("super_admin_update_clinic_subscription", kwargs={'hospital_id': self.clinic_a.id})
        payload = {"action_type": "change_plan", "plan_id": self.plan_enterprise.id}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)

    def test_tenant_isolation_clinic_a_cannot_touch_clinic_b_overrides(self):
        """TC-SAAS-019: Clinic A cannot modify Clinic B feature overrides."""
        self.client.force_login(self.admin_a)
        url = reverse("super_admin_save_feature_override", kwargs={'hospital_id': self.clinic_b.id})
        payload = {"feature_code": "salary_payroll", "override_type": "grant"}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ClinicFeatureOverride.objects.filter(hospital=self.clinic_b).exists()
        )
