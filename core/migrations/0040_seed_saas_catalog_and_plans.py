from django.db import migrations
from decimal import Decimal


def seed_saas_catalog(apps, schema_editor):
    FeatureCategory = apps.get_model("core", "FeatureCategory")
    Feature = apps.get_model("core", "Feature")
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    PlanFeature = apps.get_model("core", "PlanFeature")
    Hospital = apps.get_model("core", "Hospital")
    HospitalSubscription = apps.get_model("core", "HospitalSubscription")

    # 1. Feature Categories
    categories_data = [
        ("core", "Core Clinical", "Core patient & clinic management workflows", "fas fa-stethoscope", 10),
        ("clinical", "Clinical Care & Rehab", "EMR, session documentation, and exercise protocols", "fas fa-notes-medical", 20),
        ("communication", "Communication & Alerts", "Patient messaging, email, and notification channels", "fas fa-comments", 30),
        ("financial", "Financial & Billing", "Receipts, payments, invoices, and revenue tracking", "fas fa-file-invoice-dollar", 40),
        ("reporting", "Reporting & Analytics", "Export capabilities, clinic analytics, and insights", "fas fa-chart-line", 50),
        ("marketing", "Marketing & Public Web", "Promotional banners, blogs, and public web showcase", "fas fa-bullhorn", 60),
        ("governance", "Administration & Governance", "Audit logs, compliance, and security controls", "fas fa-shield-alt", 70),
    ]

    cat_map = {}
    for code, name, desc, icon, order in categories_data:
        cat, _ = FeatureCategory.objects.get_or_create(
            code=code,
            defaults={"name": name, "description": desc, "icon": icon, "order": order},
        )
        cat_map[code] = cat

    # 2. Features Catalog
    features_data = [
        ("patients", "core", "Patient Records & Directory", "Active patient registration, health profile, and demographics", False, True, 500, "patients"),
        ("appointments", "core", "Appointment Scheduling & Slots", "Shift-based appointments, real-time booking, and slot governance", False, True, 100, "appts/month"),
        ("staff_management", "core", "Staff & Provider Management", "Physiotherapists, assistants, duty allocation, and profiles", False, True, 5, "staff"),
        ("attendance_tracking", "core", "Staff Shift & Attendance", "Morning/evening shifts clock-in, duty hours, and attendance logs", False, False, 0, ""),
        ("salary_payroll", "core", "Staff Payroll & Compensation", "Disbursements, bonus calculation, deductions, and salary slips", True, False, 0, ""),
        ("session_notes", "clinical", "Clinical Session Notes & EMR", "Consultation documentation, diagnosis, and treatment followups", False, False, 0, ""),
        ("treatment_plans", "clinical", "Treatment Plans & Rehab Exercises", "Multi-stage rehabilitation protocols and home-exercise assignments", True, False, 0, ""),
        ("patient_chat", "communication", "Real-Time Patient & Doctor Chat", "Two-way in-app secure chat between patients, doctors, and clinic admins", False, False, 0, ""),
        ("email_notifications", "communication", "Transactional Email Alerts", "Automated email confirmations for bookings, invoices, and password OTPs", False, False, 0, ""),
        ("multi_account_email", "communication", "Dedicated Multi-Portal SMTP/API", "Custom per-clinic, per-doctor, and support email mailbox governance", True, False, 0, ""),
        ("billing_invoices", "financial", "Patient Payments & Cash/UPI Invoicing", "Instant payment recording, digital receipts, and ledger reconciliation", False, False, 0, ""),
        ("basic_reports", "reporting", "Standard Excel & PDF Exports", "Export patient lists and appointment registries in Excel/PDF", False, False, 0, ""),
        ("advanced_analytics", "reporting", "Revenue & Appointment Trend Analytics", "Platform analytics, revenue breakdowns, and appointment trend graphs", True, False, 0, ""),
        ("promos_offers", "marketing", "Promotional Campaigns & Banners", "Targeted discount offers and client dashboard promotional banners", False, False, 0, ""),
        ("blog_showcase", "marketing", "Case Studies & Clinical Blog", "Educational wellness articles, case recovery notes, and before/after gallery", False, False, 0, ""),
        ("audit_logs", "governance", "Immutable Compliance Audit Trail", "System-wide activity logs, role change tracking, and security monitoring", True, False, 0, ""),
    ]

    feat_map = {}
    for code, cat_code, name, desc, is_paid, has_limit, def_limit, unit in features_data:
        feat, _ = Feature.objects.get_or_create(
            code=code,
            defaults={
                "category": cat_map[cat_code],
                "name": name,
                "description": desc,
                "is_paid": is_paid,
                "has_usage_limit": has_limit,
                "default_limit": def_limit,
                "limit_unit": unit,
                "global_status": "available",
            },
        )
        feat_map[code] = feat

    # 3. Standard Subscription Plans
    plans_data = [
        (
            "free",
            "Free Starter",
            "Essential clinic workflows for small private practitioners getting started.",
            Decimal("0.00"),
            Decimal("0.00"),
            0,
            2,
            50,
            40,
            100,
            1,
            [
                "patients", "appointments", "staff_management", "attendance_tracking",
                "session_notes", "patient_chat", "email_notifications",
                "billing_invoices", "promos_offers", "blog_showcase",
            ],
        ),
        (
            "basic",
            "Clinic Basic",
            "Standard clinic management with payroll tracking and automated reporting.",
            Decimal("1999.00"),
            Decimal("19990.00"),
            14,
            5,
            300,
            250,
            500,
            2,
            [
                "patients", "appointments", "staff_management", "attendance_tracking",
                "salary_payroll", "session_notes", "patient_chat", "email_notifications",
                "billing_invoices", "basic_reports", "promos_offers", "blog_showcase",
            ],
        ),
        (
            "professional",
            "Professional Rehab",
            "Full clinical rehabilitation suite with exercise assignments and advanced analytics.",
            Decimal("4999.00"),
            Decimal("49990.00"),
            14,
            15,
            1000,
            800,
            2000,
            3,
            [
                "patients", "appointments", "staff_management", "attendance_tracking",
                "salary_payroll", "session_notes", "treatment_plans", "patient_chat",
                "email_notifications", "billing_invoices", "basic_reports",
                "advanced_analytics", "promos_offers", "blog_showcase", "audit_logs",
            ],
        ),
        (
            "enterprise",
            "Enterprise Multi-Branch",
            "Unlimited capacity, dedicated multi-portal email, and premium governance for hospital networks.",
            Decimal("9999.00"),
            Decimal("99990.00"),
            30,
            0,  # Unlimited
            0,  # Unlimited
            0,  # Unlimited
            10000,
            4,
            [
                "patients", "appointments", "staff_management", "attendance_tracking",
                "salary_payroll", "session_notes", "treatment_plans", "patient_chat",
                "email_notifications", "multi_account_email", "billing_invoices",
                "basic_reports", "advanced_analytics", "promos_offers", "blog_showcase", "audit_logs",
            ],
        ),
    ]

    for (code, display_name, desc, price_m, price_a, trial_d,
         m_staff, m_patients, m_appts, storage, tier, included_features) in plans_data:
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name=code,
            defaults={
                "code": code,
                "display_name": display_name,
                "description": desc,
                "price_monthly": price_m,
                "price_annual": price_a,
                "trial_days": trial_d,
                "max_staff": m_staff,
                "max_patients": m_patients,
                "max_appointments_monthly": m_appts,
                "storage_mb": storage,
                "tier_level": tier,
                "is_active": True,
                "is_public": True,
            },
        )
        if not plan.display_name:
            plan.display_name = display_name
            plan.code = code
            plan.tier_level = tier
            plan.save()

        # Connect plan features
        for f_code in included_features:
            if f_code in feat_map:
                f_obj = feat_map[f_code]
                u_limit = 0
                if f_code == "patients":
                    u_limit = m_patients
                elif f_code == "appointments":
                    u_limit = m_appts
                elif f_code == "staff_management":
                    u_limit = m_staff

                PlanFeature.objects.get_or_create(
                    plan=plan,
                    feature=f_obj,
                    defaults={
                        "access_type": "full",
                        "usage_limit": u_limit,
                        "limit_period": "monthly" if f_code == "appointments" else "lifetime",
                    },
                )

    # 4. Also ensure any existing plans (like "premium" or "standard") have code and plan features
    all_plans = SubscriptionPlan.objects.all()
    for p in all_plans:
        if not p.code:
            p.code = p.name.lower()
            p.display_name = p.name.title()
            p.save()
        # Ensure all existing features are mapped if missing
        for f_code, f_obj in feat_map.items():
            PlanFeature.objects.get_or_create(
                plan=p,
                feature=f_obj,
                defaults={
                    "access_type": "full",
                    "usage_limit": 0,
                    "limit_period": "lifetime",
                },
            )

    # 5. Ensure existing hospitals have an active subscription linked to a valid plan
    pro_plan = SubscriptionPlan.objects.filter(code="professional").first() or SubscriptionPlan.objects.first()
    for h in Hospital.objects.all():
        sub = HospitalSubscription.objects.filter(hospital=h).first()
        if not sub:
            HospitalSubscription.objects.create(
                hospital=h,
                plan=pro_plan,
                status="active",
            )
        elif not sub.plan:
            sub.plan = pro_plan
            sub.status = "active"
            sub.save()


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_featurecategory_alter_subscriptionplan_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_saas_catalog, reverse_seed),
    ]
