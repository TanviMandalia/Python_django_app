"""
core/entitlements.py
Centralized SaaS Feature Entitlement, Usage Limiting & Subscription Access Engine.

Rule: Role Permission + Clinic Entitlement + Usage Limit = Final Access.
Resolution Hierarchy:
  1. Global Feature Kill Switch / Maintenance Mode
  2. Clinic System Suspension / Archive
  3. Clinic-Specific Feature Override (Complimentary grant, hard disable, custom limit)
  4. Subscription Plan Feature Entitlement & Limits
  5. Feature Default (for free tier baseline)
  6. Denied by default
"""

from decimal import Decimal
from functools import wraps
from django.utils import timezone
from django.db.models import Sum, Q
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages

from core.models import (
    Hospital,
    SubscriptionPlan,
    HospitalSubscription,
    Feature,
    FeatureCategory,
    PlanFeature,
    ClinicFeatureOverride,
    SubscriptionHistory,
    AuditEvent,
    PatientProfile,
    Appointment,
    StaffProfile,
    MediaAsset,
)


# ─── 1. AUDIT LOGGING HELPER ─────────────────────────────────


def log_audit_event(action, actor=None, hospital=None, entity_type="", entity_id="", metadata=None):
    """Create an immutable platform audit event record."""
    try:
        return AuditEvent.objects.create(
            action=action,
            actor=actor if (actor and actor.is_authenticated) else None,
            hospital=hospital,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata=metadata or {},
        )
    except Exception:
        return None


# ─── 2. USAGE METRICS TRACKING ────────────────────────────────


def get_feature_usage(hospital, feature_code):
    """
    Calculate real-time resource consumption for a clinic.
    Never returns fabricated data.
    """
    if not hospital:
        return {"current": 0, "limit": 0, "remaining": 0, "percent": 0, "is_exceeded": False}

    current = 0
    now = timezone.now()

    if feature_code == "patients":
        current = PatientProfile.objects.filter(hospital=hospital, patient_status="active").count()
    elif feature_code == "appointments":
        # Monthly appointments count
        current = Appointment.objects.filter(
            hospital=hospital,
            date__year=now.year,
            date__month=now.month,
        ).exclude(status="cancelled").count()
    elif feature_code == "staff_management":
        current = StaffProfile.objects.filter(hospital=hospital, is_active=True).count()
    elif feature_code in ("storage", "media_storage"):
        total_bytes = MediaAsset.objects.filter(hospital=hospital, deleted_at__isnull=True).aggregate(
            t=Sum("bytes")
        )["t"] or 0
        current = round(total_bytes / (1024 * 1024), 2)  # In Megabytes
    elif feature_code == "blogs":
        current = hospital.blogs.count()
    elif feature_code == "promos":
        current = hospital.promos.filter(is_active=True).count()

    entitlement = evaluate_entitlement(hospital, feature_code)
    limit = entitlement.get("limit", 0)

    if limit and limit > 0:
        remaining = max(0, limit - int(current))
        percent = min(100, round((current / limit) * 100))
        is_exceeded = current >= limit
    else:
        remaining = None  # Unlimited
        percent = 0
        is_exceeded = False

    warning_level = "normal"
    if percent >= 100 or is_exceeded:
        warning_level = "limit_reached"
    elif percent >= 90:
        warning_level = "critical_90"
    elif percent >= 80:
        warning_level = "warning_80"
    elif percent >= 50:
        warning_level = "info_50"

    return {
        "feature_code": feature_code,
        "current": current,
        "limit": limit,
        "remaining": remaining,
        "percent": percent,
        "is_exceeded": is_exceeded,
        "warning_level": warning_level,
        "period": entitlement.get("limit_period", "lifetime"),
    }


# ─── 3. CENTRALIZED ENTITLEMENT EVALUATION ────────────────────


def evaluate_entitlement(hospital, feature_code):
    """
    Evaluates whether a hospital is entitled to use a given feature.
    Returns:
      {
        "allowed": bool,
        "reason_code": str,
        "reason_text": str,
        "access_type": str,      # full, limited, read_only, disabled, complimentary
        "limit": int,            # 0 = unlimited
        "limit_period": str,     # lifetime, monthly, annual
        "source": str,           # override, plan, global_disabled, default
        "is_complimentary": bool,
        "feature": Feature obj,
        "override": ClinicFeatureOverride obj or None,
      }
    """
    # 1. Fetch Feature from Catalog
    feature = Feature.objects.filter(code=feature_code, is_active=True).first()
    if not feature:
        # Unknown feature is denied
        return {
            "allowed": False,
            "reason_code": "feature_not_found",
            "reason_text": f"Feature '{feature_code}' does not exist in the platform catalog.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "catalog",
            "is_complimentary": False,
            "feature": None,
            "override": None,
        }

    # 2. Global Kill Switch & Maintenance Check
    if feature.global_status == "disabled":
        return {
            "allowed": False,
            "reason_code": "global_kill_switch",
            "reason_text": f"Feature '{feature.name}' is currently disabled platform-wide by platform administration.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "global_kill_switch",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    if feature.global_status == "maintenance":
        return {
            "allowed": False,
            "reason_code": "maintenance_mode",
            "reason_text": feature.maintenance_message or f"Feature '{feature.name}' is undergoing scheduled platform maintenance. Please try again shortly.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "maintenance",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # If no hospital provided, access cannot be granted
    if not hospital:
        return {
            "allowed": False,
            "reason_code": "no_hospital",
            "reason_text": "No clinic tenant context found.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "tenant",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # 3. Hospital Active / Suspended Check
    if not hospital.is_active or hospital.status in ("suspended", "archived"):
        reason = hospital.suspension_reason or "Clinic account is currently suspended by platform administration."
        return {
            "allowed": False,
            "reason_code": "clinic_suspended",
            "reason_text": reason,
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "clinic_suspension",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # 4. Clinic-Specific Override (Highest Priority after Global / Suspension)
    override = ClinicFeatureOverride.objects.filter(hospital=hospital, feature=feature).first()
    if override:
        # Check if temporary override has expired
        if override.is_expired:
            override.delete()
            override = None
        else:
            if override.override_type == "disable":
                return {
                    "allowed": False,
                    "reason_code": "clinic_override_disabled",
                    "reason_text": override.reason or f"Feature '{feature.name}' has been explicitly disabled for this clinic.",
                    "access_type": "disabled",
                    "limit": 0,
                    "limit_period": "lifetime",
                    "source": "override",
                    "is_complimentary": False,
                    "feature": feature,
                    "override": override,
                }
            elif override.override_type == "grant":
                return {
                    "allowed": True,
                    "reason_code": "clinic_override_granted",
                    "reason_text": f"Complimentary access granted by platform administration: {override.reason or 'Promotional access'}",
                    "access_type": "complimentary",
                    "limit": override.custom_limit or 0,
                    "limit_period": "lifetime",
                    "source": "override",
                    "is_complimentary": True,
                    "feature": feature,
                    "override": override,
                }
            elif override.override_type == "custom_limit":
                return {
                    "allowed": True,
                    "reason_code": "clinic_override_custom_limit",
                    "reason_text": f"Custom usage limit active ({override.custom_limit}): {override.reason}",
                    "access_type": "limited",
                    "limit": override.custom_limit or 0,
                    "limit_period": "lifetime",
                    "source": "override",
                    "is_complimentary": False,
                    "feature": feature,
                    "override": override,
                }

    # 5. Clinic Subscription Check
    sub = HospitalSubscription.objects.filter(hospital=hospital).select_related("plan").first()
    if not sub:
        # Check if feature is marked free by default
        if not feature.is_paid:
            return {
                "allowed": True,
                "reason_code": "free_feature_default",
                "reason_text": "Free core clinic feature.",
                "access_type": "full",
                "limit": feature.default_limit,
                "limit_period": "lifetime",
                "source": "default",
                "is_complimentary": False,
                "feature": feature,
                "override": None,
            }
        return {
            "allowed": False,
            "reason_code": "no_subscription",
            "reason_text": "No active subscription plan found for this clinic.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "subscription",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # Check subscription status
    if sub.status == "suspended":
        return {
            "allowed": False,
            "reason_code": "subscription_suspended",
            "reason_text": sub.suspension_reason or "Clinic subscription is suspended.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "subscription",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    if sub.status == "expired" or (sub.is_expired and sub.status not in ("active", "grace_period")):
        # On expired subscriptions, free features remain accessible in read-only or limited mode
        if not feature.is_paid:
            return {
                "allowed": True,
                "reason_code": "expired_free_access",
                "reason_text": "Free core features remain accessible after subscription expiration.",
                "access_type": "read_only",
                "limit": feature.default_limit,
                "limit_period": "lifetime",
                "source": "expired_fallback",
                "is_complimentary": False,
                "feature": feature,
                "override": None,
            }
        return {
            "allowed": False,
            "reason_code": "subscription_expired",
            "reason_text": "Clinic subscription has expired. Please upgrade or renew your plan to restore paid features.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "subscription",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # 6. Plan-Feature Matrix Check
    plan = sub.plan
    if not plan:
        # Fallback to free if plan unassigned
        if not feature.is_paid:
            return {
                "allowed": True,
                "reason_code": "plan_unassigned_free",
                "reason_text": "Free core feature.",
                "access_type": "full",
                "limit": feature.default_limit,
                "limit_period": "lifetime",
                "source": "default",
                "is_complimentary": False,
                "feature": feature,
                "override": None,
            }
        return {
            "allowed": False,
            "reason_code": "no_plan_assigned",
            "reason_text": "No subscription tier assigned to clinic.",
            "access_type": "disabled",
            "limit": 0,
            "limit_period": "lifetime",
            "source": "plan",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    pf = PlanFeature.objects.filter(plan=plan, feature=feature).first()
    if pf:
        if pf.access_type == "disabled":
            return {
                "allowed": False,
                "reason_code": "plan_feature_disabled",
                "reason_text": f"Feature '{feature.name}' is not included in the {plan.display_name} tier.",
                "access_type": "disabled",
                "limit": 0,
                "limit_period": pf.limit_period,
                "source": "plan",
                "is_complimentary": False,
                "feature": feature,
                "override": None,
            }
        else:
            return {
                "allowed": True,
                "reason_code": "plan_feature_allowed",
                "reason_text": f"Included in {plan.display_name} plan ({pf.get_access_type_display()}).",
                "access_type": pf.access_type,
                "limit": pf.usage_limit,
                "limit_period": pf.limit_period,
                "source": "plan",
                "is_complimentary": False,
                "feature": feature,
                "override": None,
            }

    # If not explicitly in plan matrix, check if it's a free feature
    if not feature.is_paid:
        return {
            "allowed": True,
            "reason_code": "free_feature_default",
            "reason_text": "Free core feature included for all active clinics.",
            "access_type": "full",
            "limit": feature.default_limit,
            "limit_period": "lifetime",
            "source": "default",
            "is_complimentary": False,
            "feature": feature,
            "override": None,
        }

    # Otherwise denied by default
    return {
        "allowed": False,
        "reason_code": "plan_not_included",
        "reason_text": f"Feature '{feature.name}' requires an upgrade from your current {plan.display_name} plan.",
        "access_type": "disabled",
        "limit": 0,
        "limit_period": "lifetime",
        "source": "plan",
        "is_complimentary": False,
        "feature": feature,
        "override": None,
    }


def can_access_feature(hospital, feature_code):
    """Simple boolean check for feature access."""
    ent = evaluate_entitlement(hospital, feature_code)
    return ent.get("allowed", False)


# ─── 4. SUPER ADMIN EXPLANATION / DEBUG ENGINE ────────────────


def explain_entitlement(hospital, feature_code):
    """
    Detailed diagnostic resolution trace answering:
    'Why can / can't this clinic access this feature?'
    """
    feature = Feature.objects.filter(code=feature_code).first()
    sub = HospitalSubscription.objects.filter(hospital=hospital).select_related("plan").first() if hospital else None
    override = ClinicFeatureOverride.objects.filter(hospital=hospital, feature=feature).first() if (hospital and feature) else None
    pf = PlanFeature.objects.filter(plan=sub.plan, feature=feature).first() if (sub and sub.plan and feature) else None
    ent = evaluate_entitlement(hospital, feature_code)
    usage = get_feature_usage(hospital, feature_code) if feature and feature.has_usage_limit else None

    steps = [
        {
            "step": "1. Feature Catalog Check",
            "status": "PASS" if feature else "FAIL",
            "details": f"Feature '{feature_code}' found in catalog: {feature.name}" if feature else f"Feature '{feature_code}' does not exist.",
        },
        {
            "step": "2. Global Platform Status",
            "status": "PASS" if (feature and feature.global_status == "available") else "BLOCKED",
            "details": f"Global status is '{feature.get_global_status_display()}'" if feature else "N/A",
        },
        {
            "step": "3. Clinic Status",
            "status": "PASS" if (hospital and hospital.is_active and hospital.status not in ('suspended', 'archived')) else "BLOCKED",
            "details": f"Clinic status: '{hospital.status}' (Active: {hospital.is_active})" if hospital else "No hospital provided",
        },
        {
            "step": "4. Clinic-Specific Override",
            "status": "OVERRIDE ACTIVE" if override else "NO OVERRIDE",
            "details": f"Override: {override.get_override_type_display()} (Reason: {override.reason or 'None'})" if override else "No clinic-specific override set. Falling back to plan.",
        },
        {
            "step": "5. Subscription & Plan",
            "status": "PASS" if (sub and sub.status in ('active', 'trial', 'grace_period')) else "ATTENTION",
            "details": f"Subscription status: '{sub.status}', Plan: '{sub.plan.display_name if sub.plan else 'None'}'" if sub else "No subscription found.",
        },
        {
            "step": "6. Plan Feature Matrix",
            "status": "PASS" if (pf and pf.access_type != 'disabled') else ("FREE PASS" if (feature and not feature.is_paid) else "BLOCKED"),
            "details": f"Plan matrix: access={pf.access_type}, limit={pf.usage_limit}" if pf else ("Free feature default access" if (feature and not feature.is_paid) else "Not included in current plan"),
        },
    ]

    return {
        "hospital": hospital,
        "feature": feature,
        "subscription": sub,
        "plan": sub.plan if sub else None,
        "override": override,
        "plan_feature": pf,
        "entitlement": ent,
        "usage": usage,
        "resolution_steps": steps,
        "final_decision": "ALLOWED" if ent["allowed"] else "DENIED",
        "final_reason": ent["reason_text"],
    }


# ─── 5. BACKEND ENFORCEMENT DECORATOR ─────────────────────────


def require_feature(feature_code, action="access"):
    """
    View decorator to enforce feature entitlement and usage limits.
    Usage:
        @require_feature("salary_payroll")
        def admin_salary(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from core.tenancy import resolve_hospital

            # Super admin always has platform-level bypass
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            hospital = resolve_hospital(request.user)
            if not hospital:
                messages.error(request, "❌ No clinic association found for this user account.")
                return redirect("client_dashboard")

            ent = evaluate_entitlement(hospital, feature_code)
            if not ent["allowed"]:
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({
                        "error": "feature_denied",
                        "feature": feature_code,
                        "reason": ent["reason_text"],
                    }, status=403)

                return render(
                    request,
                    "shared/feature_upgrade.html",
                    {
                        "feature_code": feature_code,
                        "feature": ent.get("feature"),
                        "entitlement": ent,
                        "hospital": hospital,
                        "subscription": getattr(hospital, "subscription", None),
                    },
                    status=403,
                )

            # If write/create action, check resource limits
            if action in ("create", "add") and request.method == "POST":
                usage = get_feature_usage(hospital, feature_code)
                if usage["is_exceeded"]:
                    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                        return JsonResponse({
                            "error": "usage_limit_reached",
                            "feature": feature_code,
                            "current": usage["current"],
                            "limit": usage["limit"],
                            "reason": f"Usage limit reached ({usage['current']}/{usage['limit']}). Please upgrade your plan.",
                        }, status=403)

                    messages.error(
                        request,
                        f"❌ Usage limit reached for {ent.get('feature').name if ent.get('feature') else feature_code} ({usage['current']}/{usage['limit']}). Upgrade your plan to increase limits."
                    )
                    return redirect(request.META.get("HTTP_REFERER") or "admin_dashboard")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
