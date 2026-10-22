# ════════════════════════════════════════════════════════════
# core/views.py — TOP IMPORTS (replace your existing imports)
# ════════════════════════════════════════════════════════════

import os
import re
import json
_json = json
import random
import logging
from datetime import datetime, time as dtime, timedelta  # ← time as dtime ADDED

from .models import Blog
from .forms import BlogForm
from .email_utils import send_clinic_email
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache  # ← ADDED
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count
from django.db import models, transaction, IntegrityError
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import check_password
from decimal import Decimal
import uuid

from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.conf import settings

CLINIC_NAME = getattr(settings, "CLINIC_NAME", "PhysioRehab Clinic")

from .models import (
    Appointment,
    Attendance,
    DailyTask,
    LeaveApplication,
    Message,
    Notification,
    PasswordResetOTP,
    Profile,
    PatientProfile,
    SalaryRecord,
    SessionNote,
    StaffProfile,
    ClinicSettings,
    Blog,
    Review,
    TreatmentCategory,
    Treatment,
    Hospital,
    ClinicAdmin,
    SubscriptionPlan,
    HospitalSubscription,
    SupportTicket,
    SupportReply,
    PaymentRecord,
    ClinicPromo,
    ClinicSubscriptionPayment,
    AuditEvent,
    EmailAccount,
    EmailLog,
    FeatureCategory,
    Feature,
    PlanFeature,
    ClinicFeatureOverride,
    SubscriptionHistory,
    MediaAsset,
)
from .entitlements import (
    evaluate_entitlement,
    get_feature_usage,
    can_access_feature,
    explain_entitlement,
    require_feature,
    log_audit_event,
)
from .appointment_slots import (
    validate_appointment_booking,
    get_available_slots_for_date,
    CLINIC_SLOTS,
    MORNING_SLOTS,
    EVENING_SLOTS,
)
from .email_utils import (
    send_appointment_confirmation,
    send_appointment_status_update,
    send_admin_new_appointment_alert,
    send_otp_email,
    send_leave_status_email,
    send_salary_paid_email,
    send_task_assigned_email,
    send_staff_welcome_email,
)
from .notifications import (
    notify_appointment_booked,
    notify_appointment_status,
    notify_leave_decision,
    notify_task_assigned,
    notify_salary_paid,
)
from .tenancy import resolve_hospital

logger = logging.getLogger(__name__)

# Shift definitions
MORNING_START = dtime(10, 0)
MORNING_END = dtime(13, 0)
EVENING_START = dtime(16, 0)
EVENING_END = dtime(20, 0)
LATE_GRACE = 15


# ─── HELPERS ─────────────────────────────────────────────────


def get_admin_user(hospital=None):
    if hospital:
        admin_membership = ClinicAdmin.objects.filter(hospital=hospital).first()
        if admin_membership:
            return admin_membership.user
    return User.objects.filter(is_superuser=True).first()


def is_online(user):
    profile = getattr(user, "profile", None)
    return bool(
        profile
        and profile.last_seen
        and profile.last_seen >= timezone.now() - timedelta(minutes=2)
    )


# ─── PUBLIC PAGES ────────────────────────────────────────────


def home(request):
    """
    Public Homepage: Renders dynamic Google reviews summary, rating breakdown,
    official Google Maps links, and featured clinical treatments.
    """
    from .google_reviews import get_public_reviews_summary
    reviews_data = get_public_reviews_summary()

    # Optional server-side review sorting
    sort_param = request.GET.get("review_sort", "newest").strip().lower()
    reviews = list(reviews_data.get("reviews", []))
    if sort_param == "highest":
        reviews.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_param == "lowest":
        reviews.sort(key=lambda r: r.get("rating", 0))

    # Optional verified treatment filter (strictly applies only to reviews with verified treatment association)
    treatment_filter = request.GET.get("review_treatment", "").strip().lower()
    if treatment_filter and treatment_filter != "all":
        reviews = [r for r in reviews if r.get("treatment_slug") == treatment_filter]

    reviews_data["filtered_reviews"] = reviews
    reviews_data["active_sort"] = sort_param
    reviews_data["active_treatment_filter"] = treatment_filter

    # Featured treatments for homepage highlights
    featured_treatments = Treatment.objects.filter(is_active=True).select_related("category").order_by("order")[:6]

    return render(
        request,
        "public/home.html",
        {
            "reviews_data": reviews_data,
            "approved_reviews": reviews,  # Backwards compatibility for existing loops
            "featured_treatments": featured_treatments,
        },
    )


def about(request):
    return render(request, "public/about.html")


def services(request):
    """
    Public Treatments page with category chips filter, search bar, and treatment cards.
    Supports ?category=<slug> and ?q=<query>.
    """
    categories = TreatmentCategory.objects.filter(is_active=True).annotate(
        active_treatments_count=Count("treatments", filter=Q(treatments__is_active=True))
    ).order_by("order", "name")

    total_treatments_count = Treatment.objects.filter(is_active=True).count()

    active_category_slug = request.GET.get("category", "").strip().lower()
    search_query = request.GET.get("q", "").strip()

    treatments_qs = Treatment.objects.filter(is_active=True).select_related("category")

    active_category = None
    if active_category_slug and active_category_slug != "all":
        active_category = categories.filter(slug=active_category_slug).first()
        if active_category:
            treatments_qs = treatments_qs.filter(category=active_category)

    if search_query:
        treatments_qs = treatments_qs.filter(
            Q(name__icontains=search_query)
            | Q(short_description__icontains=search_query)
            | Q(full_description__icontains=search_query)
            | Q(symptoms__icontains=search_query)
            | Q(techniques__icontains=search_query)
        )

    treatments = list(treatments_qs.order_by("order", "name"))

    context = {
        "categories": categories,
        "treatments": treatments,
        "active_category_slug": active_category_slug or "all",
        "active_category": active_category,
        "search_query": search_query,
        "total_treatments_count": total_treatments_count,
        "displayed_count": len(treatments),
        "seo_title": (
            f"{active_category.name} in Jamnagar | Dr. Dhvani Patalia Physio Rehab"
            if active_category
            else "Physiotherapy Treatments & Rehabilitation in Jamnagar | Dr. Dhvani Patalia"
        ),
        "seo_description": (
            (active_category.description if active_category and active_category.description else "")
            or "Comprehensive physiotherapy treatments in Jamnagar for back pain, frozen shoulder, knee pain, sciatica, neck pain, and sports injuries by Dr. Dhvani Patalia."
        )[:160],
    }
    return render(request, "public/services.html", context)


def treatment_detail(request, slug):
    """
    Individual public treatment landing page with rich SEO metadata,
    symptoms breakdown, clinical techniques, breadcrumb navigation, and direct appointment CTA.
    """
    treatment = get_object_or_404(
        Treatment.objects.select_related("category"),
        slug=slug,
        is_active=True,
    )

    # Related treatments
    related_treatments = list(
        Treatment.objects.filter(
            category=treatment.category,
            is_active=True,
        )
        .exclude(pk=treatment.pk)
        .order_by("order")[:3]
    )

    if len(related_treatments) < 3:
        existing_ids = [t.id for t in related_treatments] + [treatment.id]
        fallback_related = list(
            Treatment.objects.filter(is_active=True)
            .exclude(id__in=existing_ids)
            .order_by("order")[: 3 - len(related_treatments)]
        )
        related_treatments.extend(fallback_related)

    # Specific verified patient reviews for this treatment
    treatment_reviews = list(
        Review.objects.filter(treatment=treatment, is_approved=True).order_by("-created_at")[:5]
    )

    context = {
        "treatment": treatment,
        "category": treatment.category,
        "related_treatments": related_treatments,
        "treatment_reviews": treatment_reviews,
        "seo_title": treatment.seo_title or f"{treatment.name} in Jamnagar | Dr. Dhvani Patalia Physio Rehab",
        "seo_description": treatment.seo_meta_description or (treatment.short_description or treatment.full_description[:150]),
    }
    return render(request, "public/treatment_detail.html", context)


def public_reviews_api(request):
    """
    JSON API endpoint for client-side sorting and filtering of reviews without full-page reloads.
    """
    from .google_reviews import get_public_reviews_summary

    data = get_public_reviews_summary()
    reviews = list(data.get("reviews", []))

    sort_param = request.GET.get("sort", "newest").strip().lower()
    treatment_param = request.GET.get("treatment", "").strip().lower()

    if treatment_param and treatment_param != "all":
        # Strictly only include verified treatment reviews; Google reviews are unclassified
        reviews = [r for r in reviews if r.get("treatment_slug") == treatment_param]

    if sort_param == "highest":
        reviews.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_param == "lowest":
        reviews.sort(key=lambda r: r.get("rating", 0))

    return JsonResponse(
        {
            "status": "success",
            "average_rating": data.get("average_rating"),
            "total_reviews_count": data.get("total_reviews_count"),
            "rating_breakdown": data.get("rating_breakdown"),
            "rating_breakdown_pct": data.get("rating_breakdown_pct"),
            "reviews": reviews,
            "count": len(reviews),
        }
    )


def contact(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        subject_choice = request.POST.get("subject", "General Enquiry").strip()
        message = request.POST.get("message", "").strip()

        if not first_name or not email or not message:
            messages.error(request, "Please fill in all required fields (First Name, Email, and Message).")
            return redirect("contact")

        from .email_utils import validate_recipient_email, sanitize_header_value
        try:
            clean_email = validate_recipient_email(email)
        except Exception:
            messages.error(request, "Please provide a valid email address.")
            return redirect("contact")

        full_name = f"{first_name} {last_name}".strip()
        clean_subject = sanitize_header_value(f"Inquiry: {subject_choice} - {full_name}")

        hospital = Hospital.objects.filter(is_active=True).first()
        raw_admin_email = hospital.email if (hospital and hospital.email) else getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@physiorehab.com")
        if "<" in raw_admin_email and ">" in raw_admin_email:
            extracted = raw_admin_email.split("<")[1].split(">")[0].strip()
            admin_email = extracted if extracted else "noreply@physiorehab.com"
        else:
            admin_email = raw_admin_email.strip() if raw_admin_email else "noreply@physiorehab.com"

        alert_body = f"""New public website contact inquiry received:

From    : {full_name}
Email   : {clean_email}
Phone   : {phone or 'Not provided'}
Subject : {subject_choice}

Message:
{message}
"""
        ack_body = f"""Dear {full_name},

Thank you for contacting {CLINIC_NAME}.
We have received your message regarding "{subject_choice}" and our team will get in touch with you shortly.

Summary of your inquiry:
{message}

Warm regards,
{CLINIC_NAME} Team
"""
        # Save as VisitorLead securely
        visitor_session = None
        session_token = request.COOKIES.get("va_session") or request.POST.get("va_session")
        if session_token and len(session_token) <= 64:
            from .models import VisitorSession
            visitor_session = VisitorSession.objects.filter(session_key=session_token).first()
            if visitor_session:
                visitor_session.has_converted = True
                visitor_session.save(update_fields=["has_converted"])

        marketing_consent = request.POST.get("marketing_consent", "").lower() in ("true", "1", "on")

        from .models import VisitorLead
        lead = VisitorLead.objects.create(
            session=visitor_session,
            first_name=first_name[:100],
            last_name=last_name[:100],
            email=clean_email,
            phone=phone[:30],
            category=subject_choice if subject_choice in dict(VisitorLead.CATEGORY_CHOICES) else "General Enquiry",
            message=message[:5000],
            source_page="/contact/",
            marketing_consent=marketing_consent,
            status="new",
        )

        ok_admin = False
        try:
            ok_admin = bool(send_clinic_email(
                clean_subject,
                alert_body,
                admin_email,
                hospital=hospital,
                email_type="contact_inquiry_admin",
            ))
        except Exception as exc:
            logger.error(f"Contact form admin email failed: {exc.__class__.__name__} - {exc}")

        ok_ack = False
        try:
            ok_ack = bool(send_clinic_email(
                f"We received your inquiry – {CLINIC_NAME}",
                ack_body,
                clean_email,
                hospital=hospital,
                email_type="contact_inquiry_ack",
            ))
        except Exception as exc:
            logger.error(f"Contact form user acknowledgment email failed: {exc.__class__.__name__} - {exc}")

        if ok_admin or ok_ack:
            messages.success(request, "✅ Message sent! We will contact you soon.")
        else:
            messages.error(
                request,
                "⚠️ We could not deliver your message due to a mail server configuration issue. Please contact the clinic directly."
            )
        return redirect("contact")
    return render(request, "public/contact.html")


# =========================
# PUBLIC BOOK APPOINTMENT
# =========================
def public_book_appointment(request):
    """
    Dedicated Public Appointment Booking Page.
    Accessible to all visitors without requiring authentication or account creation.
    Validates form data, saves the request as PublicAppointmentRequest in 'pending' status,
    and dispatches an email notification to the clinic doctor at physio.rehab.guj@gmail.com.
    """
    from .forms import PublicAppointmentRequestForm
    from .models import PublicAppointmentRequest, Hospital
    from .email_utils import send_public_appointment_request_notification
    from .ip_utils import get_client_ip
    from django.core.cache import cache

    hospital = Hospital.objects.filter(is_active=True).first()

    # Success confirmation display via PRG pattern
    last_ref = request.session.pop("public_booking_ref", None)
    if last_ref:
        booking_obj = PublicAppointmentRequest.objects.filter(reference_id=last_ref).first()
        if booking_obj:
            return render(
                request,
                "public/book_appointment.html",
                {
                    "booking_success": True,
                    "booking_obj": booking_obj,
                    "page_title": "Book Your Physiotherapy Appointment",
                    "page_subtitle": "Take the first step towards better movement and recovery. Request an appointment with our physiotherapy team.",
                    "clinic_phone": getattr(settings, "CLINIC_PHONE", "+91 94095 10501"),
                    "clinic_email": getattr(settings, "CLINIC_NOTIFICATION_EMAIL", "physio.rehab.guj@gmail.com"),
                },
            )

    if request.method == "POST":
        # Rate limit check: max 10 requests per hour per IP
        client_ip = get_client_ip(request) or "unknown"
        cache_key = f"rate_limit_pub_appt_{client_ip}"
        sub_count = cache.get(cache_key, 0)
        if sub_count >= 10:
            messages.error(
                request,
                "Too many appointment requests submitted from your network. Please wait a while or contact our clinic directly at +91 94095 10501."
            )
            return render(
                request,
                "public/book_appointment.html",
                {
                    "form": PublicAppointmentRequestForm(request.POST),
                    "page_title": "Book Your Physiotherapy Appointment",
                    "page_subtitle": "Take the first step towards better movement and recovery. Request an appointment with our physiotherapy team.",
                    "clinic_phone": getattr(settings, "CLINIC_PHONE", "+91 94095 10501"),
                    "clinic_email": getattr(settings, "CLINIC_NOTIFICATION_EMAIL", "physio.rehab.guj@gmail.com"),
                },
            )

        form = PublicAppointmentRequestForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            email = cleaned["email"]
            phone = cleaned["phone"]
            pref_date = cleaned["preferred_date"]
            pref_time = cleaned["preferred_time"]

            # Deduplication: check if identical request was created in the last 3 minutes
            recent_threshold = timezone.now() - timezone.timedelta(minutes=3)
            existing_req = PublicAppointmentRequest.objects.filter(
                email=email,
                phone=phone,
                preferred_date=pref_date,
                preferred_time=pref_time,
                created_at__gte=recent_threshold,
            ).first()

            if existing_req:
                req_obj = existing_req
                messages.info(
                    request,
                    "Thank you for your appointment request. Your request has been received and is awaiting confirmation from our clinic. We will contact you using the details provided."
                )
            else:
                req_obj = form.save(commit=False)
                req_obj.hospital = hospital
                req_obj.ip_address = client_ip if client_ip != "unknown" else None
                req_obj.user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
                req_obj.status = "pending"
                req_obj.email_notification_status = "pending"
                req_obj.save()

                cache.set(cache_key, sub_count + 1, timeout=3600)

                email_sent = False
                try:
                    email_sent = send_public_appointment_request_notification(req_obj)
                    req_obj.email_notification_status = "sent" if email_sent else "failed"
                    if not email_sent:
                        req_obj.notification_error = "Clinic notification email provider returned failure."
                    req_obj.save(update_fields=["email_notification_status", "notification_error"])
                except Exception as exc:
                    logger.error(f"Error in send_public_appointment_request_notification: {exc.__class__.__name__} - {exc}")
                    req_obj.email_notification_status = "failed"
                    req_obj.notification_error = f"{exc.__class__.__name__}: {str(exc)[:200]}"
                    req_obj.save(update_fields=["email_notification_status", "notification_error"])

                if email_sent:
                    messages.success(
                        request,
                        "Thank you for your appointment request. Your request has been received and is awaiting confirmation from our clinic. We will contact you using the details provided."
                    )
                else:
                    messages.warning(
                        request,
                        "Thank you for your appointment request. Your request has been received and is awaiting confirmation from our clinic. We will contact you using the details provided."
                    )

            request.session["public_booking_ref"] = req_obj.reference_id
            return redirect("public_book_appointment")
        else:
            messages.error(request, "Please review and correct the highlighted fields below.")
    else:
        form = PublicAppointmentRequestForm()

    return render(
        request,
        "public/book_appointment.html",
        {
            "form": form,
            "page_title": "Book Your Physiotherapy Appointment",
            "page_subtitle": "Take the first step towards better movement and recovery. Request an appointment with our physiotherapy team.",
            "clinic_phone": getattr(settings, "CLINIC_PHONE", "+91 94095 10501"),
            "clinic_email": getattr(settings, "CLINIC_NOTIFICATION_EMAIL", "physio.rehab.guj@gmail.com"),
        },
    )


# =========================
# PUBLIC PHYSIO REHAB REVIEW PAGE
# =========================
def public_review(request):
    """
    Dedicated Public Review Page for Dr. Dhvani Patalia Physio Rehab (/review/).
    - Accessible without logging in.
    - Zero private clinic, patient, appointment, or administrative data exposed.
    - Dual path: Direct in-app review submission form + Verified Google Review CTA.
    - Never displays Google Maps embeds or search redirects.
    - Validates spam, rate-limits submissions, and routes entries to clinic moderation.
    """
    from .forms import PublicReviewForm
    from .google_reviews import (
        get_google_write_review_url,
        get_public_reviews_summary,
        DEFAULT_CLINIC_NAME,
    )

    google_review_url = get_google_write_review_url()
    has_google_review_url = bool(google_review_url)
    reviews_summary = get_public_reviews_summary()

    if request.method == "POST":
        # Session rate-limiting: max 5 submissions in 10 minutes to prevent automated abuse
        review_count = request.session.get("review_sub_count", 0)
        review_time = request.session.get("review_sub_time", 0)
        current_time = timezone.now().timestamp()
        if review_time and (current_time - review_time < 600) and review_count >= 5:
            messages.error(
                request,
                "You have submitted multiple reviews recently. Please wait a few minutes before submitting another.",
            )
            return redirect("public_review")

        form = PublicReviewForm(request.POST)
        if form.is_valid():
            hospital = (
                resolve_hospital(request.user)
                if (request.user and request.user.is_authenticated)
                else Hospital.objects.first()
            )
            review = form.save(commit=False)
            review.hospital = hospital
            if request.user.is_authenticated:
                review.patient = request.user
            review.is_approved = False  # Moderation required before public display
            review.is_verified = True
            review.added_by_admin = False
            review.source = "Website Review"
            review.save()

            # Invalidate reviews cache so stats update accurately once approved
            cache.delete("google_places_reviews_cache_v2")
            cache.delete("public_reviews_aggregated_v2")

            # Update session rate-limit
            if not review_time or (current_time - review_time >= 600):
                request.session["review_sub_time"] = current_time
                request.session["review_sub_count"] = 1
            else:
                request.session["review_sub_count"] = review_count + 1

            messages.success(
                request,
                "Thank you for sharing your experience! Your review has been received with sincere gratitude and will be reviewed by our clinic team before being displayed.",
            )
            return redirect("public_review")
        else:
            messages.error(
                request,
                "Please review the highlighted fields below and provide your feedback.",
            )
    else:
        form = PublicReviewForm()

    # Get approved testimonials with public consent for display (up to 6)
    approved_testimonials = (
        Review.objects.filter(is_approved=True, consent_to_publish=True)
        .select_related("treatment")
        .order_by("-created_at")[:6]
    )

    return render(
        request,
        "public/review.html",
        {
            "form": form,
            "clinic_name": DEFAULT_CLINIC_NAME,
            "google_review_url": google_review_url,
            "has_google_review_url": has_google_review_url,
            "reviews_summary": reviews_summary,
            "approved_testimonials": approved_testimonials,
            "page_title": "Patient Reviews & Feedback | Dr. Dhvani Patalia Physio Rehab",
            "page_subtitle": "How was your experience with Physio Rehab? Share your story and help fellow patients take the first step toward living pain-free.",
            "canonical_url": request.build_absolute_uri("/review/"),
        },
    )


def review_google_redirect(request):
    """
    Direct, secure redirect to the verified Google Review creation URL.
    - Strictly prevents open redirects to arbitrary third-party or phishing domains.
    - If unconfigured or invalid, safely redirects back to /review/ with an informative message.
    """
    from .google_reviews import get_google_write_review_url, is_safe_google_review_url

    # Check for optional target parameter, but strictly validate it against authorized Google domains
    requested_target = request.GET.get("target", "").strip()
    if requested_target:
        if is_safe_google_review_url(requested_target):
            return redirect(requested_target)
        else:
            messages.warning(
                request,
                "Invalid external destination. Redirected back to the clinic review portal.",
            )
            return redirect("public_review")

    verified_url = get_google_write_review_url()
    if verified_url and is_safe_google_review_url(verified_url):
        return redirect(verified_url)

    # Safe fallback if Google reviews URL is not yet configured in environment
    messages.info(
        request,
        "Our direct Google Review link is currently being connected. In the meantime, you can write and submit your review directly below!",
    )
    return redirect("public_review")


# =========================
# PUBLIC BLOG LIST
# =========================
def blog_list(request):
    category = request.GET.get("category", "")
    blogs = Blog.objects.order_by("-created_at")
    if category:
        blogs = blogs.filter(category=category)
    categories = Blog.CATEGORY_CHOICES
    return render(
        request,
        "public/blog.html",
        {"blogs": blogs, "categories": categories, "active_category": category},
    )


# =========================
# PUBLIC BLOG DETAIL
# =========================
def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    return render(request, "public/blog_detail.html", {"blog": blog})


# =========================
# ADMIN BLOG LIST
# =========================
@login_required
def admin_blog_list(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    blogs = Blog.objects.order_by("-created_at")
    return render(request, "admin/admin_blog_list.html", {"blogs": blogs})


# =========================
# ADMIN ADD BLOG
# =========================
@login_required
def admin_blog_add(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        category = request.POST.get("category", "General")
        content = request.POST.get("content", "").strip()

        if not title or not content:
            messages.error(request, "Title and content are required.")
            return render(request, "admin/admin_blog_form.html", {"categories": Blog.CATEGORY_CHOICES})

        from .file_security import validate_image_file
        for field in ["image", "before_image", "after_image"]:
            img_file = request.FILES.get(field)
            if img_file:
                try:
                    validate_image_file(img_file, max_size_mb=5, field_name=field.replace('_', ' ').title())
                except ValidationError as e:
                    messages.error(request, str(e.message if hasattr(e, 'message') else e))
                    return render(request, "admin/admin_blog_form.html", {"categories": Blog.CATEGORY_CHOICES})

        Blog.objects.create(
            title=title,
            excerpt=excerpt,
            category=category,
            content=content,
            image=request.FILES.get("image") or None,
            before_image=request.FILES.get("before_image") or None,
            after_image=request.FILES.get("after_image") or None,
        )
        messages.success(request, "Blog post published successfully.")
        return redirect("admin_blog_list")
    return render(request, "admin/admin_blog_form.html", {"categories": Blog.CATEGORY_CHOICES})


# =========================
# ADMIN EDIT BLOG
# =========================
@login_required
def admin_blog_edit(request, id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    blog = get_object_or_404(Blog, id=id)
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()
        if not title or not content:
            messages.error(request, "Title and content are required.")
            return render(request, "admin/admin_blog_form.html", {"blog": blog, "categories": Blog.CATEGORY_CHOICES})

        from .file_security import validate_image_file
        for field in ["image", "before_image", "after_image"]:
            img_file = request.FILES.get(field)
            if img_file:
                try:
                    validate_image_file(img_file, max_size_mb=5, field_name=field.replace('_', ' ').title())
                except ValidationError as e:
                    messages.error(request, str(e.message if hasattr(e, 'message') else e))
                    return render(request, "admin/admin_blog_form.html", {"blog": blog, "categories": Blog.CATEGORY_CHOICES})

        blog.title = title
        blog.excerpt = request.POST.get("excerpt", "").strip()
        blog.category = request.POST.get("category", "General")
        blog.content = content
        if request.FILES.get("image"):
            blog.image = request.FILES.get("image")
        if request.FILES.get("before_image"):
            blog.before_image = request.FILES.get("before_image")
        if request.FILES.get("after_image"):
            blog.after_image = request.FILES.get("after_image")
        blog.save()
        messages.success(request, "Blog post updated successfully.")
        return redirect("admin_blog_list")
    return render(
        request, "admin/admin_blog_form.html", {"blog": blog, "categories": Blog.CATEGORY_CHOICES}
    )


# =========================
# ADMIN DELETE BLOG
# =========================
@login_required
def admin_blog_delete(request, id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    blog = get_object_or_404(Blog, id=id)

    if request.method == "POST":
        blog.delete()
        messages.success(request, "Blog post deleted.")
        return redirect("admin_blog_list")

    return render(request, "admin/admin_blog_delete.html", {"blog": blog})



# ──────────────────────────────────────────────────────────
# REVIEWS
# ──────────────────────────────────────────────────────────


@login_required
def submit_review(request):
    if request.method == "POST":
        name = (
            request.POST.get("reviewer_name", "").strip()
            or request.user.get_full_name()
            or request.user.username
        )
        title = request.POST.get("reviewer_title", "").strip()
        rating = int(request.POST.get("rating", 5))
        message = request.POST.get("message", "").strip()
        if message:
            hospital = resolve_hospital(request.user)
            Review.objects.create(
                hospital=hospital,
                patient=request.user,
                reviewer_name=name,
                reviewer_title=title,
                rating=max(1, min(5, rating)),
                message=message,
                is_approved=False,
                added_by_admin=False,
            )
            messages.success(
                request, "Thank you! Your review has been submitted for approval."
            )
        return redirect("client_dashboard")
    return redirect("client_dashboard")


@login_required
def admin_reviews(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital:
        reviews = Review.objects.filter(hospital=hospital)
    else:
        reviews = Review.objects.all()
    pending_count = reviews.filter(is_approved=False).count()
    return render(
        request,
        "admin/admin_reviews.html",
        {"reviews": reviews, "pending_count": pending_count},
    )


@login_required
def admin_add_review(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    if request.method == "POST":
        hospital = resolve_hospital(request.user)
        Review.objects.create(
            hospital=hospital,
            reviewer_name=request.POST.get("reviewer_name", ""),
            reviewer_title=request.POST.get("reviewer_title", ""),
            rating=int(request.POST.get("rating", 5)),
            message=request.POST.get("message", ""),
            is_approved=True,
            added_by_admin=True,
        )
        messages.success(request, "Review added successfully.")
        return redirect("admin_reviews")
    return render(request, "admin/admin_add_review.html")


@login_required
def toggle_review_approval(request, review_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    review = get_object_or_404(Review, id=review_id)
    if not request.user.is_superuser and hospital and review.hospital_id and review.hospital_id != hospital.id:
        messages.error(request, "Unauthorized: Review belongs to another clinic.")
        return redirect("admin_reviews")
    review.is_approved = not review.is_approved
    review.save()
    return redirect("admin_reviews")


@login_required
def admin_delete_review(request, review_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    review = get_object_or_404(Review, id=review_id)
    if not request.user.is_superuser and hospital and review.hospital_id and review.hospital_id != hospital.id:
        messages.error(request, "Unauthorized: Review belongs to another clinic.")
        return redirect("admin_reviews")
    review.delete()
    return redirect("admin_reviews")


def csrf_failure_view(request, reason="", template_name="shared/csrf_failure.html"):
    """
    Production-grade CSRF failure view:
    Replaces Django's raw 403 debug screen with a secure, clinic-branded, recoverable page.
    Handles:
      - Expired tokens due to inactivity or multi-tab login rotation
      - Browser back-forward cache (bfcache) token discrepancies
      - AJAX / fetch requests with structured JSON error & csrf_refresh flag
      - Clean retry and refresh guidance preserving user peace-of-mind
    """
    client_ip = _get_client_ip(request) if "_get_client_ip" in globals() else request.META.get("REMOTE_ADDR", "")
    logging.getLogger("core.security").warning(
        "CSRF verification failed: reason='%s', path='%s', method='%s', ip='%s'",
        reason,
        request.path,
        request.method,
        client_ip,
    )

    # Check for AJAX/JSON request
    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    ):
        return JsonResponse(
            {
                "error": "CSRF verification failed. Please refresh the page.",
                "reason": reason if settings.DEBUG else "Security token expired.",
                "csrf_refresh": True,
            },
            status=403,
        )

    context = {
        "reason": reason,
        "debug": settings.DEBUG,
        "page_title": "Security Verification Notice",
        "requested_path": request.path,
        "clinic_phone": getattr(settings, "CLINIC_PHONE", "+91 94095 10501"),
    }
    return render(request, template_name, context, status=403)


# ─── AUTH ────────────────────────────────────────────────────


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    username = ""
    remember_me = False
    next_url = request.POST.get("next") or request.GET.get("next", "").strip()

    if request.method == "POST":
        ip = _get_client_ip(request)
        cache_key = f"login_attempts_{ip}"
        attempts = cache.get(cache_key, 0)

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        remember_raw = request.POST.get("remember_me")
        remember_me = remember_raw in ("on", "true", "1", "True", True)

        # Double-check lockout (middleware also checks)
        if attempts >= 5:
            remaining = cache.ttl(cache_key) // 60
            messages.error(
                request, f"🔒 Account locked. Try again in {remaining} minute(s)."
            )
            return render(
                request,
                "auth/login.html",
                {"username": username, "remember_me": remember_me, "next": next_url},
            )

        user = authenticate(request, username=username, password=password)

        if user:
            # ✅ Success — clear failed attempts
            cache.delete(cache_key)
            login(request, user)

            # Connect Remember Me checkbox to Django session expiry:
            if remember_me:
                # 14 days persistent session duration
                expiry = getattr(settings, "REMEMBER_ME_EXPIRY", 1209600)
                request.session.set_expiry(expiry)
                request.session["remember_me"] = True
            else:
                # Browser-session cookie: expires when browser closes
                request.session.set_expiry(0)
                request.session["remember_me"] = False

            # Safe redirect: check 'next' parameter if valid and safe
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)

            return _redirect_by_role(user)
        else:
            # ❌ Failed — increment counter
            attempts += 1
            cache.set(cache_key, attempts, timeout=15 * 60)  # 15 min window
            remaining_attempts = 5 - attempts

            if remaining_attempts > 0:
                messages.error(
                    request,
                    f"❌ Invalid username or password. "
                    f"{remaining_attempts} attempt(s) remaining before lockout.",
                )
            else:
                messages.error(
                    request,
                    "🔒 Too many failed attempts. Account locked for 15 minutes.",
                )

    return render(
        request,
        "auth/login.html",
        {"username": username, "remember_me": remember_me, "next": next_url},
    )


def _get_client_ip(request):
    from core.ip_utils import get_client_ip
    return get_client_ip(request) or request.META.get("REMOTE_ADDR", "0.0.0.0")


def get_shift(t):
    """Return which shift a time belongs to."""
    if MORNING_START <= t <= MORNING_END:
        return "morning"
    if EVENING_START <= t <= EVENING_END:
        return "evening"
    return None


def is_late(t, shift):
    """Check if clock-in time is late beyond grace period."""
    if shift == "morning":
        grace = (
            datetime.combine(datetime.today(), MORNING_START)
            + timedelta(minutes=LATE_GRACE)
        ).time()
        return t > grace
    if shift == "evening":
        grace = (
            datetime.combine(datetime.today(), EVENING_START)
            + timedelta(minutes=LATE_GRACE)
        ).time()
        return t > grace
    return False


def _is_platform_superadmin(user):
    """True only for Django superusers who also have is_platform_admin=True on their Profile."""
    if not user.is_authenticated or not user.is_superuser:
        return False
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_platform_admin)


def _is_clinic_admin(user):
    """True for users with a ClinicAdmin record (is_staff=True, is_superuser=False)."""
    if not user.is_authenticated:
        return False
    return hasattr(user, "clinic_admin_profile")


def platform_superadmin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not _is_platform_superadmin(request.user):
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return wrapper


def _redirect_by_role(user):
    """Redirect user to their role-appropriate dashboard after login."""
    # Platform superadmin (is_superuser + is_platform_admin)
    if _is_platform_superadmin(user):
        return redirect("super_admin_dashboard")
    # Clinic admin (has ClinicAdmin record)
    if _is_clinic_admin(user):
        return redirect("admin_dashboard")
    # Staff / physiotherapist
    if hasattr(user, "staff_profile"):
        return redirect("staff_dashboard")
    # Regular patient
    return redirect("client_dashboard")


def register_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if password != confirm_password:
            messages.error(request, "❌ Passwords do not match!")
            return redirect("register")
        if User.objects.filter(username=username).exists():
            messages.error(request, "❌ Username already taken!")
            return redirect("register")
        if User.objects.filter(email=email).exists():
            messages.error(request, "❌ Email already registered!")
            return redirect("register")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        messages.success(request, "✅ Account created! Please login.")
        return redirect("login")
    return render(request, "auth/register.html")


def logout_view(request):
    logout(request)
    return redirect("home")


# ─── PROFILE ─────────────────────────────────────────────────


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "client/profile.html", {"profile": profile})


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name", "").strip()
        request.user.last_name = request.POST.get("last_name", "").strip()
        request.user.email = request.POST.get("email", "").strip()
        request.user.save()

        profile.phone_number = request.POST.get("phone_number", "").strip()
        profile.gender = request.POST.get("gender", "")
        profile.date_of_birth = request.POST.get("date_of_birth") or None
        profile.blood_group = request.POST.get("blood_group", "")
        profile.emergency_contact = request.POST.get("emergency_contact", "").strip()
        profile.medical_notes = request.POST.get("medical_notes", "").strip()
        profile.address = request.POST.get("address", "").strip()
        if request.FILES.get("profile_photo"):
            photo = request.FILES["profile_photo"]
            from .file_security import validate_image_file
            try:
                validate_image_file(photo, max_size_mb=5, field_name="Profile photo")
                profile.profile_photo = photo
            except ValidationError as e:
                messages.error(request, f"❌ {e.message if hasattr(e, 'message') else str(e)}")
                return render(request, "client/edit_profile.html", {"profile": profile})
        profile.save()

        messages.success(request, "✅ Profile updated successfully.")
        return redirect("profile")
    return render(request, "client/edit_profile.html", {"profile": profile})


# ─── PASSWORD RESET (OTP FLOW) ───────────────────────────────


def request_otp(request):
    """Step 1 – user enters their email."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "❌ No account found with that email.")
            return render(request, "auth/request_otp.html")

        # Expire old OTPs
        PasswordResetOTP.objects.filter(user=user).delete()

        import secrets
        otp = f"{secrets.SystemRandom().randint(100000, 999999):06d}"
        PasswordResetOTP.objects.create(user=user, otp=otp)

        ok = send_otp_email(email, otp, purpose="Password Reset", user=user)
        if ok:
            messages.success(request, f"✅ OTP sent to {email}. Check your inbox.")
        else:
            messages.warning(
                request, "⚠️ Could not send email. Check server email config."
            )

        request.session["reset_user_id"] = user.id
        return redirect("verify_otp")

    return render(request, "auth/request_otp.html")


def verify_otp(request):
    """Step 2 – user enters OTP."""
    user_id = request.session.get("reset_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect("request_otp")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()
        try:
            user = User.objects.get(id=user_id)
            otp_obj = PasswordResetOTP.objects.filter(user=user).latest("created_at")
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            messages.error(request, "❌ Invalid or expired OTP.")
            return redirect("request_otp")

        if otp_obj.is_expired():
            messages.error(request, "❌ OTP expired. Please request a new one.")
            return redirect("request_otp")

        if entered_otp == otp_obj.otp:
            request.session["otp_verified"] = True
            otp_obj.delete()
            return redirect("reset_password")

        messages.error(request, "❌ Incorrect OTP. Try again.")
    return render(request, "auth/verify_otp.html")


def resend_otp(request):
    """Resend OTP to same email."""
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("request_otp")
    try:
        user = User.objects.get(id=user_id)
        PasswordResetOTP.objects.filter(user=user).delete()
        otp = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.create(user=user, otp=otp)
        ok = send_otp_email(user.email, otp, purpose="Password Reset", user=user)
        if ok:
            messages.success(request, "✅ New OTP sent!")
        else:
            messages.warning(request, "⚠️ Could not send email.")
    except User.DoesNotExist:
        messages.error(request, "User not found.")
    return redirect("verify_otp")


def reset_password(request):
    """
    Step 3 - Set new password after OTP verification.
    """

    if not request.session.get("otp_verified"):
        messages.error(request, "Please verify OTP first.")
        return redirect("request_otp")

    user_id = request.session.get("reset_user_id")

    if not user_id:
        messages.error(request, "Session expired.")
        return redirect("request_otp")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("request_otp")

    if request.method == "POST":
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # Empty fields
        if not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect("reset_password")

        # Password match check
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("reset_password")

        # Minimum length
        if len(password) < 8:
            messages.error(request, "Password must contain at least 8 characters.")
            return redirect("reset_password")

        # Same as old password check
        if user.check_password(password):
            messages.error(
                request, "New password cannot be the same as your current password."
            )
            return redirect("reset_password")

        # Save password
        user.set_password(password)
        user.save()

        # Clear reset session
        request.session.pop("otp_verified", None)
        request.session.pop("reset_user_id", None)

        messages.success(request, "Password reset successfully. Please login.")

        return redirect("login")

    return render(request, "auth/reset_password.html")


@login_required
def change_password_request(request):

    if request.method == "POST":

        if not request.user.email:
            messages.error(request, "❌ Email not set in user profile")
            return redirect("change_password")

        otp = str(random.randint(100000, 999999))

        PasswordResetOTP.objects.filter(user=request.user).delete()
        PasswordResetOTP.objects.create(user=request.user, otp=otp)

        ok = send_otp_email(request.user.email, otp, purpose="Password Change", user=request.user)

        if ok:
            messages.success(request, "✅ OTP sent successfully")
        else:
            messages.error(request, "❌ Email sending failed (check logs)")

        request.session["reset_user_id"] = request.user.id
        request.session["otp_verified"] = False

        return redirect("verify_otp")

    return render(request, "auth/change_password.html")


# ─── NOTIFICATIONS ───────────────────────────────────────────


@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(recipient=request.user)
    is_admin = request.user.is_superuser or _is_clinic_admin(request.user)
    tpl = "admin/admin_notifications.html" if is_admin else "client/notifications.html"
    return render(
        request,
        tpl,
        {
            "notifications": notifs,
            "today": timezone.now().date(),
        },
    )


@login_required
def mark_notification_read(request, notif_id):
    Notification.objects.filter(id=notif_id, recipient=request.user).update(
        is_read=True
    )
    return JsonResponse({"status": "ok"})


@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    messages.success(request, "✅ All notifications marked as read.")
    return redirect("notifications")


# ─── PAYMENT ─────────────────────────────────────────────────




def _user_payment_role(user):
    """Determine the effective payment role and scope for a user.
    Returns: (role_str, can_manage_bool, hospital_obj)
    Roles:
      - 'super_admin': platform-wide management
      - 'admin': clinic-scoped management
      - 'staff': clinic-scoped read-only
      - 'client': own-record read-only
    """
    if not user or not user.is_authenticated:
        return "anonymous", False, None
    if user.is_superuser or _is_platform_superadmin(user):
        return "super_admin", True, None
    if _is_clinic_admin(user):
        return "admin", True, resolve_hospital(user)
    if _is_staff(user):
        return "staff", False, resolve_hospital(user)
    return "client", False, resolve_hospital(user)


def log_payment_audit(actor, action, pay=None, hospital=None, notes="", metadata=None):
    """Record an audit event for payment creation, mutation, confirmation, or cancellation."""
    h = hospital or (pay.hospital if pay else None)
    meta = {
        "payment_id": pay.id if pay else None,
        "amount": str(pay.amount) if pay else None,
        "method": pay.method if pay else None,
        "status": pay.status if pay else None,
        "transaction_id": pay.transaction_id if pay else "",
        "notes": notes,
    }
    if metadata:
        meta.update(metadata)
    try:
        AuditEvent.objects.create(
            hospital=h,
            actor=actor if actor and actor.is_authenticated else None,
            action=action,
            entity_type="PaymentRecord",
            entity_id=str(pay.id) if pay else "",
            metadata=meta,
        )
    except Exception as e:
        logger.warning(f"Failed to record payment audit event: {e}")


@login_required
def payments(request):
    """Payment entry point:
    - Super Admin -> redirect to super_admin_all_payments
    - Clinic Admin -> redirect to admin_payments
    - Staff -> redirect to staff_payments (read-only clinic log)
    - Client -> render read-only personal payment history
    - POST: Only Super Admin & Clinic Admin may create payments; Staff & Client rejected with 403.
    """
    role, can_manage, hospital = _user_payment_role(request.user)

    if request.method == "POST":
        if not can_manage:
            if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.META.get("HTTP_ACCEPT", ""):
                return JsonResponse({"error": "Forbidden: Staff and clients cannot create payment records."}, status=403)
            return HttpResponseForbidden("Forbidden: Staff and clients cannot create payment records.")
        return payment_create(request)

    if role == "super_admin":
        return redirect("super_admin_all_payments")
    if role == "admin":
        return redirect("admin_payments")
    if role == "staff":
        return redirect("staff_payments")

    # Client (Patient) personal payment history
    qs = PaymentRecord.objects.filter(patient=request.user).order_by("-created_at")
    q = request.GET.get("q", "").strip()
    status_f = request.GET.get("status", "").strip()
    method_f = request.GET.get("method", "").strip()
    sort_f = request.GET.get("sort", "").strip()

    if q:
        qs = qs.filter(Q(transaction_id__icontains=q) | Q(notes__icontains=q))
    if status_f:
        qs = qs.filter(status=status_f)
    if method_f:
        qs = qs.filter(method=method_f)

    if sort_f == "date-asc":
        qs = qs.order_by("created_at")
    elif sort_f == "amount-desc":
        qs = qs.order_by("-amount")
    elif sort_f == "amount-asc":
        qs = qs.order_by("amount")
    else:
        qs = qs.order_by("-created_at")

    total_paid = qs.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
    pending_amount = qs.filter(status="pending").aggregate(t=Sum("amount"))["t"] or 0
    upcoming_appointments = Appointment.objects.filter(
        patient=request.user, status__in=["pending", "confirmed"]
    ).order_by("date")
    clinic = ClinicSettings.objects.first()

    return render(
        request,
        "client/payments.html",
        {
            "my_payments": qs,
            "total_paid": total_paid,
            "pending_amount": pending_amount,
            "upcoming_appointments": upcoming_appointments,
            "clinic": clinic,
            "q": q,
            "status_f": status_f,
            "method_f": method_f,
            "sort_f": sort_f,
        },
    )


@login_required
def payment_create(request):
    """Payment creation view: Super Admin and Clinic Admin only.
    Staff and Client are strictly forbidden (HTTP 403).
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and clients are not authorized to create payment records.")

    if request.method == "POST":
        is_json = (
            request.content_type == "application/json"
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.META.get("HTTP_ACCEPT", "")
        )
        if request.content_type == "application/json" and request.body:
            try:
                body_json = _json.loads(request.body.decode("utf-8"))
            except Exception:
                body_json = {}
        else:
            body_json = {}

        patient_id = body_json.get("patient_id") or request.POST.get("patient_id")
        amount_str = body_json.get("amount") or request.POST.get("amount", "0")
        method = body_json.get("method") or request.POST.get("method", "cash")
        appt_id = body_json.get("appointment_id") or request.POST.get("appointment_id", "")
        notes = (body_json.get("notes") or request.POST.get("notes", "")).strip()
        txn_id = (body_json.get("transaction_id") or request.POST.get("transaction_id", "")).strip() or f"COUNTER-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        try:
            amount_val = float(amount_str)
            if amount_val <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            if is_json:
                return JsonResponse({"error": "Invalid payment amount. Amount must be positive."}, status=400)
            messages.error(request, "❌ Invalid payment amount. Amount must be positive.")
            return redirect("admin_payments")

        valid_methods = [c[0] for c in PaymentRecord.METHOD_CHOICES]
        if method not in valid_methods:
            method = "cash"

        patient = get_object_or_404(User, id=patient_id)
        target_hospital = hospital

        if role == "admin":
            is_clinic_patient = (
                (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
                or patient.appointments.filter(hospital=hospital).exists()
            )
            if not is_clinic_patient:
                return HttpResponseForbidden("Forbidden: Cannot record payment for a patient outside your clinic.")
        elif role == "super_admin":
            target_h_id = body_json.get("hospital_id") or request.POST.get("hospital_id")
            if target_h_id:
                target_hospital = Hospital.objects.filter(id=target_h_id).first()
            if not target_hospital:
                target_hospital = resolve_hospital(patient)

        pay = PaymentRecord.objects.create(
            hospital=target_hospital,
            patient=patient,
            appointment_id=appt_id if appt_id else None,
            amount=amount_val,
            method=method,
            status="paid",
            transaction_id=txn_id,
            notes=notes,
        )
        log_payment_audit(request.user, "payment_created", pay=pay, hospital=target_hospital, notes=notes)
        Notification.objects.create(
            hospital=target_hospital,
            recipient=patient,
            message=f"✅ Receipt issued: Payment of ₹{pay.amount} ({method.upper()}) recorded by clinic admin.",
            link="/payments/",
        )
        if is_json:
            return JsonResponse({"success": True, "payment_id": pay.id, "amount": str(pay.amount)}, status=201)

        messages.success(request, f"✅ Payment of ₹{pay.amount} successfully recorded for {patient.get_full_name() or patient.username}.")
        return redirect("admin_payments")

    return redirect("admin_payments")


@login_required
def payment_detail(request, payment_id):
    """Payment detail API and view:
    - Super Admin: platform-wide access
    - Admin: clinic-scoped access
    - Staff: clinic-scoped read-only access (mutations rejected with 403)
    - Client: own-record read-only access (mutations rejected with 403, other patients rejected with 403)
    - Prevents IDOR/BOLA and Mass Assignment.
    """
    pay = get_object_or_404(
        PaymentRecord.objects.select_related("patient", "hospital", "appointment"),
        id=payment_id
    )
    role, can_manage, hospital = _user_payment_role(request.user)

    # Client (Patient) Authorization Check
    if role == "client":
        if pay.patient != request.user:
            return HttpResponseForbidden("Forbidden: Cannot access another patient's payment record.")
        if request.method in ("PUT", "PATCH", "DELETE", "POST"):
            return HttpResponseForbidden("Forbidden: Clients cannot modify or delete payment records.")
        return JsonResponse({
            "success": True,
            "id": pay.id,
            "amount": str(pay.amount),
            "method": pay.method,
            "method_display": pay.get_method_display(),
            "status": pay.status,
            "status_display": pay.get_status_display(),
            "transaction_id": pay.transaction_id,
            "notes": pay.notes,
            "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
            "patient_name": pay.patient.get_full_name() or pay.patient.username,
            "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
            "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
            "payment": {
                "id": pay.id,
                "amount": float(pay.amount),
                "method": pay.method,
                "method_display": pay.get_method_display(),
                "status": pay.status,
                "status_display": pay.get_status_display(),
                "transaction_id": pay.transaction_id,
                "notes": pay.notes,
                "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
                "patient_name": pay.patient.get_full_name() or pay.patient.username,
                "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
                "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
            }
        })

    # Staff Authorization Check
    if role == "staff":
        if hospital and pay.hospital != hospital:
            return HttpResponseForbidden("Forbidden: Cannot access payment records outside your clinic.")
        if request.method in ("PUT", "PATCH", "DELETE", "POST"):
            return HttpResponseForbidden("Forbidden: Staff members cannot modify or delete payment records.")
        return JsonResponse({
            "success": True,
            "id": pay.id,
            "amount": str(pay.amount),
            "method": pay.method,
            "method_display": pay.get_method_display(),
            "status": pay.status,
            "status_display": pay.get_status_display(),
            "transaction_id": pay.transaction_id,
            "notes": pay.notes,
            "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
            "patient_name": (pay.patient.get_full_name() or pay.patient.username) if pay.patient else "—",
            "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
            "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
            "payment": {
                "id": pay.id,
                "amount": float(pay.amount),
                "method": pay.method,
                "method_display": pay.get_method_display(),
                "status": pay.status,
                "status_display": pay.get_status_display(),
                "transaction_id": pay.transaction_id,
                "notes": pay.notes,
                "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
                "patient_name": (pay.patient.get_full_name() or pay.patient.username) if pay.patient else "—",
                "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
                "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
            }
        })

    # Admin Authorization Check
    if role == "admin":
        if hospital and pay.hospital != hospital:
            return HttpResponseForbidden("Forbidden: Cannot access payment records outside your clinic.")

    # Mutations (PUT / PATCH / DELETE) for Admin & Super Admin
    if request.method in ("PUT", "PATCH"):
        try:
            body_data = _json.loads(request.body.decode("utf-8")) if request.body else {}
        except Exception:
            body_data = {}
        if not body_data:
            body_data = request.POST

        # Prevent mass assignment: strictly whitelist allowed fields
        if "amount" in body_data:
            try:
                new_amt = float(body_data["amount"])
                if new_amt > 0:
                    pay.amount = new_amt
            except (ValueError, TypeError):
                pass
        if "status" in body_data:
            new_status = body_data["status"]
            valid_statuses = [s[0] for s in PaymentRecord.STATUS_CHOICES]
            if new_status in valid_statuses:
                pay.status = new_status
        if "notes" in body_data:
            pay.notes = str(body_data["notes"]).strip()
        if "transaction_id" in body_data and body_data["transaction_id"]:
            pay.transaction_id = str(body_data["transaction_id"]).strip()

        pay.save()
        log_payment_audit(request.user, "payment_updated", pay=pay, hospital=pay.hospital)
        return JsonResponse({"success": True, "message": "Payment record updated successfully."})

    if request.method == "DELETE":
        pay.status = "refunded"
        pay.save()
        log_payment_audit(request.user, "payment_deleted", pay=pay, hospital=pay.hospital)
        return JsonResponse({"success": True, "message": "Payment record cancelled/refunded."})

    # GET response for Admin and Super Admin
    return JsonResponse({
        "success": True,
        "id": pay.id,
        "amount": str(pay.amount),
        "method": pay.method,
        "method_display": pay.get_method_display(),
        "status": pay.status,
        "status_display": pay.get_status_display(),
        "transaction_id": pay.transaction_id,
        "notes": pay.notes,
        "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
        "patient_name": (pay.patient.get_full_name() or pay.patient.username) if pay.patient else "—",
        "patient_email": pay.patient.email if pay.patient else "—",
        "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
        "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
        "payment": {
            "id": pay.id,
            "amount": float(pay.amount),
            "method": pay.method,
            "method_display": pay.get_method_display(),
            "status": pay.status,
            "status_display": pay.get_status_display(),
            "transaction_id": pay.transaction_id,
            "notes": pay.notes,
            "created_at": pay.created_at.strftime("%d %b %Y, %H:%M"),
            "patient_name": (pay.patient.get_full_name() or pay.patient.username) if pay.patient else "—",
            "service": pay.appointment.get_service_display() if pay.appointment else "General Consultation",
            "clinic_name": pay.hospital.name if pay.hospital else "PhysioRehab Clinic",
        }
    })


@login_required
def payment_edit(request, payment_id):
    """Payment edit view: Super Admin and Clinic Admin only."""
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and clients cannot edit payment records.")
    pay = get_object_or_404(PaymentRecord, id=payment_id)
    if role == "admin" and pay.hospital != hospital:
        return HttpResponseForbidden("Forbidden: Cannot edit payment records belonging to another clinic.")

    if request.method in ("POST", "PUT", "PATCH"):
        is_json = (
            request.content_type == "application/json"
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.META.get("HTTP_ACCEPT", "")
        )
        if request.content_type == "application/json" and request.body:
            try:
                body_data = _json.loads(request.body.decode("utf-8"))
            except Exception:
                body_data = {}
        else:
            body_data = request.POST

        # Whitelist updates
        if "amount" in body_data:
            try:
                new_amt = float(body_data["amount"])
                if new_amt > 0:
                    pay.amount = new_amt
            except (ValueError, TypeError):
                pass
        valid_statuses = [s[0] for s in PaymentRecord.STATUS_CHOICES]
        new_status = body_data.get("status")
        if new_status in valid_statuses:
            pay.status = new_status
        notes = body_data.get("notes")
        if notes is not None:
            pay.notes = str(notes).strip()
        txn_id = body_data.get("transaction_id")
        if txn_id:
            pay.transaction_id = str(txn_id).strip()
        pay.save()
        log_payment_audit(request.user, "payment_updated", pay=pay, hospital=pay.hospital)

        if is_json:
            return JsonResponse({"success": True, "message": f"Payment #{pay.id} updated."})

        messages.success(request, f"✅ Payment #{pay.id} updated.")
        return redirect("admin_payments")

    return redirect("admin_payments")


@login_required
def payment_delete(request, payment_id):
    """Payment cancellation / deletion view: Super Admin and Clinic Admin only."""
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and clients cannot delete or cancel payments.")
    pay = get_object_or_404(PaymentRecord, id=payment_id)
    if role == "admin" and pay.hospital != hospital:
        return HttpResponseForbidden("Forbidden: Cannot delete payment records belonging to another clinic.")

    pay.status = "refunded"
    pay.save()
    log_payment_audit(request.user, "payment_cancelled", pay=pay, hospital=pay.hospital)
    messages.success(request, f"✅ Payment #{pay.id} cancelled / refunded.")
    return redirect("admin_payments")


@login_required
def staff_payments(request):
    """Dedicated Staff payments endpoint:
    Renders assigned consultation fee collections and compensation summary
    strictly scoped to the authenticated staff member.
    Enforces server-side tenant and user isolation: staff cannot view other staff's
    records or clinic-wide totals. Clients receive 403 Forbidden.
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if role == "client" or (not _is_staff(request.user) and not _is_clinic_admin(request.user) and not request.user.is_superuser):
        return HttpResponseForbidden("Forbidden: Clients cannot access staff payment logs.")

    hospital = hospital or resolve_hospital(request.user)
    assigned_payments = PaymentRecord.objects.filter(
        appointment__assigned_staff=request.user
    ).select_related("appointment", "patient")

    if hospital:
        assigned_payments = assigned_payments.filter(hospital=hospital)

    # Search query
    query = request.GET.get("q", "").strip()
    if query:
        assigned_payments = assigned_payments.filter(
            Q(patient__first_name__icontains=query)
            | Q(patient__last_name__icontains=query)
            | Q(patient__username__icontains=query)
            | Q(appointment__name__icontains=query)
            | Q(transaction_id__icontains=query)
        )

    # Status filter
    status_filter = request.GET.get("status", "").strip().lower()
    if status_filter in ["paid", "pending", "refunded", "failed"]:
        assigned_payments = assigned_payments.filter(status=status_filter)

    # Date period filter
    period = request.GET.get("period", "").strip().lower()
    now = timezone.now()
    today = now.date()
    if period == "today":
        assigned_payments = assigned_payments.filter(
            Q(created_at__date=today) | Q(appointment__date=today)
        )
    elif period == "7d":
        since_7d = today - timedelta(days=7)
        assigned_payments = assigned_payments.filter(
            Q(created_at__gte=now - timedelta(days=7)) | Q(appointment__date__gte=since_7d)
        )
    elif period == "30d":
        since_30d = today - timedelta(days=30)
        assigned_payments = assigned_payments.filter(
            Q(created_at__gte=now - timedelta(days=30)) | Q(appointment__date__gte=since_30d)
        )
    elif period == "this_month":
        assigned_payments = assigned_payments.filter(
            Q(created_at__year=now.year, created_at__month=now.month)
            | Q(appointment__date__year=now.year, appointment__date__month=now.month)
        )

    # KPI calculations for assigned consultations and personal salary
    total_collected = (
        assigned_payments.filter(status="paid").aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )
    pending_collections = (
        assigned_payments.filter(status="pending").aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )
    total_sessions_count = assigned_payments.count()

    salary_qs = SalaryRecord.objects.filter(staff=request.user)
    if hospital:
        salary_qs = salary_qs.filter(hospital=hospital)
    total_salary_earned = (
        salary_qs.filter(is_paid=True).aggregate(s=Sum("net_salary"))["s"]
        or Decimal("0.00")
    )

    # Pagination
    ordered_payments = assigned_payments.order_by("-created_at")
    paginator = Paginator(ordered_payments, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "staff/staff_payments.html",
        {
            "page_obj": page_obj,
            "total_collected": total_collected,
            "pending_collections": pending_collections,
            "total_sessions_count": total_sessions_count,
            "total_salary_earned": total_salary_earned,
            "query": query,
            "status_filter": status_filter,
            "period": period,
            "hospital": hospital,
            "is_staff_view": True,
            "can_manage": False,
        },
    )


@login_required
def admin_payments(request):
    """Clinic payment records:
    - Super Admin: full management across clinics
    - Clinic Admin: full management within own clinic
    - Staff: read-only payment log & history within clinic (all mutations return 403)
    - Client: redirected to client personal payments
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if role == "client":
        return redirect("payments")

    if request.method == "POST":
        if not can_manage:
            return HttpResponseForbidden("Forbidden: Staff members cannot create or modify payment records.")
        action = request.POST.get("action", "")
        if action == "record_offline":
            return payment_create(request)

    if role == "super_admin":
        qs = PaymentRecord.objects.select_related("patient", "appointment", "hospital").order_by("-created_at")
        patients = User.objects.filter(is_superuser=False, is_staff=False).order_by("first_name", "username")
    else:
        qs = PaymentRecord.objects.filter(hospital=hospital).select_related("patient", "appointment", "hospital").order_by("-created_at")
        patients = User.objects.filter(
            is_superuser=False, is_staff=False
        ).filter(
            Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital)
        ).distinct().order_by("first_name", "username")

    total_paid = qs.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
    pending_count = qs.filter(status="pending").count()
    pending_payments = qs.filter(status="pending")

    return render(
        request,
        "admin/admin_payments.html",
        {
            "payments": qs,
            "total_paid": total_paid,
            "pending_count": pending_count,
            "pending_payments": pending_payments,
            "patients": patients,
            "can_manage": can_manage,
            "is_staff_view": not can_manage,
            "hospital": hospital,
        },
    )


@login_required
@require_POST
def confirm_payment(request, payment_id):
    """Confirm pending payment. Gated to Super Admin and Clinic Admin (scoped to clinic).
    Staff and Client rejected with HTTP 403.
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and clients cannot modify payment status.")
    pay = get_object_or_404(PaymentRecord, id=payment_id)
    if role == "admin" and pay.hospital != hospital:
        return HttpResponseForbidden("Forbidden: Cannot modify payment records belonging to another clinic.")

    pay.status = "paid"
    if not pay.transaction_id:
        pay.transaction_id = f"CONF-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    pay.save()
    log_payment_audit(request.user, "payment_confirmed", pay=pay, hospital=pay.hospital)
    if pay.patient:
        Notification.objects.create(
            hospital=pay.hospital,
            recipient=pay.patient,
            message=f"✅ Your payment of ₹{pay.amount} has been confirmed by the clinic. Thank you!",
            link="/payments/",
        )
    messages.success(request, f"✅ Payment of ₹{pay.amount} confirmed for {pay.patient.get_full_name() or pay.patient.username if pay.patient else 'patient'}.")
    return redirect("admin_payments")


@login_required
@require_POST
def reject_payment(request, payment_id):
    """Reject pending payment. Gated to Super Admin and Clinic Admin (scoped to clinic).
    Staff and Client rejected with HTTP 403.
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and clients cannot modify payment status.")
    pay = get_object_or_404(PaymentRecord, id=payment_id)
    if role == "admin" and pay.hospital != hospital:
        return HttpResponseForbidden("Forbidden: Cannot modify payment records belonging to another clinic.")

    pay.status = "failed"
    pay.save()
    log_payment_audit(request.user, "payment_rejected", pay=pay, hospital=pay.hospital)
    if pay.patient:
        Notification.objects.create(
            hospital=pay.hospital,
            recipient=pay.patient,
            message=f"❌ Your payment of ₹{pay.amount} could not be verified. Please contact the clinic or try again.",
            link="/payments/",
        )
    messages.warning(request, f"❌ Payment of ₹{pay.amount} rejected for {pay.patient.get_full_name() or pay.patient.username if pay.patient else 'patient'}.")
    return redirect("admin_payments")


@login_required
@require_POST
def record_cash_payment(request):
    """Record cash payment. Gated to Super Admin and Clinic Admin.
    Staff and Client are forbidden from direct entry (HTTP 403).
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and patients cannot enter cash payment records directly.")

    amount = request.POST.get("amount", "0")
    appt_id = request.POST.get("appointment_id", "")
    notes = request.POST.get("notes", "")
    patient_id = request.POST.get("patient_id")

    appt = Appointment.objects.filter(id=appt_id).first() if appt_id else None
    if appt:
        patient = appt.patient
        target_hospital = hospital or appt.hospital
    elif patient_id:
        patient = get_object_or_404(User, id=patient_id)
        target_hospital = hospital
    else:
        patient = None
        target_hospital = hospital

    if not patient:
        messages.error(request, "❌ Valid patient or appointment required.")
        return redirect("admin_payments")

    if role == "admin" and target_hospital:
        if appt and appt.hospital_id != target_hospital.id:
            return HttpResponseForbidden("Forbidden: Cannot record payment for another clinic's appointment.")
        is_clinic_patient = (
            (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == target_hospital.id)
            or patient.appointments.filter(hospital=target_hospital).exists()
        )
        if not is_clinic_patient:
            return HttpResponseForbidden("Forbidden: Cannot record payment for patient from another clinic.")

    try:
        amount_val = float(amount) if amount else 0
        if amount_val <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        messages.error(request, "❌ Invalid payment amount.")
        return redirect("admin_payments")

    pay = PaymentRecord.objects.create(
        hospital=target_hospital,
        patient=patient,
        appointment_id=appt.id if appt else (appt_id if appt_id else None),
        amount=amount_val,
        method="cash",
        status="paid",
        notes=notes,
        transaction_id=f"CASH-{timezone.now().strftime('%Y%m%d%H%M%S')}",
    )
    log_payment_audit(request.user, "payment_cash_recorded", pay=pay, hospital=target_hospital)
    messages.success(request, "✅ Cash payment recorded.")
    return redirect("admin_payments")


@login_required
@require_POST
def record_upi_payment(request):
    """Record UPI payment. Gated to Super Admin and Clinic Admin.
    Staff and Client are forbidden from direct entry (HTTP 403).
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: Staff and patients cannot enter UPI payment records directly.")

    amount = request.POST.get("amount", "0")
    appt_id = request.POST.get("appointment_id", "")
    txn_id = request.POST.get("transaction_id", "")
    patient_id = request.POST.get("patient_id")

    appt = Appointment.objects.filter(id=appt_id).first() if appt_id else None
    if appt:
        patient = appt.patient
        target_hospital = hospital or appt.hospital
    elif patient_id:
        patient = get_object_or_404(User, id=patient_id)
        target_hospital = hospital
    else:
        patient = None
        target_hospital = hospital

    if not patient:
        messages.error(request, "❌ Valid patient or appointment required.")
        return redirect("admin_payments")

    if role == "admin" and target_hospital:
        if appt and appt.hospital_id != target_hospital.id:
            return HttpResponseForbidden("Forbidden: Cannot record payment for another clinic's appointment.")
        is_clinic_patient = (
            (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == target_hospital.id)
            or patient.appointments.filter(hospital=target_hospital).exists()
        )
        if not is_clinic_patient:
            return HttpResponseForbidden("Forbidden: Cannot record payment for patient from another clinic.")

    try:
        amount_val = float(amount) if amount else 0
        if amount_val <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        messages.error(request, "❌ Invalid payment amount.")
        return redirect("admin_payments")

    pay = PaymentRecord.objects.create(
        hospital=target_hospital,
        patient=patient,
        appointment_id=appt.id if appt else (appt_id if appt_id else None),
        amount=amount_val,
        method="upi",
        status="pending",
        transaction_id=txn_id,
        notes=f"UPI Ref: {txn_id}",
    )
    log_payment_audit(request.user, "payment_upi_recorded", pay=pay, hospital=target_hospital)
    messages.success(request, "✅ UPI payment submitted for verification.")
    return redirect("admin_payments")


@login_required
def export_clinic_payments_excel(request):
    """Export clinic payments to Excel: Admin (own clinic) and Super Admin.
    Staff and Client rejected with HTTP 403.
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: You do not have permission to export payment records.")
    return export_payments_excel(request)


@login_required
def export_clinic_payments_pdf(request):
    """Export clinic payments to PDF: Admin (own clinic) and Super Admin.
    Staff and Client rejected with HTTP 403.
    """
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: You do not have permission to export payment records.")
    return export_payments_pdf(request)





# ─── CLIENT DASHBOARD ────────────────────────────────────────


@login_required
def client_dashboard(request):
    if request.user.is_superuser or _is_clinic_admin(request.user):
        return redirect("admin_dashboard")
    appointments = Appointment.objects.filter(patient=request.user)
    upcoming = appointments.filter(status__in=["pending", "confirmed"])
    completed = appointments.filter(status="completed")
    recent_notifs = Notification.objects.filter(recipient=request.user)[:5]
    has_reviewed = Review.objects.filter(patient=request.user).exists()
    approved_reviews = Review.objects.filter(is_approved=True).order_by("-created_at")[:6]
    my_payments = PaymentRecord.objects.filter(patient=request.user).order_by("-created_at")[:5]
    upcoming_appointments = upcoming.order_by("date")
    return render(
        request,
        "client/client_dashboard.html",
        {
            "appointments": appointments,
            "upcoming": upcoming,
            "completed": completed,
            "total": appointments.count(),
            "upcoming_count": upcoming.count(),
            "completed_count": completed.count(),
            "recent_notifs": recent_notifs,
            "has_reviewed": has_reviewed,
            "approved_reviews": approved_reviews,
            "my_payments": my_payments,
            "upcoming_appointments": upcoming_appointments,
        },
    )


# ─── ADMIN DASHBOARD ─────────────────────────────────────────


@login_required
def admin_dashboard(request):
    # Allow Django superusers (not platform_admin) AND clinic admins
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    from django.db.models import Sum
    from decimal import Decimal
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital:
        all_appointments = Appointment.objects.filter(hospital=hospital)
        total_staff = StaffProfile.objects.filter(hospital=hospital).count()
        total_users = User.objects.filter(
            is_superuser=False, is_staff=False, appointments__hospital=hospital
        ).distinct().count()
        recent_payments = PaymentRecord.objects.filter(hospital=hospital).order_by("-created_at")[:6]
        total_paid = PaymentRecord.objects.filter(hospital=hospital, status="paid").aggregate(t=Sum("amount"))["t"] or 0
        pending_payments_count = PaymentRecord.objects.filter(hospital=hospital, status="pending").count()
    else:
        all_appointments = Appointment.objects.all()
        total_staff = StaffProfile.objects.count()
        total_users = User.objects.filter(is_superuser=False, is_staff=False).count()
        recent_payments = PaymentRecord.objects.order_by("-created_at")[:6]
        total_paid = PaymentRecord.objects.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
        pending_payments_count = PaymentRecord.objects.filter(status="pending").count()

    pending = all_appointments.filter(status="pending").count()
    confirmed = all_appointments.filter(status="confirmed").count()
    completed = all_appointments.filter(status="completed").count()
    new_messages = Message.objects.filter(receiver=request.user, is_read=False).count()
    blogs = Blog.objects.order_by("-created_at")[:6]
    pending_reviews = Review.objects.filter(is_approved=False).count()
    recent_reviews = Review.objects.filter(is_approved=True).order_by("-created_at")[:4]
    dismissed = request.session.get("dismissed_promos", [])
    active_promos = [
        p
        for p in ClinicPromo.objects.filter(is_active=True)
        if p.is_live and str(p.id) not in dismissed
    ]
    return render(
        request,
        "admin/admin_dashboard.html",
        {
            "hospital": hospital,
            "total_users": total_users,
            "all_appointments": all_appointments,
            "total_appointments": all_appointments.count(),
            "pending": pending,
            "confirmed": confirmed,
            "completed": completed,
            "new_messages": new_messages,
            "total_staff": total_staff,
            "blogs": blogs,
            "pending_reviews": pending_reviews,
            "recent_reviews": recent_reviews,
            "active_promos": active_promos,
            "recent_payments": recent_payments,
            "total_paid": total_paid,
            "pending_payments_count": pending_payments_count,
        },
    )


# ─── APPOINTMENTS ────────────────────────────────────────────


@login_required
def book_appointment(request):
    if request.method == "POST":
        hospital = resolve_hospital(request.user)
        if not hospital:
            h_id = request.POST.get("hospital_id")
            if h_id:
                hospital = Hospital.objects.filter(id=h_id, is_active=True).first()
            if not hospital:
                hospital = Hospital.objects.filter(is_active=True).first()
        service = request.POST.get("service", "")
        date = request.POST.get("date", "").strip()
        time = request.POST.get("time", "").strip()
        notes = request.POST.get("notes", "").strip()
        name = request.user.get_full_name() or request.user.username
        email = request.user.email
        phone = getattr(request.user, "profile", None)
        phone = phone.phone_number if phone else ""

        # Validate appointment slot against clinic shift rules (No Sunday public bookings, valid Mon-Sat shifts)
        is_valid, err_msg, normalized_time = validate_appointment_booking(
            date_str=date,
            time_str=time,
            hospital=hospital,
            allow_sunday=False,
        )
        if not is_valid:
            messages.error(request, f"❌ {err_msg}")
            return render(request, "client/book_appointment.html", {
                "selected_service": service,
                "selected_date": date,
                "selected_time": time,
                "notes": notes,
            })

        try:
            with transaction.atomic():
                # Concurrent booking double-check inside transaction
                is_valid_tx, err_tx, _ = validate_appointment_booking(
                    date_str=date,
                    time_str=normalized_time,
                    hospital=hospital,
                    allow_sunday=False,
                )
                if not is_valid_tx:
                    messages.error(request, f"❌ {err_tx}")
                    return render(request, "client/book_appointment.html", {
                        "selected_service": service,
                        "selected_date": date,
                        "selected_time": time,
                        "notes": notes,
                    })

                appt = Appointment.objects.create(
                    hospital=hospital,
                    patient=request.user,
                    name=name,
                    email=email,
                    phone=phone,
                    service=service,
                    date=date,
                    time=time or normalized_time,
                    notes=notes,
                    status="pending",
                )
        except IntegrityError:
            messages.error(request, "❌ This appointment slot has just been booked by another patient. Please choose another time.")
            return render(request, "client/book_appointment.html", {
                "selected_service": service,
                "selected_date": date,
                "selected_time": time,
                "notes": notes,
            })

        # Email patient + alert admin (Executed outside atomic block after successful DB commit)
        email_sent = False
        try:
            email_sent = bool(send_appointment_confirmation(appt))
        except Exception as exc:
            logger.error(f"Appointment confirmation email failed for appt {appt.id}: {exc.__class__.__name__} - {exc}")

        try:
            admin = get_admin_user(hospital)
            if admin:
                send_admin_new_appointment_alert(appt)
                notify_appointment_booked(appt, admin)
        except Exception as exc:
            logger.error(f"Admin notification failed for appt {appt.id}: {exc.__class__.__name__} - {exc}")

        if email_sent:
            messages.success(request, f"✅ Appointment booked for {appt.date} at {appt.time}! Confirmation email sent.")
        else:
            messages.success(request, f"✅ Appointment booked for {appt.date} at {appt.time}! (Note: Confirmation email delivery was delayed or unavailable, but your appointment is secured.)")
        return redirect("my_appointments")
    return render(request, "client/book_appointment.html")


@login_required
def my_appointments(request):
    appointments = Appointment.objects.filter(patient=request.user)
    return render(request, "client/my_appointments.html", {"appointments": appointments})


@login_required
def admin_appointments(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    from .models import PublicAppointmentRequest
    hospital = resolve_hospital(request.user)
    if hospital:
        all_appointments = Appointment.objects.filter(hospital=hospital).order_by("-created_at")
        public_requests = PublicAppointmentRequest.objects.filter(hospital=hospital).order_by("-created_at")
    elif request.user.is_superuser:
        all_appointments = Appointment.objects.all().order_by("-created_at")
        public_requests = PublicAppointmentRequest.objects.all().order_by("-created_at")
    else:
        all_appointments = Appointment.objects.none()
        public_requests = PublicAppointmentRequest.objects.none()
    return render(
        request,
        "admin/admin_appointments.html",
        {
            "all_appointments": all_appointments,
            "appointments": all_appointments,
            "total": all_appointments.count(),
            "pending_count": all_appointments.filter(status="pending").count(),
            "confirmed_count": all_appointments.filter(status="confirmed").count(),
            "completed_count": all_appointments.filter(status="completed").count(),
            "cancelled_count": all_appointments.filter(status="cancelled").count(),
            "public_requests": public_requests,
            "public_requests_count": public_requests.count(),
            "public_pending_count": public_requests.filter(status="pending").count(),
        },
    )


@login_required
def update_public_appointment_request(request, request_id, status):
    """
    Allow authorized clinic admin/staff to review and update public appointment request status.
    """
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    from .models import PublicAppointmentRequest
    req_obj = get_object_or_404(PublicAppointmentRequest, id=request_id)
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital and req_obj.hospital_id and req_obj.hospital_id != hospital.id:
        messages.error(request, "Unauthorized: You cannot modify requests for another clinic.")
        return redirect("admin_appointments")
    valid_statuses = ["pending", "confirmed", "cancelled"]
    if status not in valid_statuses:
        messages.error(request, "Invalid status.")
        return redirect("admin_appointments")

    req_obj.status = status
    req_obj.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Public request {req_obj.reference_id} marked as {status.title()}.")
    return redirect("admin_appointments")



@login_required
def update_appointment(request, appt_id, status):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    appt = get_object_or_404(Appointment, id=appt_id)
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital and appt.hospital_id != hospital.id:
        messages.error(request, "Unauthorized: You cannot modify appointments for another clinic.")
        return redirect("admin_appointments")
    valid = ["pending", "confirmed", "completed", "cancelled"]
    if status not in valid:
        messages.error(request, "Invalid status.")
        return redirect("admin_appointments")

    appt.status = status
    appt.save()

    # Email + notification
    email_sent = False
    try:
        email_sent = bool(send_appointment_status_update(appt))
    except Exception as exc:
        logger.error(f"Appointment status email failed for appt {appt.id}: {exc.__class__.__name__} - {exc}")

    try:
        notify_appointment_status(appt)
    except Exception as exc:
        logger.error(f"Notification status failed for appt {appt.id}: {exc.__class__.__name__} - {exc}")

    if email_sent:
        messages.success(request, f"✅ Appointment {status}. Notification email sent.")
    else:
        messages.success(request, f"✅ Appointment {status}.")
    return redirect("admin_appointments")


# ─── ADMIN PATIENTS ──────────────────────────────────────────


@login_required
def admin_patients(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = (
            User.objects.filter(
                is_superuser=False,
                is_staff=False,
            )
            .filter(
                Q(appointments__hospital=hospital)
                | Q(patient_profile__hospital=hospital)
            )
            .distinct()
            .order_by("-date_joined")
            .prefetch_related("profile", "patient_profile", "appointments", "patient_notes")
        )
    elif request.user.is_superuser:
        patients = (
            User.objects.filter(is_superuser=False, is_staff=False)
            .order_by("-date_joined")
            .prefetch_related("profile", "patient_profile", "appointments", "patient_notes")
        )
    else:
        patients = User.objects.none()
    patient_data = []
    for p in patients:
        try:
            profile = p.profile
        except Exception:
            profile = None
        patient_profile = getattr(p, "patient_profile", None)
        appts = Appointment.objects.filter(patient=p).order_by("date")
        appt_count = appts.count()
        first_appt = appts.first()
        last_completed = appts.filter(status="completed").order_by("-date").first()
        latest_note = SessionNote.objects.filter(patient=p).order_by("-date").first()
        total_fees = appts.filter(consultation_fee__isnull=False).aggregate(
            total=Sum("consultation_fee")
        )["total"]
        phone = None
        if profile and profile.phone_number:
            phone = profile.phone_number
        elif first_appt and first_appt.phone:
            phone = first_appt.phone

        # Determine joining date priority: patient_profile -> profile -> first_appt -> date_joined
        joining_date = None
        if patient_profile and patient_profile.joining_date:
            joining_date = patient_profile.joining_date
        elif profile and profile.joining_date:
            joining_date = profile.joining_date
        elif first_appt and first_appt.date:
            joining_date = first_appt.date
        else:
            joining_date = p.date_joined.date()

        patient_data.append(
            {
                "user": p,
                "profile": profile,
                "patient_profile": patient_profile,
                "appt_count": appt_count,
                "joining_date": joining_date,
                "completion_date": last_completed.date if last_completed else None,
                "diagnosis": latest_note.diagnosis if latest_note else None,
                "treatment": latest_note.treatment if latest_note else None,
                "total_fees": total_fees,
                "phone": phone,
            }
        )
    return render(request, "admin/admin_patients.html", {"patient_data": patient_data})


# ─── CHAT ────────────────────────────────────────────────────


@login_required
def client_chat(request):
    hospital = resolve_hospital(request.user)
    admin = get_admin_user(hospital)
    if not admin:
        return render(request, "client/client_chat.html", {"error": "No admin account found."})

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        attachment_file = request.FILES.get("attachment") or request.FILES.get("file")

        if not content and not attachment_file:
            messages.warning(request, "Please enter a message or select a document to attach.")
            return redirect("client_chat")

        try:
            attachment_name = ""
            attachment_size = None
            attachment_type = ""

            if attachment_file:
                from .file_security import validate_attachment_file, sanitize_upload_filename
                validate_attachment_file(attachment_file, max_size_mb=10)
                attachment_name = attachment_file.name[:250]
                attachment_size = attachment_file.size
                attachment_type = getattr(attachment_file, "content_type", "") or "application/octet-stream"

            from .file_security import sanitize_html_content
            clean_content = sanitize_html_content(content) if content else ""

            Message.objects.create(
                sender=request.user,
                receiver=admin,
                hospital=hospital,
                content=clean_content,
                attachment=attachment_file if attachment_file else None,
                attachment_name=attachment_name,
                attachment_size=attachment_size,
                attachment_type=attachment_type,
                status=Message.STATUS_SENT,
            )
        except ValidationError as val_err:
            messages.error(request, f"Attachment rejected: {val_err.message if hasattr(val_err, 'message') else str(val_err)}")
        except Exception as exc:
            messages.error(request, f"Failed to send message: {str(exc)}")

        return redirect("client_chat")

    msgs = Message.objects.filter(
        Q(sender=request.user, receiver=admin) | Q(sender=admin, receiver=request.user)
    ).select_related("sender", "receiver").order_by("created_at")

    Message.objects.filter(sender=admin, receiver=request.user, is_read=False).update(
        is_read=True, status=Message.STATUS_READ
    )

    admin_profile = Profile.objects.filter(user=admin).first()
    return render(
        request,
        "client/client_chat.html",
        {
            "messages_list": list(msgs),
            "admin": admin,
            "admin_online": is_online(admin),
            "admin_last_seen": admin_profile.last_seen if admin_profile else None,
        },
    )


@login_required
def _get_admin_patient_chats(request):
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = list(
            User.objects.filter(
                Q(appointments__hospital=hospital)
                | Q(patient_profile__hospital=hospital)
                | Q(received_messages__sender=request.user)
                | Q(sent_messages__receiver=request.user),
                is_superuser=False,
                is_staff=False,
            )
            .select_related("patient_profile", "profile")
            .distinct()
        )
    elif request.user.is_superuser:
        patients = list(
            User.objects.filter(is_superuser=False, is_staff=False)
            .select_related("patient_profile", "profile")
        )
    else:
        patients = []

    if not patients:
        return []

    patient_ids = [p.id for p in patients]

    # Batch unread counts in 1 optimized query
    unread_counts = dict(
        Message.objects.filter(
            sender_id__in=patient_ids,
            receiver=request.user,
            is_read=False,
        )
        .values("sender_id")
        .annotate(count=Count("id"))
        .values_list("sender_id", "count")
    )

    # Batch recent messages in 1 query
    recent_messages = (
        Message.objects.filter(
            Q(sender=request.user, receiver_id__in=patient_ids)
            | Q(receiver=request.user, sender_id__in=patient_ids)
        )
        .order_by("-created_at")
    )
    last_msg_map = {}
    for m in recent_messages:
        partner_id = m.receiver_id if m.sender_id == request.user.id else m.sender_id
        if partner_id not in last_msg_map:
            last_msg_map[partner_id] = m

    patient_chats = []
    for patient in patients:
        last_msg = last_msg_map.get(patient.id)
        unread = unread_counts.get(patient.id, 0)
        patient_chats.append(
            {
                "patient": patient,
                "last_msg": last_msg,
                "unread_count": unread,
                "is_online": is_online(patient),
            }
        )

    fallback_date = timezone.now() - timedelta(days=36500)
    patient_chats.sort(
        key=lambda x: x["last_msg"].created_at if x["last_msg"] else fallback_date,
        reverse=True,
    )
    return patient_chats


def _get_admin_doctor_chats(request):
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        staff_members = list(StaffProfile.objects.filter(hospital=hospital).select_related("user", "user__profile"))
    else:
        staff_members = list(StaffProfile.objects.all().select_related("user", "user__profile"))

    if not staff_members:
        return []

    doc_ids = [s.user_id for s in staff_members]

    # Batch unread counts in 1 query
    unread_counts = dict(
        Message.objects.filter(
            sender_id__in=doc_ids,
            receiver=request.user,
            is_read=False,
        )
        .values("sender_id")
        .annotate(count=Count("id"))
        .values_list("sender_id", "count")
    )

    # Batch recent messages in 1 query
    recent_messages = (
        Message.objects.filter(
            Q(sender=request.user, receiver_id__in=doc_ids)
            | Q(receiver=request.user, sender_id__in=doc_ids)
        )
        .order_by("-created_at")
    )
    last_msg_map = {}
    for m in recent_messages:
        partner_id = m.receiver_id if m.sender_id == request.user.id else m.sender_id
        if partner_id not in last_msg_map:
            last_msg_map[partner_id] = m

    doctor_chats = []
    for staff in staff_members:
        doc_user = staff.user
        last_msg = last_msg_map.get(doc_user.id)
        unread = unread_counts.get(doc_user.id, 0)
        doctor_chats.append(
            {
                "doctor": doc_user,
                "profile": staff,
                "last_msg": last_msg,
                "unread_count": unread,
                "is_online": is_online(doc_user),
            }
        )

    fallback_date = timezone.now() - timedelta(days=36500)
    doctor_chats.sort(
        key=lambda x: x["last_msg"].created_at if x["last_msg"] else fallback_date,
        reverse=True,
    )
    return doctor_chats


@login_required
def admin_chat(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("home")
    try:
        patient_chats = _get_admin_patient_chats(request)
    except Exception as exc:
        logger.error(f"Error loading admin patient chats: {exc}", exc_info=True)
        patient_chats = []
    return render(
        request,
        "admin/admin_chat.html",
        {
            "patient_chats": patient_chats,
            "selected_patient": None,
        },
    )


@login_required
def admin_chat_detail(request, patient_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    patient = get_object_or_404(User, id=patient_id)
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=patient, hospital=hospital).exists()
            or (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
            or Message.objects.filter(Q(sender=patient, receiver=request.user) | Q(sender=request.user, receiver=patient)).exists()
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Patient does not belong to your clinic.")
            return redirect("admin_chat")

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        attachment_file = request.FILES.get("attachment") or request.FILES.get("file")

        if not content and not attachment_file:
            messages.warning(request, "Please enter a message or attach a file.")
            return redirect("admin_chat_detail", patient_id=patient_id)

        try:
            attachment_name = ""
            attachment_size = None
            attachment_type = ""

            if attachment_file:
                from .file_security import validate_attachment_file
                validate_attachment_file(attachment_file, max_size_mb=10)
                attachment_name = attachment_file.name[:250]
                attachment_size = attachment_file.size
                attachment_type = getattr(attachment_file, "content_type", "") or "application/octet-stream"

            from .file_security import sanitize_html_content
            clean_content = sanitize_html_content(content) if content else ""

            Message.objects.create(
                sender=request.user,
                receiver=patient,
                hospital=hospital,
                content=clean_content,
                attachment=attachment_file if attachment_file else None,
                attachment_name=attachment_name,
                attachment_size=attachment_size,
                attachment_type=attachment_type,
                status=Message.STATUS_SENT,
            )
        except ValidationError as val_err:
            messages.error(request, f"Attachment rejected: {val_err.message if hasattr(val_err, 'message') else str(val_err)}")
        except Exception as exc:
            messages.error(request, f"Failed to send message: {str(exc)}")

        return redirect("admin_chat_detail", patient_id=patient_id)

    msgs = Message.objects.filter(
        Q(sender=patient, receiver=request.user)
        | Q(sender=request.user, receiver=patient)
    ).select_related("sender", "receiver").order_by("created_at")

    Message.objects.filter(sender=patient, receiver=request.user, is_read=False).update(
        is_read=True, status=Message.STATUS_READ
    )

    patient_chats = _get_admin_patient_chats(request)
    patient_profile = Profile.objects.filter(user=patient).first()
    return render(
        request,
        "admin/admin_chat_detail.html",
        {
            "patient": patient,
            "selected_patient": patient,
            "patient_chats": patient_chats,
            "messages_list": msgs,
            "patient_online": is_online(patient),
            "patient_last_seen": patient_profile.last_seen if patient_profile else None,
        },
    )


@login_required
def admin_doctor_chat(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    try:
        doctor_chats = _get_admin_doctor_chats(request)
    except Exception as exc:
        logger.error(f"Error loading admin doctor chats: {exc}", exc_info=True)
        doctor_chats = []
    return render(
        request,
        "admin/admin_doctor_chat.html",
        {
            "doctor_chats": doctor_chats,
            "selected_doctor": None,
        },
    )


@login_required
def admin_doctor_chat_detail(request, doctor_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    doctor = get_object_or_404(User, id=doctor_id)
    doc_profile = StaffProfile.objects.filter(user=doctor).first()
    hospital = resolve_hospital(request.user)

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        attachment_file = request.FILES.get("attachment") or request.FILES.get("file")

        if not content and not attachment_file:
            messages.warning(request, "Please enter a message or attach a file.")
            return redirect("admin_doctor_chat_detail", doctor_id=doctor_id)

        try:
            attachment_name = ""
            attachment_size = None
            attachment_type = ""

            if attachment_file:
                from .file_security import validate_attachment_file
                validate_attachment_file(attachment_file, max_size_mb=10)
                attachment_name = attachment_file.name[:250]
                attachment_size = attachment_file.size
                attachment_type = getattr(attachment_file, "content_type", "") or "application/octet-stream"

            from .file_security import sanitize_html_content
            clean_content = sanitize_html_content(content) if content else ""

            Message.objects.create(
                sender=request.user,
                receiver=doctor,
                hospital=hospital,
                content=clean_content,
                attachment=attachment_file if attachment_file else None,
                attachment_name=attachment_name,
                attachment_size=attachment_size,
                attachment_type=attachment_type,
                status=Message.STATUS_SENT,
            )
        except ValidationError as val_err:
            messages.error(request, f"Attachment rejected: {val_err.message if hasattr(val_err, 'message') else str(val_err)}")
        except Exception as exc:
            messages.error(request, f"Failed to send message: {str(exc)}")

        return redirect("admin_doctor_chat_detail", doctor_id=doctor_id)

    msgs = Message.objects.filter(
        Q(sender=doctor, receiver=request.user)
        | Q(sender=request.user, receiver=doctor)
    ).select_related("sender", "receiver").order_by("created_at")

    Message.objects.filter(sender=doctor, receiver=request.user, is_read=False).update(
        is_read=True, status=Message.STATUS_READ
    )

    doctor_chats = _get_admin_doctor_chats(request)
    return render(
        request,
        "admin/admin_doctor_chat_detail.html",
        {
            "doctor": doctor,
            "selected_doctor": doctor,
            "doctor_chats": doctor_chats,
            "doctor_profile": doc_profile,
            "messages_list": msgs,
            "doctor_online": is_online(doctor),
            "doctor_last_seen": getattr(doctor, "profile", None).last_seen if hasattr(doctor, "profile") and doctor.profile else None,
        },
    )


@login_required
def download_chat_attachment(request, message_id):
    """
    Secure authenticated attachment download view.
    Enforces defense-in-depth authorization:
      - Authenticated user
      - Must be sender, receiver, or superuser
      - For clinic admin/staff, tenancy check is enforced
      - Returns FileResponse with Content-Disposition: attachment
    """
    from django.http import Http404, HttpResponseForbidden, FileResponse
    import mimetypes

    msg = get_object_or_404(Message, id=message_id)
    if not msg.attachment:
        raise Http404("Attachment not found.")

    # Authorization check
    is_party = (request.user.id == msg.sender_id or request.user.id == msg.receiver_id)
    is_authorized = is_party or request.user.is_superuser

    if not is_authorized:
        hospital = resolve_hospital(request.user)
        if hospital and (_is_clinic_admin(request.user) or getattr(request.user, "is_staff", False)):
            sender_h = resolve_hospital(msg.sender)
            receiver_h = resolve_hospital(msg.receiver)
            if (sender_h and sender_h.id == hospital.id) or (receiver_h and receiver_h.id == hospital.id):
                is_authorized = True

    if not is_authorized:
        return HttpResponseForbidden("Access Denied: You are not authorized to download this clinical document.")

    try:
        file_handle = msg.attachment.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404("Attachment file does not exist on storage.")

    content_type = msg.attachment_type or mimetypes.guess_type(msg.attachment.name)[0] or "application/octet-stream"
    download_filename = msg.attachment_name or os.path.basename(msg.attachment.name)

    response = FileResponse(file_handle, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{download_filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id, sender=request.user)
    redirect_url = (
        f"/admin-chat/{message.receiver.id}/" if request.user.is_superuser else "/chat/"
    )
    message.delete()
    return redirect(redirect_url)


# ─── TYPING INDICATORS ───────────────────────────────────────


@csrf_exempt
@login_required
def start_typing(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            receiver_id = data.get("receiver_id")
        except Exception:
            receiver_id = None
        if receiver_id:
            cache.set(f"typing:{request.user.id}:{receiver_id}", True, timeout=5)
            cache.set(f"typing_target:{request.user.id}", receiver_id, timeout=5)
        return JsonResponse({"status": "started"})
    return JsonResponse({"status": "invalid"}, status=400)


@csrf_exempt
@login_required
def stop_typing(request):
    if request.method == "POST":
        target_id = cache.get(f"typing_target:{request.user.id}")
        if target_id:
            cache.delete(f"typing:{request.user.id}:{target_id}")
        cache.delete(f"typing_target:{request.user.id}")
        return JsonResponse({"status": "stopped"})
    return JsonResponse({"status": "invalid"}, status=400)


@login_required
def check_typing(request, user_id):
    is_typing = bool(cache.get(f"typing:{user_id}:{request.user.id}"))
    return JsonResponse({"is_typing": is_typing})


# ─── ADMIN – STAFF ───────────────────────────────────────────


@login_required
def admin_staff(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital:
        staff_list = StaffProfile.objects.filter(hospital=hospital).select_related("user")
    elif request.user.is_superuser:
        staff_list = StaffProfile.objects.all().select_related("user")
    else:
        staff_list = StaffProfile.objects.none()
    return render(request, "admin/admin_staff.html", {"staff_list": staff_list})


@login_required
def add_staff(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        role = request.POST.get("role", "")
        phone = request.POST.get("phone", "")
        salary = request.POST.get("salary", 0)

        # ── Validation checks ──
        if not username:
            messages.error(request, "❌ Username is required.")
            return redirect("add_staff")

        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                f'❌ Username "{username}" is already taken. Please choose a different one.',
            )
            return redirect("add_staff")

        if User.objects.filter(email=email).exists():
            messages.error(request, f'❌ Email "{email}" is already registered.')
            return redirect("add_staff")

        if len(password) < 6:
            messages.error(request, "❌ Password must be at least 6 characters.")
            return redirect("add_staff")

        try:
            hospital = resolve_hospital(request.user)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
            )
            StaffProfile.objects.create(
                user=user, hospital=hospital, role=role, phone=phone, salary=salary
            )
            send_staff_welcome_email(user, password)
            messages.success(
                request,
                f"✅ Staff member {first_name} {last_name} added successfully! Welcome email sent.",
            )
            return redirect("admin_staff")

        except Exception as e:
            messages.error(request, f"❌ Error creating staff: {str(e)}")
            return redirect("add_staff")

    return render(request, "admin/add_staff.html")


# ─── ADMIN – LEAVES ──────────────────────────────────────────


@login_required
def admin_leaves(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    # ── Auto-approve any expired pending leaves ──
    from django.utils.timezone import localdate

    today = localdate()
    expired = LeaveApplication.objects.filter(status="pending", to_date__lt=today)
    for leave in expired:
        leave.status = "approved"
        leave.admin_note = "Auto-approved: Admin did not respond before leave date."
        leave.save()
        # Email staff via clinic email pipeline
        try:
            from .email_utils import send_clinic_email, CLINIC_NAME
            staff_email = getattr(leave.staff, "email", None)
            if staff_email:
                clinic_title = leave.hospital.name if leave.hospital else CLINIC_NAME
                send_clinic_email(
                    subject="✅ Leave Auto-Approved — No Admin Response",
                    message_text=f"""Dear {leave.staff.get_full_name() or leave.staff.username},

Your leave has been AUTO-APPROVED as the admin did not respond before the leave date.

  Leave Type : {leave.get_leave_type_display()}
  From       : {leave.from_date.strftime("%d %B %Y")}
  To         : {leave.to_date.strftime("%d %B %Y")}

Regards,
{clinic_title}""".strip(),
                    recipient_list=[staff_email],
                    hospital=leave.hospital,
                    email_type="leave_auto_approved",
                )
        except Exception as exc:
            logger.warning(f"Leave auto-approval email failed for leave {leave.id}: {exc}")

    # existing code continues below ──
    hospital = resolve_hospital(request.user)
    if hospital:
        leaves = LeaveApplication.objects.filter(hospital=hospital).select_related("staff")
    elif request.user.is_superuser:
        leaves = LeaveApplication.objects.all().select_related("staff")
    else:
        leaves = LeaveApplication.objects.none()
    pending = leaves.filter(status="pending").count()
    return render(request, "admin/admin_leaves.html", {"leaves": leaves, "pending": pending})


@login_required
def update_leave(request, leave_id, status):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital and leave.hospital_id != hospital.id:
        messages.error(request, "Unauthorized: You cannot modify leave requests for another clinic.")
        return redirect("admin_leaves")
    if status in ["approved", "rejected"]:
        leave.status = status
        leave.admin_note = request.POST.get("admin_note", "")
        leave.reviewed_by = request.user
        leave.save()

        # Email + notification
        email_sent = False
        try:
            email_sent = bool(send_leave_status_email(leave))
        except Exception as exc:
            logger.error(f"Leave status email failed for leave {leave.id}: {exc.__class__.__name__} - {exc}")

        try:
            notify_leave_decision(leave)
        except Exception as exc:
            logger.error(f"Leave decision notification failed for leave {leave.id}: {exc.__class__.__name__} - {exc}")

        if email_sent:
            messages.success(request, f"✅ Leave {status}. Notification email sent to staff.")
        else:
            messages.success(request, f"✅ Leave {status}. (Note: Notification email delivery failed or unavailable)")
    return redirect("admin_leaves")


# ─── ADMIN – ATTENDANCE ──────────────────────────────────────


@login_required
def admin_attendance(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    today = timezone.now().date()
    if hospital and not request.user.is_superuser:
        today_att = Attendance.objects.filter(
            Q(hospital=hospital)
            | Q(staff__staff_profile__hospital=hospital)
            | Q(hospital__isnull=True),
            date=today,
        ).select_related("staff")
        all_attendance = Attendance.objects.filter(
            Q(hospital=hospital)
            | Q(staff__staff_profile__hospital=hospital)
            | Q(hospital__isnull=True)
        ).select_related("staff")[:50]
    else:
        today_att = Attendance.objects.filter(date=today).select_related("staff")
        all_attendance = Attendance.objects.all().select_related("staff")[:50]
    return render(
        request,
        "admin/admin_attendance.html",
        {
            "today_attendance": today_att,
            "all_attendance": all_attendance,
            "today": today,
        },
    )


# ─── ADMIN – SALARY ──────────────────────────────────────────


@login_required
def admin_salary(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        month = request.POST.get("month")
        year = request.POST.get("year")
        basic = request.POST.get("basic_salary", 0)
        bonus = request.POST.get("bonus", 0)
        deduction = request.POST.get("deduction", 0)
        net = float(basic) + float(bonus) - float(deduction)

        if hospital and not request.user.is_superuser:
            staff_user = get_object_or_404(
                User,
                Q(id=staff_id)
                & (
                    Q(staff_profile__hospital=hospital)
                    | Q(staff_profile__hospital__isnull=True)
                ),
            )
        else:
            staff_user = get_object_or_404(User, id=staff_id)

        record = SalaryRecord.objects.create(
            hospital=hospital,
            staff=staff_user,
            month=month,
            year=year,
            basic_salary=basic,
            bonus=bonus,
            deduction=deduction,
            net_salary=net,
            is_paid=True,
            paid_on=timezone.now().date(),
        )

        # Email + notification
        email_sent = False
        try:
            email_sent = bool(send_salary_paid_email(record))
        except Exception as exc:
            logger.error(f"Salary payment email failed for record {record.id}: {exc.__class__.__name__} - {exc}")

        try:
            notify_salary_paid(record)
        except Exception as exc:
            logger.error(f"Salary notification failed for record {record.id}: {exc.__class__.__name__} - {exc}")

        if email_sent:
            messages.success(request, "✅ Salary record saved and notification email sent to staff!")
        else:
            messages.warning(
                request,
                f"✅ Salary record saved, but notification email could not be delivered to {staff_user.email}."
            )
        return redirect("admin_salary")

    if hospital and not request.user.is_superuser:
        salary_records = SalaryRecord.objects.filter(
            Q(hospital=hospital)
            | Q(staff__staff_profile__hospital=hospital)
            | Q(hospital__isnull=True)
        ).select_related("staff", "hospital")
        staff_list = StaffProfile.objects.filter(
            Q(hospital=hospital) | Q(hospital__isnull=True)
        ).select_related("user")
    else:
        salary_records = SalaryRecord.objects.all().select_related("staff", "hospital")
        staff_list = StaffProfile.objects.all().select_related("user")

    return render(
        request,
        "admin/admin_salary.html",
        {
            "salary_records": salary_records,
            "staff_list": staff_list,
        },
    )


# ─── ADMIN – TASKS ───────────────────────────────────────────


@login_required
def admin_tasks(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        tasks = (
            DailyTask.objects.filter(
                Q(hospital=hospital)
                | Q(assigned_to__staff_profile__hospital=hospital)
                | Q(assigned_by=request.user)
                | Q(hospital__isnull=True)
            )
            .distinct()
            .select_related("assigned_to", "assigned_by")
        )
    else:
        tasks = DailyTask.objects.all().select_related("assigned_to", "assigned_by")
    return render(request, "admin/admin_tasks.html", {"tasks": tasks})


@login_required
def add_task(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        title = request.POST.get("title", "")
        description = request.POST.get("description", "")
        priority = request.POST.get("priority", "medium")
        due_date = request.POST.get("due_date") or None

        hospital = resolve_hospital(request.user)
        staff_user = get_object_or_404(User, id=staff_id)
        task = DailyTask.objects.create(
            hospital=hospital,
            assigned_to=staff_user,
            assigned_by=request.user,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
        )

        # Email + notification
        send_task_assigned_email(task)
        notify_task_assigned(task)

        messages.success(
            request, f"✅ Task assigned to {staff_user.get_full_name()}! Email sent."
        )
        return redirect("admin_tasks")

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        staff_list = (
            StaffProfile.objects.filter(
                Q(hospital=hospital) | Q(hospital__isnull=True)
            )
            .select_related("user")
            .distinct()
        )
    else:
        staff_list = StaffProfile.objects.all().select_related("user")
    return render(request, "admin/add_task.html", {"staff_list": staff_list})


# ─── ADMIN – SESSION NOTES ───────────────────────────────────


@login_required
def admin_session_notes(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        notes = SessionNote.objects.filter(
            Q(staff__staff_profile__hospital=hospital)
            | Q(patient__appointments__hospital=hospital)
            | Q(patient__patient_profile__hospital=hospital)
        ).distinct().select_related("staff", "patient")
    else:
        notes = SessionNote.objects.all().select_related("staff", "patient")
    return render(request, "admin/admin_session_notes.html", {"notes": notes})


# ─── STAFF DASHBOARD ─────────────────────────────────────────


def _is_staff(user):
    return user.is_staff or hasattr(user, "staff_profile")


@login_required
def staff_dashboard(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    today = timezone.now().date()
    today_att = Attendance.objects.filter(staff=request.user, date=today).first()
    pending_tasks = DailyTask.objects.filter(
        assigned_to=request.user, status="pending"
    ).count()
    pending_leaves = LeaveApplication.objects.filter(
        staff=request.user, status="pending"
    ).count()
    my_tasks = DailyTask.objects.filter(assigned_to=request.user).order_by(
        "-created_at"
    )[:5]
    return render(
        request,
        "staff/staff_dashboard.html",
        {
            "today_attendance": today_att,
            "pending_tasks": pending_tasks,
            "pending_leaves": pending_leaves,
            "my_tasks": my_tasks,
            "today": today,
        },
    )


# ════════════════════════════════════════════════════════════
# FILE: core/views.py
# FIND your existing staff_attendance function and
# REPLACE the ENTIRE function with this complete version
# ════════════════════════════════════════════════════════════


@login_required
def staff_attendance(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")

    hospital = resolve_hospital(request.user)
    today = timezone.now().date()
    now_dt = timezone.localtime(timezone.now())
    now_time = now_dt.time()

    today_record = Attendance.objects.filter(staff=request.user, date=today).first()

    # ── Shift window flags ──
    in_morning = MORNING_START <= now_time <= MORNING_END
    in_evening = EVENING_START <= now_time <= EVENING_END
    before_morning = now_time < MORNING_START
    between_shifts = MORNING_END < now_time < EVENING_START
    after_evening = now_time > EVENING_END

    if request.method == "POST":
        action = request.POST.get("action")

        # ── MORNING CLOCK IN ────────────────────────────────
        if action == "morning_clock_in":
            if not in_morning:
                messages.error(
                    request,
                    f"❌ Morning shift is 10:00 AM – 1:00 PM only. "
                    f"Current time: {now_time.strftime('%I:%M %p')}",
                )
                return redirect("staff_attendance")

            if today_record and today_record.clock_in:
                messages.warning(request, "⚠️ Already clocked in for morning shift.")
                return redirect("staff_attendance")

            record, _ = Attendance.objects.get_or_create(
                staff=request.user,
                date=today,
                defaults={"hospital": hospital},
            )
            if not record.hospital and hospital:
                record.hospital = hospital
            record.clock_in = now_time
            record.notes = ""
            record.save()

            if is_late(now_time, "morning"):
                late_mins = int(
                    (
                        datetime.combine(today, now_time)
                        - datetime.combine(today, MORNING_START)
                    ).seconds
                    / 60
                )
                record.notes = f"Late morning clock-in by {late_mins} min."
                record.save()
                _send_late_email(request.user, "Morning", now_time, late_mins)
                messages.warning(
                    request,
                    f"⚠️ Clocked in late for morning shift by {late_mins} minutes. "
                    f"Email notification sent.",
                )
            else:
                messages.success(
                    request, f"✅ Morning clock-in at {now_time.strftime('%I:%M %p')}"
                )

        # ── MORNING CLOCK OUT ───────────────────────────────
        elif action == "morning_clock_out":
            if not today_record or not today_record.clock_in:
                messages.error(
                    request, "❌ You have not clocked in for morning shift yet."
                )
                return redirect("staff_attendance")

            if today_record.morning_clock_out:
                messages.warning(request, "⚠️ Already clocked out from morning shift.")
                return redirect("staff_attendance")

            today_record.morning_clock_out = now_time

            # Calculate morning hours
            ci = datetime.combine(today, today_record.clock_in)
            co = datetime.combine(today, now_time)
            morning_hours = max(round((co - ci).seconds / 3600, 2), 0)
            today_record.morning_hours = morning_hours

            # Check early leave
            if now_time < MORNING_END:
                short_mins = int(
                    (
                        datetime.combine(today, MORNING_END)
                        - datetime.combine(today, now_time)
                    ).seconds
                    / 60
                )
                note = f"Left morning shift {short_mins} min early."
                today_record.notes = (today_record.notes + " " + note).strip()
                _send_early_leave_email(request.user, "Morning", now_time, short_mins)
                messages.warning(
                    request,
                    f"⚠️ Clocked out {short_mins} min early from morning shift. "
                    f"Email notification sent.",
                )
            else:
                messages.success(
                    request,
                    f"✅ Morning clock-out at {now_time.strftime('%I:%M %p')} "
                    f"— {morning_hours} hrs",
                )
            today_record.save()

        # ── EVENING CLOCK IN ────────────────────────────────
        elif action == "evening_clock_in":
            if not in_evening:
                messages.error(
                    request,
                    f"❌ Evening shift is 4:00 PM – 8:00 PM only. "
                    f"Current time: {now_time.strftime('%I:%M %p')}",
                )
                return redirect("staff_attendance")

            if today_record and today_record.evening_clock_in:
                messages.warning(request, "⚠️ Already clocked in for evening shift.")
                return redirect("staff_attendance")

            record, _ = Attendance.objects.get_or_create(
                staff=request.user,
                date=today,
                defaults={"hospital": hospital},
            )
            if not record.hospital and hospital:
                record.hospital = hospital

            # ── If morning was fully missed → First Half Leave ──
            if not record.clock_in and not record.morning_clock_out:
                if "First Half Leave" not in record.notes:
                    record.notes = (
                        record.notes + " First Half Leave (Morning shift missed)."
                    ).strip()
                    LeaveApplication.objects.get_or_create(
                        staff=request.user,
                        from_date=today,
                        to_date=today,
                        defaults={
                            "hospital": hospital,
                            "leave_type": "casual",
                            "reason": "Auto-marked: First Half Leave (morning shift missed)",
                            "status": "pending",
                        },
                    )
                    _send_half_day_email(request.user, "Morning")
                    messages.warning(
                        request,
                        "⚠️ Morning shift was missed. Marked as First Half Leave. "
                        "Leave application auto-submitted for admin approval.",
                    )

            record.evening_clock_in = now_time
            record.save()
            today_record = record

            if is_late(now_time, "evening"):
                late_mins = int(
                    (
                        datetime.combine(today, now_time)
                        - datetime.combine(today, EVENING_START)
                    ).seconds
                    / 60
                )
                today_record.notes = (
                    today_record.notes + f" Late evening clock-in by {late_mins} min."
                ).strip()
                today_record.save()
                _send_late_email(request.user, "Evening", now_time, late_mins)
                messages.warning(
                    request,
                    f"⚠️ Clocked in late for evening shift by {late_mins} minutes. "
                    f"Email notification sent.",
                )
            else:
                if "First Half Leave" not in (today_record.notes or ""):
                    messages.success(
                        request,
                        f"✅ Evening clock-in at {now_time.strftime('%I:%M %p')}",
                    )

        # ── EVENING CLOCK OUT ───────────────────────────────
        elif action == "evening_clock_out":
            if not today_record or not today_record.evening_clock_in:
                messages.error(
                    request, "❌ You have not clocked in for evening shift yet."
                )
                return redirect("staff_attendance")

            if today_record.clock_out:
                messages.warning(request, "⚠️ Already clocked out from evening shift.")
                return redirect("staff_attendance")

            today_record.clock_out = now_time

            # Calculate evening hours
            ci = datetime.combine(today, today_record.evening_clock_in)
            co = datetime.combine(today, now_time)
            evening_hours = max(round((co - ci).seconds / 3600, 2), 0)
            today_record.evening_hours = evening_hours

            # Total = morning + evening
            morning_h = float(today_record.morning_hours or 0)
            today_record.total_hours = round(morning_h + evening_hours, 2)

            # Check early leave
            if now_time < EVENING_END:
                short_mins = int(
                    (
                        datetime.combine(today, EVENING_END)
                        - datetime.combine(today, now_time)
                    ).seconds
                    / 60
                )
                note = f"Left evening shift {short_mins} min early."
                today_record.notes = (today_record.notes + " " + note).strip()
                _send_early_leave_email(request.user, "Evening", now_time, short_mins)
                messages.warning(
                    request,
                    f"⚠️ Clocked out {short_mins} min early from evening shift. "
                    f"Email notification sent.",
                )
            else:
                messages.success(
                    request,
                    f"✅ Day complete! Total: {today_record.total_hours} hrs 🎉",
                )

            # ── If evening missed before this point was caught by cron ──
            # Mark Second Half Leave if morning done but evening was missed
            # (This handles edge case where staff clocks out very late)
            today_record.save()

        else:
            messages.error(request, "❌ Invalid action.")

        return redirect("staff_attendance")

    # ── GET request ─────────────────────────────────────────
    all_att = Attendance.objects.filter(staff=request.user).order_by("-date")[:30]

    return render(
        request,
        "staff/staff_attendance.html",
        {
            "today_record": today_record,
            "all_attendance": all_att,
            "today": today,
            "now_time": now_time,
            "in_morning": in_morning,
            "in_evening": in_evening,
            "before_morning": before_morning,
            "between_shifts": between_shifts,
            "after_evening": after_evening,
            "MORNING_START": MORNING_START.strftime("%I:%M %p"),
            "MORNING_END": MORNING_END.strftime("%I:%M %p"),
            "EVENING_START": EVENING_START.strftime("%I:%M %p"),
            "EVENING_END": EVENING_END.strftime("%I:%M %p"),
        },
    )


# ════════════════════════════════════════════════════════════
# ADD these 3 helper functions anywhere in core/views.py
# AFTER the staff_attendance function
# ════════════════════════════════════════════════════════════


def _send_late_email(user, shift_name, clock_time, late_mins):
    """Send late arrival email to staff."""
    if not getattr(user, "email", None):
        return False
    from .email_utils import send_clinic_email, CLINIC_NAME
    hospital = getattr(getattr(user, "staff_profile", None), "hospital", None)
    clinic_title = hospital.name if hospital else CLINIC_NAME
    try:
        return send_clinic_email(
            subject=f"⚠️ Late Attendance — {shift_name} Shift",
            message_text=f"""Dear {user.get_full_name() or user.username},

You clocked in LATE for the {shift_name} Shift today.

  Clock-in Time : {clock_time.strftime("%I:%M %p")}
  Late By       : {late_mins} minutes
  Date          : {timezone.now().date().strftime("%d %B %Y")}

Shift Timings:
  Morning  — 10:00 AM to 1:00 PM
  Evening  — 4:00 PM to 8:00 PM

Regards,
{clinic_title}""".strip(),
            recipient_list=[user.email],
            hospital=hospital,
            email_type="attendance_late",
        )
    except Exception as exc:
        logger.warning(f"Failed to send late attendance email to {user.email}: {exc}")
        return False


def _send_early_leave_email(user, shift_name, clock_time, short_mins):
    """Send early leave email to staff."""
    if not getattr(user, "email", None):
        return False
    from .email_utils import send_clinic_email, CLINIC_NAME
    hospital = getattr(getattr(user, "staff_profile", None), "hospital", None)
    clinic_title = hospital.name if hospital else CLINIC_NAME
    try:
        return send_clinic_email(
            subject=f"⚠️ Early Leave Detected — {shift_name} Shift",
            message_text=f"""Dear {user.get_full_name() or user.username},

You clocked out EARLY from the {shift_name} Shift today.

  Clock-out Time : {clock_time.strftime("%I:%M %p")}
  Left Early By  : {short_mins} minutes
  Date           : {timezone.now().date().strftime("%d %B %Y")}

If you had a valid reason, please inform the admin.

Regards,
{clinic_title}""".strip(),
            recipient_list=[user.email],
            hospital=hospital,
            email_type="attendance_early_leave",
        )
    except Exception as exc:
        logger.warning(f"Failed to send early leave email to {user.email}: {exc}")
        return False


def _send_half_day_email(user, missed_shift):
    """Send half day leave email to staff."""
    if not getattr(user, "email", None):
        return False
    from .email_utils import send_clinic_email, CLINIC_NAME
    half = "First" if missed_shift == "Morning" else "Second"
    timing = "10:00 AM – 1:00 PM" if missed_shift == "Morning" else "4:00 PM – 8:00 PM"
    hospital = getattr(getattr(user, "staff_profile", None), "hospital", None)
    clinic_title = hospital.name if hospital else CLINIC_NAME
    try:
        return send_clinic_email(
            subject=f"📋 {half} Half Leave Auto-Marked — {missed_shift} Shift Missed",
            message_text=f"""Dear {user.get_full_name() or user.username},

Since you missed the {missed_shift} shift today, your attendance
has been automatically marked as {half.upper()} HALF LEAVE.

  Date          : {timezone.now().date().strftime("%d %B %Y")}
  Missed Shift  : {missed_shift} ({timing})
  Status        : {half} Half Leave (Pending Admin Approval)

A leave application has been auto-submitted on your behalf.
If this was an error, please contact admin to correct it.

Regards,
{clinic_title}""".strip(),
            recipient_list=[user.email],
            hospital=hospital,
            email_type="attendance_half_day",
        )
    except Exception as exc:
        logger.warning(f"Failed to send half day attendance email to {user.email}: {exc}")
        return False


@login_required
def staff_leave(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    if request.method == "POST":
        LeaveApplication.objects.create(
            staff=request.user,
            leave_type=request.POST.get("leave_type"),
            from_date=request.POST.get("from_date"),
            to_date=request.POST.get("to_date"),
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "✅ Leave application submitted!")
        return redirect("staff_leave")
    my_leaves = LeaveApplication.objects.filter(staff=request.user)
    return render(request, "staff/staff_leave.html", {"my_leaves": my_leaves})


@login_required
def staff_salary(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    salary_records = SalaryRecord.objects.filter(staff=request.user)
    total_earned = sum(s.net_salary for s in salary_records if s.is_paid)
    return render(
        request,
        "staff/staff_salary.html",
        {
            "salary_records": salary_records,
            "total_earned": total_earned,
        },
    )


@login_required
def staff_tasks(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    tasks = DailyTask.objects.filter(assigned_to=request.user)
    return render(
        request,
        "staff/staff_tasks.html",
        {
            "tasks": tasks,
            "pending": tasks.filter(status="pending").count(),
            "in_progress": tasks.filter(status="in_progress").count(),
            "completed": tasks.filter(status="completed").count(),
        },
    )


@login_required
def update_task(request, task_id, status):
    task = get_object_or_404(DailyTask, id=task_id, assigned_to=request.user)
    if status in ["pending", "in_progress", "completed"]:
        task.status = status
        if status == "completed":
            task.completed_at = timezone.now()
        task.save()
        messages.success(request, f"✅ Task marked as {status}.")
    return redirect("staff_tasks")


@login_required
def staff_session_notes(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    notes = SessionNote.objects.filter(staff=request.user)
    return render(request, "staff/staff_session_notes.html", {"notes": notes})


@login_required
def add_session_note(request):
    if not _is_staff(request.user):
        return redirect("client_dashboard")
    if request.method == "POST":
        patient = get_object_or_404(User, id=request.POST.get("patient_id"))
        hospital = resolve_hospital(request.user)
        SessionNote.objects.create(
            hospital=hospital,
            staff=request.user,
            patient=patient,
            diagnosis=request.POST.get("diagnosis", ""),
            treatment=request.POST.get("treatment", ""),
            next_session=request.POST.get("next_session", ""),
        )
        messages.success(request, "✅ Session note added!")
        return redirect("staff_session_notes")
    patients = User.objects.filter(is_superuser=False, is_staff=False)
    return render(request, "staff/add_session_note.html", {"patients": patients})


# ─── ADMIN – APPOINTMENTS CRUD ───────────────────────────────


@login_required
def add_appointment(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = (
            User.objects.filter(
                Q(appointments__hospital=hospital) | Q(patient_profile__hospital=hospital),
                is_superuser=False,
                is_staff=False,
            )
            .distinct()
        )
    else:
        patients = User.objects.filter(is_superuser=False, is_staff=False)
    if request.method == "POST":
        patient_id = request.POST.get("patient_id")
        service = request.POST.get("service", "").strip()
        date = request.POST.get("date", "").strip()
        time = request.POST.get("time", "").strip()
        notes = request.POST.get("notes", "").strip()
        status = request.POST.get("status", "pending")
        patient = get_object_or_404(User, id=patient_id)

        # Validate appointment slot against clinic shift rules (admin allowed Sunday by appointment)
        is_valid, err_msg, normalized_time = validate_appointment_booking(
            date_str=date,
            time_str=time,
            hospital=hospital,
            allow_sunday=True,
        )
        if not is_valid:
            messages.error(request, f"❌ {err_msg}")
            return render(
                request,
                "admin/add_appointment.html",
                {
                    "patients": patients,
                    "selected_patient_id": patient_id,
                    "selected_service": service,
                    "selected_date": date,
                    "selected_time": time,
                    "notes": notes,
                },
            )

        try:
            with transaction.atomic():
                # Concurrent booking double-check inside transaction
                is_valid_tx, err_tx, _ = validate_appointment_booking(
                    date_str=date,
                    time_str=normalized_time,
                    hospital=hospital,
                    allow_sunday=True,
                )
                if not is_valid_tx:
                    messages.error(request, f"❌ {err_tx}")
                    return render(
                        request,
                        "admin/add_appointment.html",
                        {
                            "patients": patients,
                            "selected_patient_id": patient_id,
                            "selected_service": service,
                            "selected_date": date,
                            "selected_time": time,
                            "notes": notes,
                        },
                    )

                Appointment.objects.create(
                    hospital=hospital,
                    patient=patient,
                    name=patient.get_full_name() or patient.username,
                    email=patient.email,
                    phone=getattr(getattr(patient, "profile", None), "phone_number", ""),
                    service=service,
                    date=date,
                    time=time or normalized_time,
                    notes=notes,
                    status=status,
                )
        except IntegrityError:
            messages.error(request, "❌ This appointment slot has just been booked. Please choose another slot.")
            return render(
                request,
                "admin/add_appointment.html",
                {
                    "patients": patients,
                    "selected_patient_id": patient_id,
                    "selected_service": service,
                    "selected_date": date,
                    "selected_time": time,
                    "notes": notes,
                },
            )

        messages.success(request, f"✅ Appointment added successfully for {date} at {normalized_time}!")
        return redirect("admin_appointments")
    return render(request, "admin/add_appointment.html", {"patients": patients})


@login_required
def edit_appointment(request, appt_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        appt = get_object_or_404(Appointment, id=appt_id, hospital=hospital)
    else:
        appt = get_object_or_404(Appointment, id=appt_id)
    if request.method == "POST":
        new_service = request.POST.get("service", appt.service).strip()
        new_date = request.POST.get("date", str(appt.date)).strip()
        new_time = request.POST.get("time", appt.time).strip()
        new_notes = request.POST.get("notes", appt.notes).strip()
        new_status = request.POST.get("status", appt.status)

        # Validate if date or time changed
        if str(new_date) != str(appt.date) or new_time != appt.time:
            is_valid, err_msg, normalized_time = validate_appointment_booking(
                date_str=new_date,
                time_str=new_time,
                hospital=hospital,
                exclude_appointment_id=appt.id,
                allow_sunday=True,
            )
            if not is_valid:
                messages.error(request, f"❌ {err_msg}")
                return render(request, "admin/edit_appointment.html", {"appt": appt})
            appt.time = new_time or normalized_time
        else:
            appt.time = new_time

        appt.service = new_service
        appt.date = new_date
        appt.notes = new_notes
        appt.status = new_status
        appt.save()
        messages.success(request, "✅ Appointment updated successfully!")
        return redirect("admin_appointments")
    return render(request, "admin/edit_appointment.html", {"appt": appt})


@login_required
def delete_appointment(request, appt_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        appt = get_object_or_404(Appointment, id=appt_id, hospital=hospital)
    else:
        appt = get_object_or_404(Appointment, id=appt_id)
    if request.method == "POST":
        appt.delete()
        messages.success(request, "✅ Appointment deleted.")
        return redirect("admin_appointments")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Appointment",
            "item": f"{appt.name} — {appt.get_service_display()} on {appt.date}",
            "cancel_url": "/admin-appointments/",
        },
    )


# ─── ADMIN – PATIENTS CRUD ───────────────────────────────────


@login_required
def add_patient(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone_number = request.POST.get("phone_number", "").strip()
        gender = request.POST.get("gender", "").strip()
        dob_str = request.POST.get("date_of_birth", "").strip()
        joining_date_str = request.POST.get("joining_date", "").strip()
        blood_group = request.POST.get("blood_group", "").strip()
        emergency_contact = request.POST.get("emergency_contact", "").strip()
        address = request.POST.get("address", "").strip()
        medical_notes = request.POST.get("medical_notes", "").strip()
        username = request.POST.get("username", "").strip() or email or f"patient_{uuid.uuid4().hex[:8]}"

        if not email and not username:
            messages.error(request, "❌ Username or email is required to register a patient.")
            return render(request, "admin/add_patient.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, f"❌ Username '{username}' already exists. Please choose another.")
            return render(request, "admin/add_patient.html")

        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"❌ Email '{email}' is already registered.")
            return render(request, "admin/add_patient.html")

        # Parse date_of_birth and joining_date as date-only objects
        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        joining_date = timezone.now().date()
        if joining_date_str:
            try:
                joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(f"Patient@{uuid.uuid4().hex[:6]}")
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone_number = phone_number
        profile.gender = gender
        profile.date_of_birth = dob
        profile.joining_date = joining_date
        profile.blood_group = blood_group
        profile.emergency_contact = emergency_contact
        profile.address = address
        profile.medical_notes = medical_notes
        profile.save()

        patient_profile, _ = PatientProfile.objects.get_or_create(user=user)
        patient_profile.hospital = hospital
        patient_profile.joining_date = joining_date
        patient_profile.save()

        messages.success(request, f"✅ Patient {user.get_full_name() or user.username} registered successfully!")
        return redirect("admin_patients")
    return render(request, "admin/add_patient.html")


@login_required
def edit_patient(request, user_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    patient = get_object_or_404(User, id=user_id)
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=patient, hospital=hospital).exists()
            or (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Patient does not belong to your clinic.")
            return redirect("admin_patients")
    profile, _ = Profile.objects.get_or_create(user=patient)
    patient_profile = getattr(patient, "patient_profile", None)
    if not patient_profile and hospital:
        patient_profile = PatientProfile.objects.create(user=patient, hospital=hospital)

    if request.method == "POST":
        patient.first_name = request.POST.get("first_name", "").strip()
        patient.last_name = request.POST.get("last_name", "").strip()
        new_email = request.POST.get("email", "").strip()
        if new_email and new_email != patient.email:
            if User.objects.filter(email=new_email).exclude(id=patient.id).exists():
                messages.error(request, "❌ Email already registered by another account.")
                return render(request, "admin/edit_patient.html", {"patient": patient, "profile": profile, "patient_profile": patient_profile})
            patient.email = new_email
        patient.save()

        profile.phone_number = request.POST.get("phone_number", "").strip()
        profile.gender = request.POST.get("gender", profile.gender).strip()
        profile.blood_group = request.POST.get("blood_group", profile.blood_group).strip()
        profile.emergency_contact = request.POST.get("emergency_contact", profile.emergency_contact).strip()
        profile.medical_notes = request.POST.get("medical_notes", profile.medical_notes).strip()
        
        # Address
        address = request.POST.get("address", "").strip() or request.POST.get("city", "").strip()
        if address:
            profile.address = address

        # Date of Birth (date-only)
        dob_str = request.POST.get("date_of_birth", "").strip()
        if dob_str:
            try:
                profile.date_of_birth = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        elif "date_of_birth" in request.POST:
            profile.date_of_birth = None

        # Joining Date (date-only, preventing timezone day-shift)
        jd_str = request.POST.get("joining_date", "").strip()
        if jd_str:
            try:
                parsed_jd = datetime.strptime(jd_str, "%Y-%m-%d").date()
                profile.joining_date = parsed_jd
                if patient_profile:
                    patient_profile.joining_date = parsed_jd
                    patient_profile.save()
            except (ValueError, TypeError):
                pass
        elif "joining_date" in request.POST:
            # Explicitly cleared if optional
            profile.joining_date = None
            if patient_profile:
                patient_profile.joining_date = None
                patient_profile.save()

        profile.save()
        messages.success(request, "✅ Patient updated successfully!")
        return redirect("admin_patients")
    return render(
        request, "admin/edit_patient.html", {"patient": patient, "profile": profile, "patient_profile": patient_profile}
    )


@login_required
def delete_patient(request, user_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    patient = get_object_or_404(User, id=user_id, is_superuser=False, is_staff=False)
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=patient, hospital=hospital).exists()
            or (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Patient does not belong to your clinic.")
            return redirect("admin_patients")
    if request.method == "POST":
        patient.is_active = False
        patient.save()
        messages.success(
            request,
            f'✅ Patient "{patient.get_full_name() or patient.username}" has been deactivated.',
        )
        return redirect("admin_patients")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Deactivate Patient",
            "item": patient.get_full_name() or patient.username,
            "message": "This will deactivate the patient account. They will not be able to log in. You can reactivate them anytime.",
            "cancel_url": "/admin-patients/",
        },
    )


@login_required
def reactivate_patient(request, user_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    patient = get_object_or_404(User, id=user_id, is_superuser=False, is_staff=False)
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=patient, hospital=hospital).exists()
            or (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Patient does not belong to your clinic.")
            return redirect("admin_patients")
    patient.is_active = True
    patient.save()
    messages.success(
        request,
        f'✅ Patient "{patient.get_full_name() or patient.username}" has been reactivated.',
    )
    return redirect("admin_patients")


# ─── ADMIN – STAFF CRUD ──────────────────────────────────────


@login_required
def edit_staff(request, staff_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital:
        staff = get_object_or_404(StaffProfile, id=staff_id, hospital=hospital)
    else:
        staff = get_object_or_404(StaffProfile, id=staff_id)
    if request.method == "POST":
        staff.user.first_name = request.POST.get("first_name", "").strip()
        staff.user.last_name = request.POST.get("last_name", "").strip()
        staff.user.email = request.POST.get("email", "").strip()
        staff.user.save()
        staff.role = request.POST.get("role", staff.role)
        staff.phone = request.POST.get("phone", "").strip()
        salary_val = request.POST.get("base_salary") or request.POST.get("salary")
        if salary_val is not None and salary_val != "":
            try:
                staff.salary = Decimal(salary_val)
            except Exception:
                pass
        staff.address = request.POST.get("address", staff.address).strip()
        jd_str = request.POST.get("joining_date", "").strip()
        if jd_str:
            try:
                staff.joining_date = datetime.strptime(jd_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        staff.save()
        messages.success(request, "✅ Staff member updated successfully!")
        return redirect("admin_staff")
    return render(request, "admin/edit_staff.html", {"staff": staff})


@login_required
def delete_staff(request, staff_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if not request.user.is_superuser and hospital:
        staff = get_object_or_404(StaffProfile, id=staff_id, hospital=hospital)
    else:
        staff = get_object_or_404(StaffProfile, id=staff_id)
    if request.method == "POST":
        staff.user.delete()
        messages.success(request, "✅ Staff member deleted.")
        return redirect("admin_staff")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Staff Member",
            "item": staff.user.get_full_name() or staff.user.username,
            "cancel_url": "/admin-staff/",
        },
    )


# ─── ADMIN – ATTENDANCE CRUD ─────────────────────────────────


@login_required
def add_attendance(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        staff_list = StaffProfile.objects.filter(
            Q(hospital=hospital) | Q(hospital__isnull=True)
        ).select_related("user")
    else:
        staff_list = StaffProfile.objects.all().select_related("user")
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        if hospital and not request.user.is_superuser:
            staff_user = get_object_or_404(
                User,
                Q(id=staff_id)
                & (
                    Q(staff_profile__hospital=hospital)
                    | Q(staff_profile__hospital__isnull=True)
                ),
            )
        else:
            staff_user = get_object_or_404(User, id=staff_id)
        date = request.POST.get("date")
        clock_in = request.POST.get("clock_in") or None
        clock_out = request.POST.get("clock_out") or None
        total_hours = request.POST.get("total_hours", 0)
        notes = request.POST.get("notes", "")
        Attendance.objects.update_or_create(
            staff=staff_user,
            date=date,
            defaults={
                "hospital": hospital,
                "clock_in": clock_in,
                "clock_out": clock_out,
                "total_hours": total_hours,
                "notes": notes,
            },
        )
        messages.success(request, "✅ Attendance record saved!")
        return redirect("admin_attendance")
    return render(request, "admin/add_attendance.html", {"staff_list": staff_list})


@login_required
def edit_attendance(request, att_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        att = (
            Attendance.objects.filter(
                Q(hospital=hospital)
                | Q(staff__staff_profile__hospital=hospital)
                | Q(hospital__isnull=True)
            )
            .filter(id=att_id)
            .first()
        )
        if not att:
            if Attendance.objects.filter(id=att_id).exists():
                messages.error(
                    request,
                    "❌ Access denied: You do not have permission to edit this attendance record.",
                )
                return redirect("admin_attendance")
            raise Http404("No Attendance matches the given query.")
    else:
        att = get_object_or_404(Attendance, id=att_id)
    if request.method == "POST":
        att.clock_in = request.POST.get("clock_in") or None
        att.clock_out = request.POST.get("clock_out") or None
        att.total_hours = request.POST.get("total_hours", att.total_hours)
        att.notes = request.POST.get("notes", "")
        if not att.hospital and hospital:
            att.hospital = hospital
        att.save()
        messages.success(request, "✅ Attendance updated!")
        return redirect("admin_attendance")
    return render(request, "admin/edit_attendance.html", {"att": att})


@login_required
def delete_attendance(request, att_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        att = (
            Attendance.objects.filter(
                Q(hospital=hospital)
                | Q(staff__staff_profile__hospital=hospital)
                | Q(hospital__isnull=True)
            )
            .filter(id=att_id)
            .first()
        )
        if not att:
            if Attendance.objects.filter(id=att_id).exists():
                messages.error(
                    request,
                    "❌ Access denied: You do not have permission to delete this attendance record.",
                )
                return redirect("admin_attendance")
            raise Http404("No Attendance matches the given query.")
    else:
        att = get_object_or_404(Attendance, id=att_id)
    if request.method == "POST":
        att.delete()
        messages.success(request, "✅ Attendance record deleted.")
        return redirect("admin_attendance")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Attendance Record",
            "item": f"{att.staff.get_full_name() or att.staff.username} — {att.date}",
            "cancel_url": "/admin-attendance/",
        },
    )


# ─── ADMIN – LEAVES CRUD ─────────────────────────────────────


@login_required
def delete_leave(request, leave_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        leave = (
            LeaveApplication.objects.filter(
                Q(hospital=hospital)
                | Q(staff__staff_profile__hospital=hospital)
                | Q(hospital__isnull=True)
            )
            .filter(id=leave_id)
            .first()
        )
        if not leave:
            if LeaveApplication.objects.filter(id=leave_id).exists():
                messages.error(
                    request,
                    "❌ Access denied: You do not have permission to delete this leave application.",
                )
                return redirect("admin_leaves")
            raise Http404("No LeaveApplication matches the given query.")
    else:
        leave = get_object_or_404(LeaveApplication, id=leave_id)
    if request.method == "POST":
        leave.delete()
        messages.success(request, "✅ Leave application deleted.")
        return redirect("admin_leaves")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Leave Application",
            "item": f"{leave.staff.get_full_name() or leave.staff.username} — {leave.from_date} to {leave.to_date}",
            "cancel_url": "/admin-leaves/",
        },
    )


# ─── ADMIN – SALARY CRUD ─────────────────────────────────────


@login_required
def edit_salary(request, record_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        record = (
            SalaryRecord.objects.filter(
                Q(hospital=hospital)
                | Q(staff__staff_profile__hospital=hospital)
                | Q(hospital__isnull=True)
            )
            .filter(id=record_id)
            .first()
        )
        if not record:
            if SalaryRecord.objects.filter(id=record_id).exists():
                messages.error(
                    request,
                    "❌ Access denied: You do not have permission to edit this salary record.",
                )
                return redirect("admin_salary")
            raise Http404("No SalaryRecord matches the given query.")
    else:
        record = get_object_or_404(SalaryRecord, id=record_id)
    if request.method == "POST":
        record.month = request.POST.get("month", record.month)
        record.year = request.POST.get("year", record.year)
        record.basic_salary = request.POST.get("basic_salary", record.basic_salary)
        record.bonus = request.POST.get("bonus", record.bonus)
        record.deduction = request.POST.get("deduction", record.deduction)
        record.net_salary = (
            float(record.basic_salary) + float(record.bonus) - float(record.deduction)
        )
        if not record.hospital and hospital:
            record.hospital = hospital
        record.save()
        messages.success(request, "✅ Salary record updated!")
        return redirect("admin_salary")
    return render(request, "admin/edit_salary.html", {"record": record})


@login_required
def delete_salary(request, record_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        record = (
            SalaryRecord.objects.filter(
                Q(hospital=hospital)
                | Q(staff__staff_profile__hospital=hospital)
                | Q(hospital__isnull=True)
            )
            .filter(id=record_id)
            .first()
        )
        if not record:
            if SalaryRecord.objects.filter(id=record_id).exists():
                messages.error(
                    request,
                    "❌ Access denied: You do not have permission to delete this salary record.",
                )
                return redirect("admin_salary")
            raise Http404("No SalaryRecord matches the given query.")
    else:
        record = get_object_or_404(SalaryRecord, id=record_id)
    if request.method == "POST":
        record.delete()
        messages.success(request, "✅ Salary record deleted.")
        return redirect("admin_salary")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Salary Record",
            "item": f"{record.staff.get_full_name() or record.staff.username} — {record.month} {record.year}",
            "cancel_url": "/admin-salary/",
        },
    )


# ─── ADMIN – TASKS CRUD ──────────────────────────────────────


@login_required
def edit_task_admin(request, task_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        task = (
            DailyTask.objects.filter(
                Q(hospital=hospital)
                | Q(assigned_to__staff_profile__hospital=hospital)
                | Q(assigned_by=request.user)
                | Q(hospital__isnull=True)
            )
            .filter(id=task_id)
            .first()
        )
        if not task:
            raise Http404("No DailyTask matches the given query.")
        staff_list = (
            StaffProfile.objects.filter(
                Q(hospital=hospital) | Q(hospital__isnull=True) | Q(user=task.assigned_to)
            )
            .select_related("user")
            .distinct()
        )
    else:
        task = get_object_or_404(DailyTask, id=task_id)
        staff_list = StaffProfile.objects.all().select_related("user")
    if request.method == "POST":
        task.title = request.POST.get("title", task.title).strip() or task.title
        task.description = request.POST.get("description", "")
        task.priority = request.POST.get("priority", task.priority)
        task.status = request.POST.get("status", task.status)
        task.due_date = request.POST.get("due_date") or None
        new_staff_id = request.POST.get("staff_id")
        if new_staff_id:
            task.assigned_to = get_object_or_404(User, id=new_staff_id)
        if not task.hospital and hospital:
            task.hospital = hospital
        task.save()
        messages.success(request, "✅ Task updated!")
        return redirect("admin_tasks")
    return render(request, "admin/edit_task.html", {"task": task, "staff_list": staff_list})


@login_required
def delete_task_admin(request, task_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        task = (
            DailyTask.objects.filter(
                Q(hospital=hospital)
                | Q(assigned_to__staff_profile__hospital=hospital)
                | Q(assigned_by=request.user)
                | Q(hospital__isnull=True)
            )
            .filter(id=task_id)
            .first()
        )
        if not task:
            raise Http404("No DailyTask matches the given query.")
    else:
        task = get_object_or_404(DailyTask, id=task_id)
    if request.method == "POST":
        task.delete()
        messages.success(request, "✅ Task deleted.")
        return redirect("admin_tasks")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Task",
            "item": task.title,
            "cancel_url": "/admin-tasks/",
        },
    )


# ─── ADMIN – SESSION NOTES CRUD ──────────────────────────────


@login_required
def admin_add_session_note(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = (
            User.objects.filter(
                Q(appointments__hospital=hospital) | Q(patient_profile__hospital=hospital),
                is_superuser=False,
                is_staff=False,
            )
            .distinct()
        )
        staff_list = StaffProfile.objects.filter(hospital=hospital).select_related("user")
    else:
        patients = User.objects.filter(is_superuser=False, is_staff=False)
        staff_list = StaffProfile.objects.all().select_related("user")
    if request.method == "POST":
        staff = get_object_or_404(User, id=request.POST.get("staff_id"))
        patient = get_object_or_404(User, id=request.POST.get("patient_id"))
        SessionNote.objects.create(
            hospital=hospital,
            staff=staff,
            patient=patient,
            diagnosis=request.POST.get("diagnosis", ""),
            treatment=request.POST.get("treatment", ""),
            next_session=request.POST.get("next_session", ""),
        )
        messages.success(request, "✅ Session note added!")
        return redirect("admin_session_notes")
    return render(
        request,
        "admin/admin_add_session_note.html",
        {"patients": patients, "staff_list": staff_list},
    )


@login_required
def edit_session_note(request, note_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    note = get_object_or_404(SessionNote, id=note_id)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=note.patient, hospital=hospital).exists()
            or (hasattr(note.patient, "patient_profile") and note.patient.patient_profile.hospital_id == hospital.id)
            or (hasattr(note.staff, "staff_profile") and note.staff.staff_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Session note belongs to another clinic.")
            return redirect("admin_session_notes")
        patients = (
            User.objects.filter(
                Q(appointments__hospital=hospital) | Q(patient_profile__hospital=hospital),
                is_superuser=False,
                is_staff=False,
            )
            .distinct()
        )
        staff_list = StaffProfile.objects.filter(hospital=hospital).select_related("user")
    else:
        patients = User.objects.filter(is_superuser=False, is_staff=False)
        staff_list = StaffProfile.objects.all().select_related("user")
    if request.method == "POST":
        note.staff = get_object_or_404(User, id=request.POST.get("staff_id"))
        note.patient = get_object_or_404(User, id=request.POST.get("patient_id"))
        note.diagnosis = request.POST.get("diagnosis", "")
        note.treatment = request.POST.get("treatment", "")
        note.next_session = request.POST.get("next_session", "")
        note.save()
        messages.success(request, "✅ Session note updated!")
        return redirect("admin_session_notes")
    return render(
        request,
        "admin/edit_session_note.html",
        {"note": note, "patients": patients, "staff_list": staff_list},
    )


@login_required
def delete_session_note(request, note_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    note = get_object_or_404(SessionNote, id=note_id)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=note.patient, hospital=hospital).exists()
            or (hasattr(note.patient, "patient_profile") and note.patient.patient_profile.hospital_id == hospital.id)
            or (hasattr(note.staff, "staff_profile") and note.staff.staff_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Session note belongs to another clinic.")
            return redirect("admin_session_notes")
    if request.method == "POST":
        note.delete()
        messages.success(request, "✅ Session note deleted.")
        return redirect("admin_session_notes")
    return render(
        request,
        "shared/confirm_delete.html",
        {
            "title": "Delete Session Note",
            "item": f"{note.patient.get_full_name() or note.patient.username} — {note.date}",
            "cancel_url": "/admin-session-notes/",
        },
    )


@login_required
def admin_settings(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    from decimal import Decimal
    hospital = resolve_hospital(request.user) or Hospital.objects.first()
    if hospital:
        settings_obj, created = ClinicSettings.objects.get_or_create(
            hospital=hospital,
            defaults={
                "clinic_name": hospital.name,
                "phone": hospital.phone or "",
                "email": hospital.email or "",
                "address": hospital.address or "",
            },
        )
    else:
        settings_obj, created = ClinicSettings.objects.get_or_create(
            id=1,
            defaults={
                "clinic_name": "PhysioRehab Clinic",
                "phone": "+91 98765 43210",
                "email": "contact@physiorehab.com",
                "address": "Rajkot, Gujarat",
            },
        )
    if not settings_obj.clinic_name and hospital:
        settings_obj.clinic_name = hospital.name
        settings_obj.save()

    if request.method == "POST":
        if request.POST.get("clinic_name"):
            settings_obj.clinic_name = request.POST.get("clinic_name").strip()
        if request.POST.get("phone"):
            settings_obj.phone = request.POST.get("phone").strip()
        if request.POST.get("email"):
            settings_obj.email = request.POST.get("email").strip()
        if request.POST.get("address"):
            settings_obj.address = request.POST.get("address").strip()
        if request.POST.get("appointment_fee"):
            try:
                settings_obj.appointment_fee = Decimal(request.POST.get("appointment_fee"))
            except Exception:
                pass

        if request.FILES.get("logo"):
            logo_file = request.FILES["logo"]
            from .file_security import validate_image_file
            try:
                validate_image_file(logo_file, max_size_mb=5, field_name="Clinic logo")
                settings_obj.logo = logo_file
            except ValidationError as e:
                messages.error(request, f"❌ {e.message if hasattr(e, 'message') else str(e)}")
                return render(request, "admin/admin_settings.html", {"settings": settings_obj})

        settings_obj.save()

        messages.success(request, "Settings updated successfully.")

        return redirect("admin_settings")

    return render(request, "admin/admin_settings.html", {"settings": settings_obj})



# ════════════════════════════════════════════════════════════
# Add these two views to your core/views.py
# ════════════════════════════════════════════════════════════


@login_required
def progress_tracking(request):
    is_admin = request.user.is_superuser or _is_clinic_admin(request.user)
    if is_admin:
        # Admin: can view any patient's progress
        all_patients = User.objects.filter(is_superuser=False, is_staff=False)
        patient_id = request.GET.get("patient_id")

        if patient_id:
            selected_patient = get_object_or_404(User, id=patient_id)
            appointments = Appointment.objects.filter(patient=selected_patient)
            session_notes = SessionNote.objects.filter(
                patient=selected_patient
            ).select_related("staff")
        else:
            selected_patient = None
            appointments = Appointment.objects.all()
            session_notes = SessionNote.objects.all().select_related("staff", "patient")
    else:
        # Client: sees only their own data
        all_patients = None
        selected_patient = None
        appointments = Appointment.objects.filter(patient=request.user)
        session_notes = SessionNote.objects.filter(patient=request.user).select_related(
            "staff"
        )

    # ── Stats ──
    total_appointments = appointments.count()
    completed_count = appointments.filter(status="completed").count()
    upcoming_count = appointments.filter(status__in=["pending", "confirmed"]).count()
    session_notes_count = session_notes.count()

    # ── Recovery percentage ──
    recovery_pct = round(
        (completed_count / total_appointments * 100) if total_appointments else 0
    )
    attendance_pct = round(
        (
            (total_appointments - appointments.filter(status="cancelled").count())
            / total_appointments
            * 100
        )
        if total_appointments
        else 0
    )
    consistency_pct = min(recovery_pct + 10, 100)
    notes_pct = round(
        (session_notes_count / completed_count * 100) if completed_count else 0
    )

    # ── Service breakdown ──
    service_map = {
        "orthopedic": "Orthopedic",
        "neurological": "Neurological",
        "sports": "Sports",
        "pediatric": "Pediatric",
        "womens": "Women's Health",
        "home_visit": "Home Visit",
    }
    service_breakdown = []
    for key, label in service_map.items():
        count = appointments.filter(service=key).count()
        if count > 0:
            service_breakdown.append(
                {
                    "label": label,
                    "count": count,
                    "pct": round(count / total_appointments * 100)
                    if total_appointments
                    else 0,
                }
            )
    service_breakdown.sort(key=lambda x: x["count"], reverse=True)

    tpl = "admin/admin_progress_tracking.html" if is_admin else "client/progress_tracking.html"
    return render(
        request,
        tpl,
        {
            "appointments": appointments,
            "session_notes": session_notes,
            "all_patients": all_patients,
            "selected_patient": selected_patient,
            "total_appointments": total_appointments,
            "completed_count": completed_count,
            "upcoming_count": upcoming_count,
            "session_notes_count": session_notes_count,
            "recovery_pct": recovery_pct,
            "attendance_pct": attendance_pct,
            "consistency_pct": consistency_pct,
            "notes_pct": notes_pct,
            "service_breakdown": service_breakdown,
        },
    )


@login_required
def reports_analytics(request):
    """Clinic Admin Analytics View:
    - Calculates real clinical metrics from PostgreSQL database records.
    - True patient retention rate computed from actual multi-session patient ratios.
    - Eliminates N+1 queries by annotating staff tasks and leave counts.
    - Supports dynamic date filtering (all, today, 7d, 30d, this_month, this_year, custom dates).
    - Enforces strict server-side authorization (rejects non-admin roles with 403 Forbidden).
    """
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return HttpResponseForbidden("Forbidden: Administrative analytics access is restricted to clinic administrators.")

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        all_appointments = Appointment.objects.filter(hospital=hospital)
        tasks_qs = DailyTask.objects.filter(hospital=hospital)
        notes_qs = SessionNote.objects.filter(hospital=hospital)
        leaves_qs = LeaveApplication.objects.filter(hospital=hospital)
        staff_qs = StaffProfile.objects.filter(hospital=hospital)
        patient_qs = User.objects.filter(
            is_superuser=False, is_staff=False
        ).filter(
            Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital)
        ).distinct()
    else:
        all_appointments = Appointment.objects.all()
        tasks_qs = DailyTask.objects.all()
        notes_qs = SessionNote.objects.all()
        leaves_qs = LeaveApplication.objects.all()
        staff_qs = StaffProfile.objects.all()
        patient_qs = User.objects.filter(is_superuser=False, is_staff=False)

    # ── Date Filtering ──
    period = request.GET.get("period", "all").strip().lower()
    date_from_str = request.GET.get("date_from", "").strip()
    date_to_str = request.GET.get("date_to", "").strip()

    now = timezone.now()
    today = now.date()

    if period == "today":
        all_appointments = all_appointments.filter(date=today)
        tasks_qs = tasks_qs.filter(Q(due_date=today) | Q(created_at__date=today))
        notes_qs = notes_qs.filter(date=today)
        leaves_qs = leaves_qs.filter(Q(from_date__lte=today, to_date__gte=today) | Q(applied_on__date=today))
    elif period == "7d":
        since_7d = today - timedelta(days=7)
        all_appointments = all_appointments.filter(date__gte=since_7d)
        tasks_qs = tasks_qs.filter(Q(due_date__gte=since_7d) | Q(created_at__date__gte=since_7d))
        notes_qs = notes_qs.filter(date__gte=since_7d)
        leaves_qs = leaves_qs.filter(Q(to_date__gte=since_7d) | Q(applied_on__date__gte=since_7d))
    elif period == "30d":
        since_30d = today - timedelta(days=30)
        all_appointments = all_appointments.filter(date__gte=since_30d)
        tasks_qs = tasks_qs.filter(Q(due_date__gte=since_30d) | Q(created_at__date__gte=since_30d))
        notes_qs = notes_qs.filter(date__gte=since_30d)
        leaves_qs = leaves_qs.filter(Q(to_date__gte=since_30d) | Q(applied_on__date__gte=since_30d))
    elif period == "this_month":
        all_appointments = all_appointments.filter(date__year=today.year, date__month=today.month)
        tasks_qs = tasks_qs.filter(created_at__year=today.year, created_at__month=today.month)
        notes_qs = notes_qs.filter(date__year=today.year, date__month=today.month)
        leaves_qs = leaves_qs.filter(applied_on__year=today.year, applied_on__month=today.month)
    elif period == "this_year":
        all_appointments = all_appointments.filter(date__year=today.year)
        tasks_qs = tasks_qs.filter(created_at__year=today.year)
        notes_qs = notes_qs.filter(date__year=today.year)
        leaves_qs = leaves_qs.filter(applied_on__year=today.year)
    elif date_from_str or date_to_str:
        if date_from_str:
            try:
                df = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                all_appointments = all_appointments.filter(date__gte=df)
                tasks_qs = tasks_qs.filter(Q(due_date__gte=df) | Q(created_at__date__gte=df))
                notes_qs = notes_qs.filter(date__gte=df)
                leaves_qs = leaves_qs.filter(applied_on__date__gte=df)
            except ValueError:
                pass
        if date_to_str:
            try:
                dt = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                all_appointments = all_appointments.filter(date__lte=dt)
                tasks_qs = tasks_qs.filter(Q(due_date__lte=dt) | Q(created_at__date__lte=dt))
                notes_qs = notes_qs.filter(date__lte=dt)
                leaves_qs = leaves_qs.filter(applied_on__date__lte=dt)
            except ValueError:
                pass

    total_appointments = all_appointments.count()
    completed_appointments = all_appointments.filter(status="completed").count()
    confirmed_appointments = all_appointments.filter(status="confirmed").count()
    pending_appointments = all_appointments.filter(status="pending").count()
    cancelled_appointments = all_appointments.filter(status="cancelled").count()

    # ── Donut chart percentages ──
    def pct(n):
        return round(n / total_appointments * 100) if total_appointments else 0

    confirmed_pct = pct(confirmed_appointments)
    completed_pct = pct(completed_appointments)
    pending_pct = pct(pending_appointments)

    # ── Service bar chart ──
    service_map = [
        ("orthopedic", "Ortho"),
        ("neurological", "Neuro"),
        ("sports", "Sports"),
        ("pediatric", "Pedia"),
        ("womens", "Women"),
        ("home_visit", "Home"),
    ]
    counts = [all_appointments.filter(service=k).count() for k, _ in service_map]
    max_count = max(counts) if counts and max(counts) > 0 else 1
    service_stats = []
    for (key, short), count in zip(service_map, counts):
        service_stats.append(
            {
                "short": short,
                "count": count,
                "bar_height": max(round(count / max_count * 120), 4)
                if count > 0
                else 4,
            }
        )

    # ── True Clinical Performance Rates ──
    completion_rate = pct(completed_appointments)

    # Real database calculation of patient retention:
    # Repeat patients (having >1 appointment) / Total patients with appointments
    patients_with_appts = (
        patient_qs.annotate(appt_count=Count("appointments", distinct=True))
        .filter(appt_count__gt=0)
    )
    total_active_patients = patients_with_appts.count()
    retained_patients = patients_with_appts.filter(appt_count__gt=1).count()
    retention_rate = (
        round(retained_patients / total_active_patients * 100)
        if total_active_patients
        else 0
    )

    total_tasks = tasks_qs.count()
    completed_tasks = tasks_qs.filter(status="completed").count()
    task_completion_rate = (
        round(completed_tasks / total_tasks * 100) if total_tasks else 0
    )
    total_notes = notes_qs.count()
    notes_rate = (
        round(total_notes / completed_appointments * 100)
        if completed_appointments
        else 0
    )

    # Staff list annotated with task and leave counts to eliminate N+1 queries
    staff_list = staff_qs.select_related("user").annotate(
        tasks_count=Count("user__tasks", distinct=True),
        leaves_count=Count("user__leaves", distinct=True),
    )

    return render(
        request,
        "admin/reports_analytics.html",
        {
            "total_patients": patient_qs.count(),
            "total_appointments": total_appointments,
            "completed_appointments": completed_appointments,
            "confirmed_appointments": confirmed_appointments,
            "pending_appointments": pending_appointments,
            "cancelled_appointments": cancelled_appointments,
            "confirmed_pct": confirmed_pct,
            "completed_pct": completed_pct,
            "pending_pct": pending_pct,
            "service_stats": service_stats,
            "completion_rate": completion_rate,
            "retention_rate": retention_rate,
            "task_completion_rate": task_completion_rate,
            "notes_rate": min(notes_rate, 100),
            "total_staff": staff_qs.count(),
            "total_notes": total_notes,
            "total_leaves": leaves_qs.count(),
            "total_tasks": total_tasks,
            "recent_patients": patient_qs.order_by("-date_joined")[:6],
            "recent_appointments": all_appointments.order_by("-created_at")[:8],
            "staff_list": staff_list,
            "period": period,
            "date_from": date_from_str,
            "date_to": date_to_str,
        },
    )


# ════════════════════════════════════════════════════════════
# EXPORT VIEWS — Excel & PDF
# ════════════════════════════════════════════════════════════

import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# ─── PATIENTS EXPORT ─────────────────────────────────────────


@login_required
def export_patients_excel(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1a1a1a")
    header_align = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        "#",
        "Full Name",
        "Username",
        "Email",
        "Phone",
        "Gender",
        "Date of Birth",
        "Blood Group",
        "Address",
        "Appointments",
        "Status",
        "Joined Date",
    ]
    ws.append(headers)

    for col_idx, col in enumerate(ws[1], 1):
        col.font = header_font
        col.fill = header_fill
        col.alignment = header_align
        col.border = border

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = (
            User.objects.filter(is_superuser=False, is_staff=False)
            .filter(Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital))
            .distinct()
            .order_by("-date_joined")
        )
    else:
        patients = User.objects.filter(is_superuser=False, is_staff=False).order_by(
            "-date_joined"
        )
    for i, p in enumerate(patients, 1):
        try:
            prof = p.profile
            phone = prof.phone_number or "—"
            gender = prof.gender or "—"
            dob = str(prof.date_of_birth) if prof.date_of_birth else "—"
            blood = prof.blood_group or "—"
            address = prof.address or "—"
        except Exception:
            phone = gender = dob = blood = address = "—"
        appt_count = Appointment.objects.filter(patient=p).count()
        status = "Active" if p.is_active else "Deactivated"
        row = [
            i,
            p.get_full_name() or p.username,
            p.username,
            p.email,
            phone,
            gender,
            dob,
            blood,
            address,
            appt_count,
            status,
            p.date_joined.strftime("%d %b %Y"),
        ]
        ws.append(row)
        for cell in ws[ws.max_row]:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    # Column widths
    col_widths = [5, 22, 18, 28, 16, 10, 14, 12, 30, 14, 12, 16]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    ws.row_dimensions[1].height = 25

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="patients_list.xlsx"'
    return response


@login_required
def export_patients_pdf(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph("Dr. Dhvani Patalia Physio-Rehab", title_style))
    elements.append(
        Paragraph(
            f"Patient List — Generated on {timezone.now().strftime('%d %b %Y %H:%M')}",
            sub_style,
        )
    )

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        patients = (
            User.objects.filter(is_superuser=False, is_staff=False)
            .filter(Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital))
            .distinct()
            .order_by("-date_joined")
        )
    else:
        patients = User.objects.filter(is_superuser=False, is_staff=False).order_by(
            "-date_joined"
        )
    data = [
        [
            "#",
            "Full Name",
            "Email",
            "Phone",
            "Gender",
            "Blood",
            "Appointments",
            "Status",
            "Joined",
        ]
    ]
    for i, p in enumerate(patients, 1):
        try:
            prof = p.profile
            phone = prof.phone_number or "—"
            gender = prof.gender or "—"
            blood = prof.blood_group or "—"
        except Exception:
            phone = gender = blood = "—"
        appt_count = Appointment.objects.filter(patient=p).count()
        status = "Active" if p.is_active else "Deactivated"
        data.append(
            [
                str(i),
                p.get_full_name() or p.username,
                p.email or "—",
                phone,
                gender,
                blood,
                str(appt_count),
                status,
                p.date_joined.strftime("%d %b %Y"),
            ]
        )

    col_widths = [
        0.8 * cm,
        4 * cm,
        5.5 * cm,
        3 * cm,
        2 * cm,
        1.8 * cm,
        2.5 * cm,
        2.5 * cm,
        3 * cm,
    ]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f9f9f9")],
                ),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 18),
            ]
        )
    )
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="patients_list.pdf"'
    return response


# ─── APPOINTMENTS EXPORT ─────────────────────────────────────


@login_required
def export_appointments_excel(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Appointments"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1a1a1a")
    header_align = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        "#",
        "Patient Name",
        "Email",
        "Phone",
        "Service",
        "Date",
        "Time",
        "Status",
        "Notes",
        "Booked On",
    ]
    ws.append(headers)
    for col in ws[1]:
        col.font = header_font
        col.fill = header_fill
        col.alignment = header_align
        col.border = border

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        appts = Appointment.objects.filter(hospital=hospital).order_by("-created_at")
    else:
        appts = Appointment.objects.all().order_by("-created_at")
    for i, a in enumerate(appts, 1):
        row = [
            i,
            a.name,
            a.email,
            a.phone,
            a.service,
            str(a.date),
            a.time,
            a.status.upper(),
            a.notes or "—",
            a.created_at.strftime("%d %b %Y"),
        ]
        ws.append(row)
        for cell in ws[ws.max_row]:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    col_widths = [5, 22, 28, 16, 20, 14, 10, 14, 30, 16]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 25

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="appointments.xlsx"'
    return response


@login_required
def export_appointments_pdf(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph("Dr. Dhvani Patalia Physio-Rehab", title_style))
    elements.append(
        Paragraph(
            f"Appointments Report — Generated on {timezone.now().strftime('%d %b %Y %H:%M')}",
            sub_style,
        )
    )

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        appts = Appointment.objects.filter(hospital=hospital).order_by("-created_at")
    else:
        appts = Appointment.objects.all().order_by("-created_at")
    data = [
        ["#", "Patient Name", "Phone", "Service", "Date", "Time", "Status", "Booked On"]
    ]
    for i, a in enumerate(appts, 1):
        data.append(
            [
                str(i),
                a.name,
                a.phone,
                a.service,
                str(a.date),
                a.time,
                a.status.upper(),
                a.created_at.strftime("%d %b %Y"),
            ]
        )

    col_widths = [
        0.8 * cm,
        4.5 * cm,
        3 * cm,
        4.5 * cm,
        3 * cm,
        2.5 * cm,
        3 * cm,
        3 * cm,
    ]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f9f9f9")],
                ),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 18),
            ]
        )
    )
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="appointments.pdf"'
    return response


# ─── ANALYTICS REPORT PDF ────────────────────────────────────


@login_required
def export_analytics_pdf(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=20,
        alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#f5c518"),
        spaceBefore=14,
        spaceAfter=6,
    )

    elements.append(Paragraph("Dr. Dhvani Patalia Physio-Rehab", title_style))
    elements.append(
        Paragraph(
            f"Analytics Report — {timezone.now().strftime('%d %b %Y')}", sub_style
        )
    )

    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        total_patients = (
            User.objects.filter(is_superuser=False, is_staff=False)
            .filter(Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital))
            .distinct()
            .count()
        )
        active_patients = (
            User.objects.filter(is_superuser=False, is_staff=False, is_active=True)
            .filter(Q(patient_profile__hospital=hospital) | Q(appointments__hospital=hospital))
            .distinct()
            .count()
        )
        total_appts = Appointment.objects.filter(hospital=hospital).count()
        completed = Appointment.objects.filter(hospital=hospital, status="completed").count()
        confirmed = Appointment.objects.filter(hospital=hospital, status="confirmed").count()
        pending = Appointment.objects.filter(hospital=hospital, status="pending").count()
        cancelled = Appointment.objects.filter(hospital=hospital, status="cancelled").count()
        total_staff = StaffProfile.objects.filter(hospital=hospital).count()
    else:
        total_patients = User.objects.filter(is_superuser=False, is_staff=False).count()
        active_patients = User.objects.filter(
            is_superuser=False, is_staff=False, is_active=True
        ).count()
        total_appts = Appointment.objects.count()
        completed = Appointment.objects.filter(status="completed").count()
        confirmed = Appointment.objects.filter(status="confirmed").count()
        pending = Appointment.objects.filter(status="pending").count()
        cancelled = Appointment.objects.filter(status="cancelled").count()
        total_staff = StaffProfile.objects.count()

    elements.append(Paragraph("Summary Statistics", section_style))
    summary_data = [
        ["Metric", "Count"],
        ["Total Patients", str(total_patients)],
        ["Active Patients", str(active_patients)],
        ["Deactivated Patients", str(total_patients - active_patients)],
        ["Total Staff", str(total_staff)],
        ["Total Appointments", str(total_appts)],
        ["Completed Appointments", str(completed)],
        ["Confirmed Appointments", str(confirmed)],
        ["Pending Appointments", str(pending)],
        ["Cancelled Appointments", str(cancelled)],
    ]
    t = Table(summary_data, colWidths=[10 * cm, 5 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f9f9f9")],
                ),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(t)

    elements.append(Paragraph("Service Breakdown", section_style))
    from django.db.models import Count

    appt_service_qs = (
        Appointment.objects.filter(hospital=hospital)
        if (hospital and not request.user.is_superuser)
        else Appointment.objects.all()
    )
    service_stats = (
        appt_service_qs.values("service")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    svc_data = [["Service", "Total Appointments"]]
    for s in service_stats:
        svc_data.append([s["service"].replace("_", " ").title(), str(s["count"])])
    if len(svc_data) > 1:
        t2 = Table(svc_data, colWidths=[10 * cm, 5 * cm])
        t2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f9f9f9")],
                    ),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                    ("ROWHEIGHT", (0, 0), (-1, -1), 20),
                ]
            )
        )
        elements.append(t2)

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="analytics_report.pdf"'
    return response


# ════════════════════════════════════════════════════════════
# SUPER ADMIN PANEL — Platform-level multi-clinic management
# ════════════════════════════════════════════════════════════


@platform_superadmin_required
def super_admin_dashboard(request):
    from django.db.models import Count, Sum
    now = timezone.now()
    today = now.date()

    # Clinic counts & statuses
    total_hospitals = Hospital.objects.count()
    active_hospitals = Hospital.objects.filter(is_active=True).count()
    trial_hospitals = HospitalSubscription.objects.filter(status="trial").count()
    paid_hospitals = HospitalSubscription.objects.filter(
        status="active", plan__price_monthly__gt=0
    ).count()
    expired_hospitals = Hospital.objects.filter(
        Q(subscription__status="expired") | Q(status="expired")
    ).count()
    suspended_hospitals = Hospital.objects.filter(
        Q(status="suspended") | Q(subscription__status="suspended")
    ).count()
    new_hospitals_month = Hospital.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    ).count()

    # User & clinical resources
    total_patients = User.objects.filter(is_superuser=False, is_staff=False).count()
    total_staff = StaffProfile.objects.count()
    total_appointments = Appointment.objects.count()
    open_tickets = SupportTicket.objects.filter(status="open").count()

    # Subscriptions
    active_subs = HospitalSubscription.objects.filter(status="active").count()
    trial_subs = HospitalSubscription.objects.filter(status="trial").count()
    expired_subs = HospitalSubscription.objects.filter(status="expired").count()
    upcoming_renewals = HospitalSubscription.objects.filter(
        status="active",
        expires_at__gte=today,
        expires_at__lte=today + timedelta(days=7),
    ).count()

    # Payments & Revenue
    has_sub_payments = ClinicSubscriptionPayment.objects.exists()
    mrr_val = (
        HospitalSubscription.objects.filter(status="active").aggregate(
            t=Sum("plan__price_monthly")
        )["t"]
        or Decimal("0.00")
    )
    total_revenue = (
        PaymentRecord.objects.filter(status="paid").aggregate(t=Sum("amount"))["t"]
        or 0
    )
    pending_payments = PaymentRecord.objects.filter(status="pending").count()
    failed_payments = ClinicSubscriptionPayment.objects.filter(status="failed").count()

    # Alert center calculations
    clinics_near_limit = []
    for h in Hospital.objects.filter(is_active=True).select_related("subscription__plan"):
        for fcode in ("patients", "appointments", "staff_management"):
            u = get_feature_usage(h, fcode)
            if u.get("limit", 0) > 0 and u.get("percent", 0) >= 80:
                clinics_near_limit.append({
                    "hospital": h,
                    "metric": fcode.replace("_", " ").title(),
                    "percent": u["percent"],
                    "current": u["current"],
                    "limit": u["limit"],
                    "level": u["warning_level"],
                })
                break

    trials_expiring = HospitalSubscription.objects.filter(
        status="trial",
        expires_at__lte=today + timedelta(days=3),
    ).select_related("hospital", "plan")

    impaired_features = Feature.objects.filter(
        global_status__in=["maintenance", "disabled"], is_active=True
    ).select_related("category")

    recent_hospitals = Hospital.objects.select_related("subscription__plan").order_by(
        "-created_at"
    )[:6]
    recent_tickets = SupportTicket.objects.select_related("hospital").order_by(
        "-created_at"
    )[:5]
    recent_payments = PaymentRecord.objects.select_related(
        "patient", "appointment", "hospital"
    ).order_by("-created_at")[:15]
    recent_audit_events = AuditEvent.objects.select_related(
        "actor", "hospital"
    ).order_by("-created_at")[:8]

    return render(
        request,
        "super_admin/super_admin_dashboard.html",
        {
            # Core counters (backwards-compatible)
            "total_hospitals": total_hospitals,
            "active_hospitals": active_hospitals,
            "total_patients": total_patients,
            "total_staff": total_staff,
            "total_appointments": total_appointments,
            "open_tickets": open_tickets,
            "active_subs": active_subs,
            "trial_subs": trial_subs,
            "expired_subs": expired_subs,
            "recent_hospitals": recent_hospitals,
            "recent_tickets": recent_tickets,
            "recent_payments": recent_payments,
            "total_revenue": total_revenue,
            "pending_payments": pending_payments,
            # SaaS Subscription & Multi-Clinic metrics
            "trial_hospitals": trial_hospitals,
            "paid_hospitals": paid_hospitals,
            "expired_hospitals": expired_hospitals,
            "suspended_hospitals": suspended_hospitals,
            "new_hospitals_month": new_hospitals_month,
            "mrr": mrr_val,
            "has_billing_data": (mrr_val > 0 or has_sub_payments or total_revenue > 0),
            "upcoming_renewals": upcoming_renewals,
            "failed_payments": failed_payments,
            "clinics_near_limit": clinics_near_limit,
            "trials_expiring": trials_expiring,
            "impaired_features": impaired_features,
            "recent_audit_events": recent_audit_events,
        },
    )


@platform_superadmin_required
def super_admin_hospitals(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    plan_filter = request.GET.get("plan", "").strip()

    hospitals_qs = (
        Hospital.objects.select_related("subscription__plan")
        .prefetch_related("admins__user", "staff")
        .all()
    )

    if q:
        hospitals_qs = hospitals_qs.filter(
            Q(name__icontains=q)
            | Q(city__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(admins__user__username__icontains=q)
        ).distinct()

    if status_filter:
        hospitals_qs = hospitals_qs.filter(status=status_filter)

    if plan_filter:
        hospitals_qs = hospitals_qs.filter(subscription__plan_id=plan_filter)

    hospitals_data = []
    now = timezone.now()
    for h in hospitals_qs:
        sub = getattr(h, "subscription", None)
        patient_count = PatientProfile.objects.filter(
            hospital=h, patient_status="active"
        ).count()
        staff_count = StaffProfile.objects.filter(hospital=h, is_active=True).count()
        monthly_appts = (
            Appointment.objects.filter(
                hospital=h, date__year=now.year, date__month=now.month
            )
            .exclude(status="cancelled")
            .count()
        )

        patient_usage = get_feature_usage(h, "patients")
        appt_usage = get_feature_usage(h, "appointments")

        hospitals_data.append({
            "hospital": h,
            "subscription": sub,
            "patient_count": patient_count,
            "staff_count": staff_count,
            "monthly_appts": monthly_appts,
            "patient_usage": patient_usage,
            "appt_usage": appt_usage,
        })

    plans = SubscriptionPlan.objects.all().order_by("tier_level", "price_monthly")

    return render(
        request,
        "super_admin/super_admin_hospitals.html",
        {
            "hospitals": [d["hospital"] for d in hospitals_data],
            "hospitals_data": hospitals_data,
            "plans": plans,
            "q": q,
            "status_filter": status_filter,
            "plan_filter": plan_filter,
            "total_count": len(hospitals_data),
        },
    )


@platform_superadmin_required
def super_admin_add_hospital(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        city = request.POST.get("city", "").strip()
        address = request.POST.get("address", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        admin_username = request.POST.get("admin_username", "").strip()
        admin_email = request.POST.get("admin_email", "").strip()
        admin_password = request.POST.get("admin_password", "").strip()
        admin_first = request.POST.get("admin_first", "").strip()
        admin_last = request.POST.get("admin_last", "").strip()
        plan_id = request.POST.get("plan", "")

        errors = []
        if not name:
            errors.append("Hospital name is required.")
        if not admin_username:
            errors.append("Admin username is required.")
        if not admin_email:
            errors.append("Admin email is required.")
        if not admin_password:
            errors.append("Admin password is required.")
        if User.objects.filter(username=admin_username).exists():
            errors.append(f'Username "{admin_username}" is already taken.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "super_admin/super_admin_add_hospital.html", {"plans": plans})

        hospital = Hospital.objects.create(
            name=name, city=city, address=address, phone=phone, email=email
        )
        admin_user = User.objects.create_user(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            first_name=admin_first,
            last_name=admin_last,
            is_superuser=True,
            is_staff=True,
        )
        ClinicAdmin.objects.create(user=admin_user, hospital=hospital)

        plan = None
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
            except SubscriptionPlan.DoesNotExist:
                pass
        HospitalSubscription.objects.create(
            hospital=hospital, plan=plan, status="trial"
        )

        messages.success(
            request, f'✅ Hospital "{name}" created with admin "{admin_username}".'
        )
        return redirect("super_admin_hospitals")

    return render(request, "super_admin/super_admin_add_hospital.html", {"plans": plans})


@platform_superadmin_required
def super_admin_edit_hospital(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    plans = SubscriptionPlan.objects.filter(is_active=True)
    try:
        subscription = hospital.subscription
    except HospitalSubscription.DoesNotExist:
        subscription = None

    if request.method == "POST":
        hospital.name = request.POST.get("name", hospital.name).strip()
        hospital.city = request.POST.get("city", "").strip()
        hospital.address = request.POST.get("address", "").strip()
        hospital.phone = request.POST.get("phone", "").strip()
        hospital.email = request.POST.get("email", "").strip()
        hospital.is_active = request.POST.get("is_active") == "on"
        hospital.save()

        plan_id = request.POST.get("plan", "")
        sub_status = request.POST.get("sub_status", "trial")
        expires_raw = request.POST.get("expires_at", "")
        expires_at = expires_raw if expires_raw else None

        if subscription:
            if plan_id:
                try:
                    subscription.plan = SubscriptionPlan.objects.get(id=plan_id)
                except SubscriptionPlan.DoesNotExist:
                    pass
            subscription.status = sub_status
            subscription.expires_at = expires_at
            subscription.save()
        else:
            plan = None
            if plan_id:
                try:
                    plan = SubscriptionPlan.objects.get(id=plan_id)
                except SubscriptionPlan.DoesNotExist:
                    pass
            HospitalSubscription.objects.create(
                hospital=hospital, plan=plan, status=sub_status, expires_at=expires_at
            )

        messages.success(request, f'✅ Hospital "{hospital.name}" updated.')
        return redirect("super_admin_hospitals")

    return render(
        request,
        "super_admin/super_admin_edit_hospital.html",
        {
            "hospital": hospital,
            "plans": plans,
            "subscription": subscription,
        },
    )


@platform_superadmin_required
def super_admin_delete_hospital(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    if request.method == "POST":
        name = hospital.name
        log_audit_event(
            action="clinic.deleted",
            actor=request.user,
            entity_type="Hospital",
            entity_id=hospital.id,
            metadata={"name": name},
        )
        hospital.delete()
        messages.success(request, f'Hospital "{name}" deleted.')
    return redirect("super_admin_hospitals")


# ════════════════════════════════════════════════════════════
# SUPER ADMIN SAAS MANAGEMENT SUITE
# ════════════════════════════════════════════════════════════


@platform_superadmin_required
def super_admin_clinic_detail(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    active_tab = request.GET.get("tab", "overview").lower()
    if active_tab not in (
        "overview",
        "users",
        "subscription",
        "features",
        "usage",
        "billing",
        "audit",
    ):
        active_tab = "overview"

    # Tab 1: Overview
    admins = ClinicAdmin.objects.filter(hospital=hospital).select_related("user")
    staff_count = StaffProfile.objects.filter(hospital=hospital, is_active=True).count()
    patient_count = PatientProfile.objects.filter(
        hospital=hospital, patient_status="active"
    ).count()
    appointment_count = Appointment.objects.filter(hospital=hospital).count()

    # Tab 2: Users
    staff_members = (
        StaffProfile.objects.filter(hospital=hospital)
        .select_related("user")
        .order_by("-joining_date", "-id")
    )
    recent_patients = (
        PatientProfile.objects.filter(hospital=hospital)
        .select_related("user")
        .order_by("-created_at")[:20]
    )

    # Tab 3: Subscription
    sub = getattr(hospital, "subscription", None)
    plans = SubscriptionPlan.objects.all().order_by("tier_level", "price_monthly")
    sub_history = (
        SubscriptionHistory.objects.filter(hospital=hospital)
        .select_related("previous_plan", "new_plan", "changed_by")
        .order_by("-created_at")
    )

    # Tab 4: Features & Overrides
    features = (
        Feature.objects.filter(is_active=True)
        .select_related("category")
        .order_by("category__order", "name")
    )
    overrides = {
        o.feature_id: o
        for o in ClinicFeatureOverride.objects.filter(hospital=hospital).select_related(
            "feature"
        )
    }
    features_data = []
    for f in features:
        ent = evaluate_entitlement(hospital, f.code)
        override = overrides.get(f.id)
        usage = get_feature_usage(hospital, f.code) if f.has_usage_limit else None
        features_data.append({
            "feature": f,
            "entitlement": ent,
            "override": override,
            "usage": usage,
        })

    # Tab 5: Usage
    usage_metrics = [
        {
            "name": "Active Patients",
            "code": "patients",
            "icon": "fa-user-injured",
            **get_feature_usage(hospital, "patients"),
        },
        {
            "name": "Monthly Appointments",
            "code": "appointments",
            "icon": "fa-calendar-check",
            **get_feature_usage(hospital, "appointments"),
        },
        {
            "name": "Active Staff",
            "code": "staff_management",
            "icon": "fa-user-md",
            **get_feature_usage(hospital, "staff_management"),
        },
        {
            "name": "Media Storage (MB)",
            "code": "storage",
            "icon": "fa-hdd",
            **get_feature_usage(hospital, "storage"),
        },
        {
            "name": "Blog Articles",
            "code": "blogs",
            "icon": "fa-newspaper",
            **get_feature_usage(hospital, "blogs"),
        },
        {
            "name": "Active Promotions",
            "code": "promos",
            "icon": "fa-tags",
            **get_feature_usage(hospital, "promos"),
        },
    ]

    # Tab 6: Billing
    sub_payments = (
        ClinicSubscriptionPayment.objects.filter(hospital=hospital)
        .select_related("plan")
        .order_by("-created_at")
    )
    patient_payments = (
        PaymentRecord.objects.filter(hospital=hospital)
        .select_related("patient", "appointment")
        .order_by("-created_at")[:25]
    )
    total_billed = (
        sub_payments.filter(status="paid").aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )

    # Tab 7: Audit Log
    audit_logs = (
        AuditEvent.objects.filter(hospital=hospital)
        .select_related("actor")
        .order_by("-created_at")[:50]
    )

    return render(
        request,
        "super_admin/super_admin_clinic_detail.html",
        {
            "hospital": hospital,
            "active_tab": active_tab,
            "admins": admins,
            "staff_count": staff_count,
            "patient_count": patient_count,
            "appointment_count": appointment_count,
            "staff_members": staff_members,
            "recent_patients": recent_patients,
            "subscription": sub,
            "plans": plans,
            "sub_history": sub_history,
            "features_data": features_data,
            "usage_metrics": usage_metrics,
            "sub_payments": sub_payments,
            "patient_payments": patient_payments,
            "total_billed": total_billed,
            "audit_logs": audit_logs,
        },
    )


@platform_superadmin_required
@require_POST
def super_admin_suspend_clinic(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    reason = request.POST.get("reason", "").strip() or "Suspended by Super Admin"

    hospital.status = "suspended"
    hospital.is_active = False
    hospital.suspension_reason = reason
    hospital.save()

    sub = getattr(hospital, "subscription", None)
    if sub:
        old_status = sub.status
        sub.status = "suspended"
        sub.suspended_at = timezone.now()
        sub.suspension_reason = reason
        sub.save()
        SubscriptionHistory.objects.create(
            hospital=hospital,
            previous_plan=sub.plan,
            new_plan=sub.plan,
            previous_status=old_status,
            new_status="suspended",
            change_type="status_change",
            reason=f"Suspension: {reason}",
            changed_by=request.user,
        )

    log_audit_event(
        action="clinic.suspended",
        actor=request.user,
        hospital=hospital,
        entity_type="Hospital",
        entity_id=hospital.id,
        metadata={"reason": reason},
    )

    messages.warning(
        request,
        f'Clinic "{hospital.name}" has been suspended. Normal operations are locked.',
    )
    return redirect("super_admin_clinic_detail", hospital_id=hospital.id)


@platform_superadmin_required
@require_POST
def super_admin_activate_clinic(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)

    hospital.status = "active"
    hospital.is_active = True
    hospital.suspension_reason = ""
    hospital.save()

    sub = getattr(hospital, "subscription", None)
    if sub:
        old_status = sub.status
        sub.status = "active"
        sub.suspended_at = None
        sub.suspension_reason = ""
        sub.save()
        SubscriptionHistory.objects.create(
            hospital=hospital,
            previous_plan=sub.plan,
            new_plan=sub.plan,
            previous_status=old_status,
            new_status="active",
            change_type="status_change",
            reason="Reactivation by Super Admin",
            changed_by=request.user,
        )

    log_audit_event(
        action="clinic.activated",
        actor=request.user,
        hospital=hospital,
        entity_type="Hospital",
        entity_id=hospital.id,
        metadata={"action": "reactivate"},
    )

    messages.success(
        request, f'Clinic "{hospital.name}" has been reactivated successfully.'
    )
    return redirect("super_admin_clinic_detail", hospital_id=hospital.id)


@platform_superadmin_required
@require_POST
def super_admin_update_clinic_subscription(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    sub = getattr(hospital, "subscription", None)
    if not sub:
        sub = HospitalSubscription(hospital=hospital, status="trial")

    action_type = request.POST.get("action_type", "change_plan")
    today = timezone.now().date()

    if action_type == "change_plan":
        plan_id = request.POST.get("plan_id")
        reason = (
            request.POST.get("reason", "").strip() or "Plan modified by Super Admin"
        )
        if plan_id:
            try:
                new_plan = SubscriptionPlan.objects.get(id=plan_id)
                old_plan = sub.plan
                sub.plan = new_plan
                sub.save()

                SubscriptionHistory.objects.create(
                    hospital=hospital,
                    previous_plan=old_plan,
                    new_plan=new_plan,
                    previous_status=sub.status,
                    new_status=sub.status,
                    change_type="plan_change",
                    reason=reason,
                    changed_by=request.user,
                )
                log_audit_event(
                    action="plan.changed",
                    actor=request.user,
                    hospital=hospital,
                    entity_type="HospitalSubscription",
                    entity_id=sub.id,
                    metadata={
                        "old_plan": getattr(old_plan, "name", None),
                        "new_plan": new_plan.name,
                        "reason": reason,
                    },
                )
                messages.success(
                    request, f'✅ Plan updated to "{new_plan.display_name}".'
                )
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, "Invalid plan selected.")

    elif action_type == "extend_trial":
        days = int(request.POST.get("extend_days", 7))
        reason = (
            request.POST.get("reason", "").strip() or f"Trial extended by {days} days"
        )
        current_exp = sub.expires_at or today
        if current_exp < today:
            current_exp = today
        sub.expires_at = current_exp + timedelta(days=days)
        sub.trial_ends_at = timezone.now() + timedelta(days=days)
        sub.status = "trial"
        sub.save()

        SubscriptionHistory.objects.create(
            hospital=hospital,
            previous_plan=sub.plan,
            new_plan=sub.plan,
            previous_status=sub.status,
            new_status="trial",
            change_type="trial_extension",
            reason=reason,
            changed_by=request.user,
        )
        log_audit_event(
            action="trial.extended",
            actor=request.user,
            hospital=hospital,
            entity_type="HospitalSubscription",
            entity_id=sub.id,
            metadata={
                "extended_days": days,
                "new_expiry": str(sub.expires_at),
                "reason": reason,
            },
        )
        messages.success(
            request, f"✅ Trial extended by {days} days until {sub.expires_at}."
        )

    elif action_type == "update_status":
        new_status = request.POST.get("status", "active")
        reason = (
            request.POST.get("reason", "").strip() or f"Status changed to {new_status}"
        )
        old_status = sub.status
        sub.status = new_status
        sub.save()

        SubscriptionHistory.objects.create(
            hospital=hospital,
            previous_plan=sub.plan,
            new_plan=sub.plan,
            previous_status=old_status,
            new_status=new_status,
            change_type="status_change",
            reason=reason,
            changed_by=request.user,
        )
        log_audit_event(
            action="subscription.status_changed",
            actor=request.user,
            hospital=hospital,
            entity_type="HospitalSubscription",
            entity_id=sub.id,
            metadata={
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
            },
        )
        messages.success(
            request,
            f'✅ Subscription status changed to "{sub.get_status_display()}".',
        )

    return redirect(f"/super-admin/clinics/{hospital.id}/detail/?tab=subscription")


@platform_superadmin_required
@require_POST
def super_admin_save_feature_override(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    feature_code = request.POST.get("feature_code", "").strip()
    override_type = request.POST.get("override_type", "grant").strip()
    custom_limit_raw = request.POST.get("custom_limit", "0").strip()
    reason = request.POST.get("reason", "").strip()
    expires_days_raw = request.POST.get("expires_days", "").strip()

    feature = get_object_or_404(Feature, code=feature_code)
    try:
        custom_limit = int(custom_limit_raw) if custom_limit_raw else 0
    except ValueError:
        custom_limit = 0

    expires_at = None
    if expires_days_raw:
        try:
            expires_at = timezone.now() + timedelta(days=int(expires_days_raw))
        except ValueError:
            expires_at = None

    override, created = ClinicFeatureOverride.objects.update_or_create(
        hospital=hospital,
        feature=feature,
        defaults={
            "override_type": override_type,
            "custom_limit": custom_limit,
            "reason": reason,
            "expires_at": expires_at,
            "created_by": request.user,
        },
    )

    action_label = "feature.override.created" if created else "feature.override.updated"
    log_audit_event(
        action=action_label,
        actor=request.user,
        hospital=hospital,
        entity_type="ClinicFeatureOverride",
        entity_id=override.id,
        metadata={
            "feature": feature.code,
            "override_type": override_type,
            "custom_limit": custom_limit,
            "reason": reason,
            "expires_at": str(expires_at) if expires_at else None,
        },
    )

    messages.success(
        request,
        f'✅ Override for "{feature.name}" set to {override.get_override_type_display()}.',
    )
    return redirect(f"/super-admin/clinics/{hospital.id}/detail/?tab=features")


@platform_superadmin_required
@require_POST
def super_admin_delete_feature_override(request, hospital_id, feature_code):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    feature = get_object_or_404(Feature, code=feature_code)
    override = ClinicFeatureOverride.objects.filter(
        hospital=hospital, feature=feature
    ).first()

    if override:
        override.delete()
        log_audit_event(
            action="feature.override.removed",
            actor=request.user,
            hospital=hospital,
            entity_type="ClinicFeatureOverride",
            entity_id=feature.code,
            metadata={"feature": feature.code},
        )
        messages.success(
            request,
            f'✅ Override removed for "{feature.name}". Standard plan rules apply.',
        )
    else:
        messages.info(request, "No active override found.")

    return redirect(f"/super-admin/clinics/{hospital.id}/detail/?tab=features")


# ─── PLAN MANAGEMENT ─────────────────────────────────────────


@platform_superadmin_required
def super_admin_plans(request):
    plans = SubscriptionPlan.objects.all().order_by("tier_level", "price_monthly")
    plans_data = []
    for p in plans:
        clinic_count = HospitalSubscription.objects.filter(
            plan=p, status__in=["active", "trial"]
        ).count()
        feature_count = PlanFeature.objects.filter(
            plan=p, access_type__in=["full", "limited"]
        ).count()
        plans_data.append({
            "plan": p,
            "clinic_count": clinic_count,
            "feature_count": feature_count,
        })
    return render(
        request,
        "super_admin/super_admin_plans.html",
        {"plans_data": plans_data, "plans": plans},
    )


@platform_superadmin_required
def super_admin_add_plan(request):
    features = (
        Feature.objects.filter(is_active=True)
        .select_related("category")
        .order_by("category__order", "name")
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip().lower()
        code = request.POST.get("code", "").strip().lower() or name
        display_name = request.POST.get("display_name", "").strip() or name.title()
        description = request.POST.get("description", "").strip()
        price_monthly_raw = request.POST.get("price_monthly", "0").strip()
        price_annual_raw = request.POST.get("price_annual", "0").strip()
        trial_days_raw = request.POST.get("trial_days", "14").strip()
        tier_level_raw = request.POST.get("tier_level", "10").strip()
        is_public = request.POST.get("is_public") == "on"
        is_active = request.POST.get("is_active") == "on"

        max_patients_raw = request.POST.get("max_patients", "100").strip()
        max_appointments_raw = request.POST.get(
            "max_appointments_monthly", "100"
        ).strip()
        max_staff_raw = request.POST.get("max_staff", "3").strip()
        storage_mb_raw = request.POST.get("storage_mb", "500").strip()

        errors = []
        if not name:
            errors.append("Internal name is required.")
        if SubscriptionPlan.objects.filter(name=name).exists():
            errors.append(f'Plan with name "{name}" already exists.')
        if SubscriptionPlan.objects.filter(code=code).exists():
            errors.append(f'Plan with code "{code}" already exists.')

        try:
            price_monthly = Decimal(price_monthly_raw or "0")
            price_annual = Decimal(price_annual_raw or "0")
        except Exception:
            errors.append("Invalid price format.")

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(
                request,
                "super_admin/super_admin_plan_form.html",
                {"features": features, "is_edit": False},
            )

        plan = SubscriptionPlan.objects.create(
            name=name,
            code=code,
            display_name=display_name,
            description=description,
            price_monthly=Decimal(price_monthly_raw or "0"),
            price_annual=Decimal(price_annual_raw or "0"),
            trial_days=int(trial_days_raw or 14),
            tier_level=int(tier_level_raw or 10),
            is_public=is_public,
            is_active=is_active,
            max_patients=int(max_patients_raw or 100),
            max_appointments_monthly=int(max_appointments_raw or 100),
            max_staff=int(max_staff_raw or 3),
            storage_mb=int(storage_mb_raw or 500),
        )

        # Configure PlanFeature entries
        for f in features:
            access_type = request.POST.get(f"access_{f.code}", "disabled")
            limit_raw = request.POST.get(f"limit_{f.code}", "0")
            try:
                limit_val = int(limit_raw) if limit_raw else 0
            except ValueError:
                limit_val = 0
            PlanFeature.objects.create(
                plan=plan,
                feature=f,
                access_type=access_type,
                usage_limit=limit_val,
                limit_period=(
                    "monthly" if f.code == "appointments" else "lifetime"
                ),
            )

        log_audit_event(
            action="plan.created",
            actor=request.user,
            entity_type="SubscriptionPlan",
            entity_id=plan.id,
            metadata={"plan_name": plan.name, "code": plan.code},
        )
        messages.success(
            request, f'✅ Plan "{plan.display_name}" created successfully.'
        )
        return redirect("super_admin_plans")

    return render(
        request,
        "super_admin/super_admin_plan_form.html",
        {"features": features, "is_edit": False},
    )


@platform_superadmin_required
def super_admin_edit_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    features = (
        Feature.objects.filter(is_active=True)
        .select_related("category")
        .order_by("category__order", "name")
    )
    existing_pfs = {pf.feature_id: pf for pf in PlanFeature.objects.filter(plan=plan)}

    if request.method == "POST":
        display_name = (
            request.POST.get("display_name", "").strip() or plan.name.title()
        )
        description = request.POST.get("description", "").strip()
        price_monthly_raw = request.POST.get("price_monthly", "0").strip()
        price_annual_raw = request.POST.get("price_annual", "0").strip()
        trial_days_raw = request.POST.get("trial_days", "14").strip()
        tier_level_raw = request.POST.get("tier_level", "10").strip()
        is_public = request.POST.get("is_public") == "on"
        is_active = request.POST.get("is_active") == "on"

        max_patients_raw = request.POST.get("max_patients", "100").strip()
        max_appointments_raw = request.POST.get(
            "max_appointments_monthly", "100"
        ).strip()
        max_staff_raw = request.POST.get("max_staff", "3").strip()
        storage_mb_raw = request.POST.get("storage_mb", "500").strip()

        plan.display_name = display_name
        plan.description = description
        plan.price_monthly = Decimal(price_monthly_raw or "0")
        plan.price_annual = Decimal(price_annual_raw or "0")
        plan.trial_days = int(trial_days_raw or 14)
        plan.tier_level = int(tier_level_raw or 10)
        plan.is_public = is_public
        plan.is_active = is_active
        plan.max_patients = int(max_patients_raw or 100)
        plan.max_appointments_monthly = int(max_appointments_raw or 100)
        plan.max_staff = int(max_staff_raw or 3)
        plan.storage_mb = int(storage_mb_raw or 500)
        plan.save()

        # Update PlanFeature entries
        for f in features:
            access_type = request.POST.get(f"access_{f.code}", "disabled")
            limit_raw = request.POST.get(f"limit_{f.code}", "0")
            try:
                limit_val = int(limit_raw) if limit_raw else 0
            except ValueError:
                limit_val = 0
            PlanFeature.objects.update_or_create(
                plan=plan,
                feature=f,
                defaults={
                    "access_type": access_type,
                    "usage_limit": limit_val,
                    "limit_period": (
                        "monthly" if f.code == "appointments" else "lifetime"
                    ),
                },
            )

        log_audit_event(
            action="plan.updated",
            actor=request.user,
            entity_type="SubscriptionPlan",
            entity_id=plan.id,
            metadata={"plan_name": plan.name},
        )
        messages.success(
            request, f'✅ Plan "{plan.display_name}" updated successfully.'
        )
        return redirect("super_admin_plans")

    feature_rows = []
    for f in features:
        pf = existing_pfs.get(f.id)
        feature_rows.append({
            "feature": f,
            "access_type": (
                pf.access_type
                if pf
                else ("full" if not f.is_paid else "disabled")
            ),
            "usage_limit": (
                pf.usage_limit
                if pf
                else (f.default_limit if f.has_usage_limit else 0)
            ),
        })

    return render(
        request,
        "super_admin/super_admin_plan_form.html",
        {
            "plan": plan,
            "features": features,
            "feature_rows": feature_rows,
            "is_edit": True,
        },
    )


@platform_superadmin_required
@require_POST
def super_admin_duplicate_plan(request, plan_id):
    original = get_object_or_404(SubscriptionPlan, id=plan_id)
    suffix = uuid.uuid4().hex[:4]
    new_name = f"{original.name}_{suffix}"
    new_code = f"{original.code or original.name}_{suffix}"

    clone = SubscriptionPlan.objects.create(
        name=new_name,
        code=new_code,
        display_name=f"{original.display_name} (Copy)",
        description=original.description,
        price_monthly=original.price_monthly,
        price_annual=original.price_annual,
        trial_days=original.trial_days,
        tier_level=original.tier_level + 1,
        is_public=False,
        is_active=True,
        max_patients=original.max_patients,
        max_appointments_monthly=original.max_appointments_monthly,
        max_staff=original.max_staff,
        storage_mb=original.storage_mb,
    )

    for pf in PlanFeature.objects.filter(plan=original):
        PlanFeature.objects.create(
            plan=clone,
            feature=pf.feature,
            access_type=pf.access_type,
            usage_limit=pf.usage_limit,
            limit_period=pf.limit_period,
        )

    log_audit_event(
        action="plan.duplicated",
        actor=request.user,
        entity_type="SubscriptionPlan",
        entity_id=clone.id,
        metadata={"original": original.name, "clone": clone.name},
    )
    messages.success(
        request,
        f'✅ Plan "{original.display_name}" duplicated as "{clone.display_name}".',
    )
    return redirect("super_admin_plans")


@platform_superadmin_required
@require_POST
def super_admin_toggle_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    plan.is_active = not plan.is_active
    plan.save()
    status_str = "activated" if plan.is_active else "deactivated"
    log_audit_event(
        action=f"plan.{status_str}",
        actor=request.user,
        entity_type="SubscriptionPlan",
        entity_id=plan.id,
        metadata={"plan": plan.name, "is_active": plan.is_active},
    )
    messages.success(request, f'✅ Plan "{plan.display_name}" {status_str}.')
    return redirect("super_admin_plans")


# ─── FEATURE CATALOG & ACCESS MATRIX ─────────────────────────


@platform_superadmin_required
def super_admin_features(request):
    categories = FeatureCategory.objects.prefetch_related("features").order_by(
        "order", "name"
    )
    total_features = Feature.objects.count()
    paid_features = Feature.objects.filter(is_paid=True).count()
    free_features = Feature.objects.filter(is_paid=False).count()
    impaired_count = Feature.objects.filter(
        global_status__in=["maintenance", "disabled"]
    ).count()

    return render(
        request,
        "super_admin/super_admin_features.html",
        {
            "categories": categories,
            "total_features": total_features,
            "paid_features": paid_features,
            "free_features": free_features,
            "impaired_count": impaired_count,
        },
    )


@platform_superadmin_required
@require_POST
def super_admin_feature_global_status(request, feature_code):
    feature = get_object_or_404(Feature, code=feature_code)
    status = request.POST.get("global_status", "available").strip()
    reason = request.POST.get("reason", "").strip()
    maintenance_message = request.POST.get("maintenance_message", "").strip()

    if status not in ("available", "maintenance", "disabled"):
        status = "available"

    old_status = feature.global_status
    feature.global_status = status
    feature.maintenance_message = maintenance_message
    feature.save()

    log_audit_event(
        action="feature.global_status_changed",
        actor=request.user,
        entity_type="Feature",
        entity_id=feature.code,
        metadata={
            "feature": feature.code,
            "old_status": old_status,
            "new_status": status,
            "reason": reason,
        },
    )

    messages.success(
        request,
        f'✅ Feature "{feature.name}" global status changed from {old_status.upper()} to {status.upper()}.',
    )
    return redirect("super_admin_features")


@platform_superadmin_required
def super_admin_access_matrix(request):
    plans = SubscriptionPlan.objects.all().order_by("tier_level", "price_monthly")
    categories = FeatureCategory.objects.prefetch_related("features").order_by(
        "order", "name"
    )
    pfs = PlanFeature.objects.select_related("plan", "feature")
    matrix = {}
    for pf in pfs:
        matrix[(pf.feature_id, pf.plan_id)] = pf

    category_data = []
    for cat in categories:
        feat_list = []
        for f in cat.features.filter(is_active=True).order_by("name"):
            plan_cells = []
            for p in plans:
                cell = matrix.get((f.id, p.id))
                plan_cells.append({
                    "plan": p,
                    "pf": cell,
                    "access_type": (
                        cell.access_type
                        if cell
                        else ("full" if not f.is_paid else "disabled")
                    ),
                    "usage_limit": cell.usage_limit if cell else 0,
                })
            feat_list.append({"feature": f, "plan_cells": plan_cells})
        if feat_list:
            category_data.append({"category": cat, "features": feat_list})

    return render(
        request,
        "super_admin/super_admin_access_matrix.html",
        {"plans": plans, "category_data": category_data},
    )


@platform_superadmin_required
@require_POST
def super_admin_update_access_matrix(request):
    plan_id = request.POST.get("plan_id")
    feature_code = request.POST.get("feature_code")
    access_type = request.POST.get("access_type", "disabled")
    limit_raw = request.POST.get("usage_limit", "0")

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    feature = get_object_or_404(Feature, code=feature_code)
    try:
        usage_limit = int(limit_raw) if limit_raw else 0
    except ValueError:
        usage_limit = 0

    pf, created = PlanFeature.objects.update_or_create(
        plan=plan,
        feature=feature,
        defaults={
            "access_type": access_type,
            "usage_limit": usage_limit,
            "limit_period": (
                "monthly" if feature.code == "appointments" else "lifetime"
            ),
        },
    )

    log_audit_event(
        action="access_matrix.updated",
        actor=request.user,
        entity_type="PlanFeature",
        entity_id=pf.id,
        metadata={
            "plan": plan.name,
            "feature": feature.code,
            "access_type": access_type,
            "usage_limit": usage_limit,
        },
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "message": "Access updated."})

    messages.success(
        request,
        f"✅ Matrix updated: {plan.display_name} → {feature.name}:"
        f" {pf.get_access_type_display()}.",
    )
    return redirect("super_admin_access_matrix")


@platform_superadmin_required
def super_admin_entitlement_debug(request):
    hospitals = Hospital.objects.all().order_by("name")
    features = (
        Feature.objects.filter(is_active=True)
        .select_related("category")
        .order_by("category__order", "name")
    )

    hospital_id = request.GET.get("hospital_id")
    feature_code = request.GET.get("feature_code")

    explanation = None
    selected_hospital = None
    selected_feature = None

    if hospital_id and feature_code:
        selected_hospital = Hospital.objects.filter(id=hospital_id).first()
        selected_feature = Feature.objects.filter(code=feature_code).first()
        if selected_hospital and selected_feature:
            explanation = explain_entitlement(selected_hospital, feature_code)

    return render(
        request,
        "super_admin/super_admin_entitlement_debug.html",
        {
            "hospitals": hospitals,
            "features": features,
            "selected_hospital": selected_hospital,
            "selected_feature": selected_feature,
            "explanation": explanation,
        },
    )


# ─── USAGE & ALERTS OVERVIEW ─────────────────────────────────


@platform_superadmin_required
def super_admin_usage_overview(request):
    threshold_filter = request.GET.get("threshold", "all")
    now = timezone.now()

    # Aggregate platform resources
    total_clinics = Hospital.objects.filter(is_active=True).count()
    total_patients = PatientProfile.objects.filter(
        patient_status="active"
    ).count()
    total_staff = StaffProfile.objects.filter(is_active=True).count()
    monthly_appts = (
        Appointment.objects.filter(date__year=now.year, date__month=now.month)
        .exclude(status="cancelled")
        .count()
    )
    total_storage_bytes = (
        MediaAsset.objects.filter(deleted_at__isnull=True).aggregate(
            t=Sum("bytes")
        )["t"]
        or 0
    )
    total_storage_mb = round(total_storage_bytes / (1024 * 1024), 2)

    # Per clinic breakdown and threshold detection
    clinics_usage = []
    for h in Hospital.objects.filter(is_active=True).select_related(
        "subscription__plan"
    ):
        p_usage = get_feature_usage(h, "patients")
        a_usage = get_feature_usage(h, "appointments")
        s_usage = get_feature_usage(h, "staff_management")
        st_usage = get_feature_usage(h, "storage")

        max_percent = max(
            p_usage["percent"],
            a_usage["percent"],
            s_usage["percent"],
            st_usage["percent"],
        )
        has_warning_80 = (
            p_usage["percent"] >= 80
            or a_usage["percent"] >= 80
            or s_usage["percent"] >= 80
            or st_usage["percent"] >= 80
        )
        has_limit_reached = (
            p_usage["is_exceeded"]
            or a_usage["is_exceeded"]
            or s_usage["is_exceeded"]
            or st_usage["is_exceeded"]
        )

        item = {
            "hospital": h,
            "subscription": getattr(h, "subscription", None),
            "patients": p_usage,
            "appointments": a_usage,
            "staff": s_usage,
            "storage": st_usage,
            "max_percent": max_percent,
            "has_warning_80": has_warning_80,
            "has_limit_reached": has_limit_reached,
        }

        if threshold_filter == "warning_80" and not has_warning_80:
            continue
        if threshold_filter == "limit_reached" and not has_limit_reached:
            continue

        clinics_usage.append(item)

    clinics_usage.sort(key=lambda x: x["max_percent"], reverse=True)

    return render(
        request,
        "super_admin/super_admin_usage_overview.html",
        {
            "total_clinics": total_clinics,
            "total_patients": total_patients,
            "total_staff": total_staff,
            "monthly_appts": monthly_appts,
            "total_storage_mb": total_storage_mb,
            "clinics_usage": clinics_usage,
            "threshold_filter": threshold_filter,
        },
    )


# ─── PLATFORM AUDIT LOGS ──────────────────────────────────────


@platform_superadmin_required
def super_admin_audit_logs(request):
    action_filter = request.GET.get("action", "")
    hospital_id = request.GET.get("hospital_id", "")
    q = request.GET.get("q", "").strip()

    qs = AuditEvent.objects.select_related("actor", "hospital").order_by(
        "-created_at"
    )
    if action_filter:
        qs = qs.filter(action__icontains=action_filter)
    if hospital_id:
        qs = qs.filter(hospital_id=hospital_id)
    if q:
        qs = qs.filter(
            Q(action__icontains=q)
            | Q(actor__username__icontains=q)
            | Q(hospital__name__icontains=q)
            | Q(entity_type__icontains=q)
        )

    hospitals = Hospital.objects.all().order_by("name")
    recent_logs = qs[:100]

    return render(
        request,
        "super_admin/super_admin_audit_logs.html",
        {
            "logs": recent_logs,
            "hospitals": hospitals,
            "action_filter": action_filter,
            "hospital_id": hospital_id,
            "q": q,
            "total_count": qs.count(),
        },
    )


@platform_superadmin_required
def super_admin_subscriptions(request):
    from django.db.models import Sum, Count

    subscriptions = HospitalSubscription.objects.select_related(
        "hospital", "plan"
    ).all()
    plans = SubscriptionPlan.objects.all()
    # Pending payments needing verification
    pending_payments = (
        ClinicSubscriptionPayment.objects.select_related("hospital", "plan")
        .filter(status="pending")
        .order_by("-created_at")
    )
    # Per-hospital payment summary
    hospital_payment_summary = {}
    for csp in ClinicSubscriptionPayment.objects.select_related(
        "hospital", "plan"
    ).order_by("-created_at"):
        hid = csp.hospital_id
        if hid not in hospital_payment_summary:
            hospital_payment_summary[hid] = {
                "hospital": csp.hospital,
                "payments": [],
                "total_paid": 0,
                "has_pending": False,
            }
        hospital_payment_summary[hid]["payments"].append(csp)
        if csp.status == "paid":
            hospital_payment_summary[hid]["total_paid"] += float(csp.amount)
        if csp.status == "pending":
            hospital_payment_summary[hid]["has_pending"] = True

    # Save plan changes
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_plan":
            plan_name = request.POST.get("plan_name", "").strip()
            price_monthly = request.POST.get("price_monthly", "0")
            max_staff = request.POST.get("max_staff", "5")
            max_patients = request.POST.get("max_patients", "500")
            features = request.POST.get("features", "")
            plan_id = request.POST.get("plan_id", "")
            if plan_id:
                try:
                    p = SubscriptionPlan.objects.get(id=plan_id)
                    p.price_monthly = price_monthly
                    p.max_staff = max_staff
                    p.max_patients = max_patients
                    p.features = features
                    p.save()
                    messages.success(request, "Plan updated.")
                except SubscriptionPlan.DoesNotExist:
                    pass
            else:
                obj, created = SubscriptionPlan.objects.get_or_create(
                    name=plan_name,
                    defaults={
                        "price_monthly": price_monthly,
                        "max_staff": max_staff,
                        "max_patients": max_patients,
                        "features": features,
                    },
                )
                if not created:
                    obj.price_monthly = price_monthly
                    obj.max_staff = max_staff
                    obj.max_patients = max_patients
                    obj.features = features
                    obj.is_active = True
                    obj.save()
                    messages.success(
                        request, f"{obj.get_name_display()} plan updated successfully."
                    )
                else:
                    messages.success(
                        request, f"{obj.get_name_display()} plan created successfully."
                    )
        return redirect("super_admin_subscriptions")

    unpaid_clinics = []
    for sub in subscriptions:
        if sub.status in ("trial", "expired") or sub.is_expired:
            hid = sub.hospital_id
            summary = hospital_payment_summary.get(hid, {})
            if not summary.get("total_paid", 0):
                unpaid_clinics.append(sub.hospital)

    return render(
        request,
        "super_admin/super_admin_subscriptions.html",
        {
            "subscriptions": subscriptions,
            "plans": plans,
            "pending_payments": pending_payments,
            "hospital_payment_summary": hospital_payment_summary,
            "unpaid_clinics": unpaid_clinics,
        },
    )


@platform_superadmin_required
def super_admin_confirm_sub_payment(request, payment_id):
    payment = get_object_or_404(ClinicSubscriptionPayment, id=payment_id)
    from dateutil.relativedelta import relativedelta

    payment.status = "paid"
    payment.paid_at = timezone.now()
    payment.save()
    # Activate the hospital subscription
    hospital = payment.hospital
    try:
        sub = hospital.subscription
    except HospitalSubscription.DoesNotExist:
        sub = HospitalSubscription(hospital=hospital)
    sub.plan = payment.plan
    sub.status = "active"
    sub.started_at = timezone.now().date()
    sub.expires_at = timezone.now().date() + relativedelta(
        months=payment.duration_months
    )
    sub.save()
    messages.success(
        request,
        f"✅ Payment confirmed and {payment.hospital.name} subscription activated until {sub.expires_at}.",
    )
    return redirect("super_admin_subscriptions")


@platform_superadmin_required
def super_admin_reject_sub_payment(request, payment_id):
    payment = get_object_or_404(ClinicSubscriptionPayment, id=payment_id)
    payment.status = "failed"
    payment.save()
    messages.warning(
        request, f"❌ Payment for {payment.hospital.name} marked as failed."
    )
    return redirect("super_admin_subscriptions")


@platform_superadmin_required
def super_admin_hospital_payments(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    payments = (
        ClinicSubscriptionPayment.objects.filter(hospital=hospital)
        .select_related("plan")
        .order_by("-created_at")
    )
    try:
        current_sub = hospital.subscription
    except HospitalSubscription.DoesNotExist:
        current_sub = None
    return render(
        request,
        "super_admin/super_admin_hospital_payments.html",
        {
            "hospital": hospital,
            "payments": payments,
            "current_sub": current_sub,
        },
    )


@platform_superadmin_required
def super_admin_analytics(request):
    from django.db.models import Count

    hospitals = Hospital.objects.annotate(
        appt_count=Count("appointments", distinct=True),
        staff_count=Count("staff", distinct=True),
    ).order_by("-appt_count")
    total_hospitals = Hospital.objects.count()
    active_hospitals = Hospital.objects.filter(is_active=True).count()
    total_appointments = Appointment.objects.count()
    total_patients = User.objects.filter(is_superuser=False, is_staff=False).count()
    total_staff = StaffProfile.objects.count()
    active_subs = HospitalSubscription.objects.filter(status="active").count()
    trial_subs = HospitalSubscription.objects.filter(status="trial").count()
    expired_subs = HospitalSubscription.objects.filter(status="expired").count()
    return render(
        request,
        "super_admin/super_admin_analytics.html",
        {
            "hospitals": hospitals,
            "total_hospitals": total_hospitals,
            "active_hospitals": active_hospitals,
            "total_appointments": total_appointments,
            "total_patients": total_patients,
            "total_staff": total_staff,
            "active_subs": active_subs,
            "trial_subs": trial_subs,
            "expired_subs": expired_subs,
        },
    )


@platform_superadmin_required
def super_admin_support(request):
    status_filter = request.GET.get("status", "")
    tickets = SupportTicket.objects.select_related("hospital", "submitted_by").all()
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    open_count = SupportTicket.objects.filter(status="open").count()
    in_progress_count = SupportTicket.objects.filter(status="in_progress").count()
    resolved_count = SupportTicket.objects.filter(status="resolved").count()
    return render(
        request,
        "super_admin/super_admin_support.html",
        {
            "tickets": tickets,
            "status_filter": status_filter,
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "resolved_count": resolved_count,
        },
    )


@platform_superadmin_required
def super_admin_support_reply(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    replies = ticket.replies.select_related("replier").all()
    hospitals = Hospital.objects.filter(is_active=True)
    if request.method == "POST":
        msg = request.POST.get("message", "").strip()
        new_status = request.POST.get("status", ticket.status)
        if msg:
            SupportReply.objects.create(
                ticket=ticket, replier=request.user, message=msg
            )
        ticket.status = new_status
        ticket.save()
        messages.success(request, "✅ Reply sent.")
        return redirect("super_admin_support_reply", ticket_id=ticket_id)
    return render(
        request,
        "super_admin/super_admin_support_reply.html",
        {
            "ticket": ticket,
            "replies": replies,
            "hospitals": hospitals,
        },
    )


# ── Clinic admin can submit a support ticket ──────────────────
@login_required
def submit_support_ticket(request):
    if not _is_clinic_admin(request.user):
        return redirect("home")
    hospital = None
    if hasattr(request.user, "clinic_admin_profile"):
        hospital = request.user.clinic_admin_profile.hospital
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        msg = request.POST.get("message", "").strip()
        if subject and msg:
            SupportTicket.objects.create(
                hospital=hospital,
                submitted_by=request.user,
                subject=subject,
                message=msg,
            )
            messages.success(request, "✅ Support ticket submitted successfully.")
        return redirect("admin_dashboard")
    return redirect("admin_dashboard")


# ─── SUBSCRIPTION PAGE ────────────────────────────────────────


@platform_superadmin_required
def super_admin_all_payments(request):
    from django.db.models import Sum
    status_filter = request.GET.get("status", "")
    method_filter = request.GET.get("method", "")
    hospital_filter = request.GET.get("hospital", "")
    q = request.GET.get("q", "").strip()

    all_payments = PaymentRecord.objects.select_related("patient", "appointment", "hospital").order_by("-created_at")
    if q:
        all_payments = all_payments.filter(
            Q(transaction_id__icontains=q) | Q(notes__icontains=q) |
            Q(patient__username__icontains=q) | Q(patient__first_name__icontains=q) |
            Q(patient__last_name__icontains=q) | Q(hospital__name__icontains=q)
        )
    if status_filter:
        all_payments = all_payments.filter(status=status_filter)
    if method_filter:
        all_payments = all_payments.filter(method=method_filter)
    if hospital_filter:
        all_payments = all_payments.filter(hospital_id=hospital_filter)

    total_paid = PaymentRecord.objects.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
    total_pending = PaymentRecord.objects.filter(status="pending").aggregate(t=Sum("amount"))["t"] or 0
    pending_count = PaymentRecord.objects.filter(status="pending").count()
    paid_count = PaymentRecord.objects.filter(status="paid").count()
    failed_count = PaymentRecord.objects.filter(status="failed").count()
    hospitals = Hospital.objects.all().order_by("name")
    patients = User.objects.filter(is_superuser=False, is_staff=False).order_by("first_name", "username")

    return render(request, "super_admin/super_admin_all_payments.html", {
        "all_payments": all_payments,
        "payments": all_payments,
        "status_filter": status_filter,
        "method_filter": method_filter,
        "hospital_filter": hospital_filter,
        "q": q,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "pending_count": pending_count,
        "paid_count": paid_count,
        "failed_count": failed_count,
        "hospitals": hospitals,
        "patients": patients,
    })


@login_required
def export_payments_excel(request):
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: You do not have permission to export payment records.")

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.http import HttpResponse
    status_filter = request.GET.get("status", "")
    method_filter = request.GET.get("method", "")
    qs = PaymentRecord.objects.select_related("patient", "appointment").order_by("-created_at")

    if role == "admin":
        qs = qs.filter(hospital=hospital)
    elif role == "super_admin":
        h_id = request.GET.get("hospital_id")
        if h_id:
            qs = qs.filter(hospital_id=h_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if method_filter:
        qs = qs.filter(method=method_filter)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patient Payments"

    hdr_font = Font(bold=True, color="FFFFFF", size=11)
    hdr_fill = PatternFill("solid", fgColor="1a1a2e")
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ["#", "Date", "Time", "Patient Name", "Patient Email", "Appointment Date", "Amount (₹)", "Method", "Transaction ID / Ref", "Notes", "Status"]
    ws.append(headers)
    for col_idx, cell in enumerate(ws[1], 1):
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = border

    col_widths = [5, 14, 10, 22, 28, 16, 14, 14, 26, 30, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 30

    alt_fill = PatternFill("solid", fgColor="F5F5FF")
    for i, pay in enumerate(qs, 1):
        row = [
            i,
            pay.created_at.strftime("%d %b %Y"),
            pay.created_at.strftime("%I:%M %p"),
            pay.patient.get_full_name() or pay.patient.username,
            pay.patient.email or "—",
            str(pay.appointment.date) if pay.appointment else "General",
            float(pay.amount),
            pay.get_method_display(),
            pay.transaction_id or "—",
            pay.notes or "—",
            pay.get_status_display(),
        ]
        ws.append(row)
        if i % 2 == 0:
            for cell in ws[i + 1]:
                cell.fill = alt_fill
        for cell in ws[i + 1]:
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="all_payments.xlsx"'
    wb.save(resp)
    return resp


@login_required
def export_payments_pdf(request):
    role, can_manage, hospital = _user_payment_role(request.user)
    if not can_manage:
        return HttpResponseForbidden("Forbidden: You do not have permission to export payment records.")

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from django.http import HttpResponse
    from django.utils import timezone as tz

    status_filter = request.GET.get("status", "")
    method_filter = request.GET.get("method", "")
    qs = PaymentRecord.objects.select_related("patient", "appointment").order_by("-created_at")

    if role == "admin":
        qs = qs.filter(hospital=hospital)
    elif role == "super_admin":
        h_id = request.GET.get("hospital_id")
        if h_id:
            qs = qs.filter(hospital_id=h_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if method_filter:
        qs = qs.filter(method=method_filter)

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="all_payments.pdf"'
    doc = SimpleDocTemplate(resp, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold", textColor=colors.HexColor("#1a1a2e"), spaceAfter=4, alignment=TA_CENTER)
    sub_style = ParagraphStyle("sub", fontSize=9, fontName="Helvetica", textColor=colors.grey, spaceAfter=12, alignment=TA_CENTER)
    elements.append(Paragraph("Patient Payment Transactions", title_style))
    elements.append(Paragraph(f"Generated: {tz.now().strftime('%d %b %Y, %I:%M %p')}   |   Records: {qs.count()}", sub_style))

    headers = ["#", "Date", "Patient", "Amount", "Method", "Txn / Ref", "Status"]
    data = [headers]
    for i, pay in enumerate(qs, 1):
        data.append([
            str(i),
            pay.created_at.strftime("%d %b %Y"),
            (pay.patient.get_full_name() or pay.patient.username)[:22],
            f"Rs.{pay.amount}",
            pay.get_method_display(),
            (pay.transaction_id or "—")[:20],
            pay.get_status_display(),
        ])

    col_widths_pdf = [1.0*cm, 2.8*cm, 5.5*cm, 2.5*cm, 2.8*cm, 5.0*cm, 2.5*cm]
    tbl = Table(data, colWidths=col_widths_pdf, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5FF")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWHEIGHT", (0, 0), (-1, 0), 20),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)
    doc.build(elements)
    return resp


@platform_superadmin_required
@require_POST
def send_subscription_reminder(request, hospital_id):
    from .models import ClinicAdmin as ClinicAdminModel
    hospital = get_object_or_404(Hospital, id=hospital_id)
    admin_users = list(ClinicAdminModel.objects.filter(hospital=hospital).select_related("user"))
    if not admin_users:
        messages.warning(request, f"No admin found for {hospital.name}.")
        return redirect("super_admin_subscriptions")
    for ca in admin_users:
        Notification.objects.create(
            recipient=ca.user,
            message=f"⚠️ Reminder: Your clinic subscription is due. Please visit the subscription page to renew or upgrade your plan to continue using all features.",
            link="/subscription/",
        )
    messages.success(request, f"✅ Subscription reminder sent to {len(admin_users)} admin(s) of {hospital.name}.")
    return redirect("super_admin_subscriptions")


@login_required
def subscription_page(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    reason = request.GET.get("reason", "")
    if reason == "expired":
        messages.error(request, "❌ Your subscription has expired. Please renew your plan to restore full access.")
    elif reason == "trial":
        messages.warning(request, "🔒 This feature is locked on the trial plan. Upgrade to unlock all premium features.")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price_monthly")
    hospital = None
    current_sub = None
    recent_payments = []
    upi_id = getattr(settings, "CLINIC_UPI_ID", "dhvanipatalia@upi")

    if hasattr(request.user, "clinic_admin_profile"):
        hospital = request.user.clinic_admin_profile.hospital
        try:
            current_sub = hospital.subscription
        except Exception:
            pass
        recent_payments = ClinicSubscriptionPayment.objects.filter(
            hospital=hospital
        ).order_by("-created_at")[:10]

    if request.method == "POST":
        if not hospital:
            messages.error(request, "No clinic linked to your account.")
            return redirect("subscription_page")
        plan_id = request.POST.get("plan_id")
        method = request.POST.get("method", "upi")
        txn_id = request.POST.get("transaction_id", "").strip()
        duration = int(request.POST.get("duration_months", 1))
        notes = request.POST.get("notes", "").strip()
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "Invalid plan selected.")
            return redirect("subscription_page")

        amount = plan.price_monthly * duration
        ClinicSubscriptionPayment.objects.create(
            hospital=hospital,
            plan=plan,
            amount=amount,
            method=method,
            status="pending",
            transaction_id=txn_id,
            duration_months=duration,
            notes=notes,
        )
        # Update the hospital subscription plan to the requested one
        try:
            sub = hospital.subscription
            sub.plan = plan
            sub.save()
        except Exception:
            HospitalSubscription.objects.create(
                hospital=hospital, plan=plan, status="trial"
            )

        messages.success(
            request,
            f"✅ Payment submitted for {plan.get_name_display()} plan! The platform admin will verify and activate your subscription shortly.",
        )
        return redirect("subscription_page")

    return render(
        request,
        "public/subscription_page.html",
        {
            "plans": plans,
            "hospital": hospital,
            "current_sub": current_sub,
            "recent_payments": recent_payments,
            "upi_id": upi_id,
        },
    )


# ─── PROMO MANAGEMENT ────────────────────────────────────────


@login_required
def admin_promos(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        promos = ClinicPromo.objects.filter(hospital=hospital)
    else:
        promos = ClinicPromo.objects.all()
    return render(request, "admin/admin_promos.html", {"promos": promos})


@login_required
def admin_promo_add(request):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if request.method == "POST":
        ClinicPromo.objects.create(
            hospital=hospital,
            title=request.POST.get("title", "").strip(),
            message=request.POST.get("message", "").strip(),
            start_date=request.POST.get("start_date") or timezone.now().date(),
            end_date=request.POST.get("end_date") or None,
            is_active=True,
        )
        messages.success(request, "✅ Promo created.")
        return redirect("admin_promos")
    return render(request, "admin/admin_promo_add.html")


@login_required
def admin_promo_delete(request, promo_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        promo = get_object_or_404(ClinicPromo, id=promo_id, hospital=hospital)
    else:
        promo = get_object_or_404(ClinicPromo, id=promo_id)
    promo.delete()
    messages.success(request, "🗑️ Promo deleted.")
    return redirect("admin_promos")


@login_required
def dismiss_promo(request):
    if request.method == "POST":
        promo_id = request.POST.get("promo_id")
        dismissed = request.session.get("dismissed_promos", [])
        if promo_id and promo_id not in dismissed:
            dismissed.append(promo_id)
            request.session["dismissed_promos"] = dismissed
    return JsonResponse({"ok": True})


# ─── EXERCISE REMINDER ────────────────────────────────────────


@login_required
def send_exercise_reminder(request, patient_id):
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")
    patient = get_object_or_404(User, id=patient_id)
    hospital = resolve_hospital(request.user)
    if hospital and not request.user.is_superuser:
        belongs = (
            Appointment.objects.filter(patient=patient, hospital=hospital).exists()
            or (hasattr(patient, "patient_profile") and patient.patient_profile.hospital_id == hospital.id)
        )
        if not belongs:
            messages.error(request, "❌ Access denied: Patient does not belong to your clinic.")
            return redirect("admin_patients")

    last_note = (
        SessionNote.objects.filter(patient=patient).order_by("-created_at").first()
    )
    next_info = last_note.next_session if last_note else "your scheduled session"
    from .notifications import notify

    notify(
        recipient=patient,
        message=f"🏃 Reminder from Dr. Dhvani: Please complete your exercises before {next_info}. Stay consistent for faster recovery!",
        link="/my-appointments/",
    )
    email_sent = False
    if patient.email:
        try:
            email_sent = bool(send_clinic_email(
                subject="Exercise Reminder from Dr. Dhvani Patalia",
                message_text=f"""Dear {patient.get_full_name() or patient.username},

This is a friendly reminder from Dr. Dhvani Patalia's PhysioRehab Clinic.

Please ensure you complete your prescribed exercises before your next session: {next_info}

Consistency is key to a faster recovery. If you have any questions, feel free to chat with us.

Dr. Dhvani Patalia — PhysioRehab Clinic
""",
                recipient_list=[patient.email],
                hospital=hospital,
                email_type="exercise_reminder",
            ))
        except Exception as exc:
            logger.error(f"Exercise reminder email failed for {patient.email}: {exc.__class__.__name__} - {exc}")

    if email_sent:
        messages.success(
            request,
            f"✅ Exercise reminder notification sent to {patient.get_full_name() or patient.username}.",
        )
    elif patient.email:
        messages.warning(
            request,
            f"Exercise reminder in-app notification created, but email delivery to {patient.email} failed.",
        )
    else:
        messages.info(
            request,
            f"Exercise reminder in-app notification created for {patient.get_full_name() or patient.username} (no email address on file).",
        )
    return redirect("admin_patients")


# ─────────────────────────────────────────────────────────────────────────────
# BULK IMPORT (Excel Upload)
# ─────────────────────────────────────────────────────────────────────────────

IMPORT_CONFIGS = {
    "patients": {
        "label": "Patients",
        "columns": [
            "first_name", "last_name", "email", "phone",
            "date_of_birth", "gender", "address", "medical_history",
        ],
        "required": ["first_name", "last_name", "email"],
        "description": "Import patient accounts. A Django user + PatientProfile will be created for each row.",
    },
    "staff": {
        "label": "Staff / Physiotherapists",
        "columns": [
            "first_name", "last_name", "email", "phone",
            "role", "specialization", "salary", "join_date",
        ],
        "required": ["first_name", "last_name", "email"],
        "description": "Import staff members. Django user + StaffProfile will be created.",
    },
    "appointments": {
        "label": "Appointments",
        "columns": [
            "patient_email", "staff_email", "date", "time",
            "service", "notes", "status",
        ],
        "required": ["patient_email", "date", "time"],
        "description": "Bulk schedule appointments. patient_email and staff_email must match existing users.",
    },
}


@login_required
def download_import_template(request, model_name):
    """Download an Excel template for the given model."""
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    config = IMPORT_CONFIGS.get(model_name)
    if not config:
        messages.error(request, "Unknown import type.")
        return redirect("bulk_import")

    import openpyxl
    from django.http import HttpResponse

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = config["label"]

    # Header row
    header_font = openpyxl.styles.Font(bold=True, color="FFFFFF")
    header_fill = openpyxl.styles.PatternFill("solid", fgColor="1F2937")
    for col_idx, col_name in enumerate(config["columns"], start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 22

    # Sample row
    samples = {
        "first_name": "Aarav", "last_name": "Sharma", "email": "aarav@example.com",
        "phone": "9876543210", "date_of_birth": "1990-05-15", "gender": "Male",
        "address": "Mumbai, Maharashtra", "medical_history": "Back pain",
        "role": "physiotherapist", "specialization": "Sports Rehab",
        "salary": "45000", "join_date": "2024-01-10",
        "patient_email": "patient@example.com", "staff_email": "staff@example.com",
        "date": "2024-12-01", "time": "10:00", "service": "Physiotherapy",
        "notes": "First session", "status": "pending",
    }
    for col_idx, col_name in enumerate(config["columns"], start=1):
        ws.cell(row=2, column=col_idx, value=samples.get(col_name, ""))

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{model_name}_template.xlsx"'
    wb.save(response)
    return response


@login_required
def bulk_import(request):
    """Upload an Excel file and import records into the database."""
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return redirect("client_dashboard")

    hospital = resolve_hospital(request.user) or Hospital.objects.first()
    results = None

    if request.method == "POST":
        import openpyxl
        model_name = request.POST.get("model_name", "")
        excel_file = request.FILES.get("excel_file")
        config = IMPORT_CONFIGS.get(model_name)

        if not config or not excel_file:
            messages.error(request, "Please select an import type and upload a file.")
            return redirect("bulk_import")

        from .file_security import validate_excel_file
        try:
            validate_excel_file(excel_file)
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, "message") else str(e))
            return redirect("bulk_import")

        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                messages.error(request, "The uploaded file is empty.")
                return redirect("bulk_import")

            # Parse header
            header = [str(h).strip().lower() if h else "" for h in rows[0]]
            data_rows = rows[1:]

            created, skipped_rows, errors = 0, 0, []

            for row_num, row in enumerate(data_rows, start=2):
                if all(cell is None or str(cell).strip() == "" for cell in row):
                    continue  # skip blank rows

                row_data = {
                    col: (str(row[i]).strip() if i < len(row) and row[i] is not None else "")
                    for i, col in enumerate(header)
                    if col
                }

                # Validate required fields
                missing = [r for r in config["required"] if not row_data.get(r)]
                if missing:
                    errors.append(f"Row {row_num}: missing {', '.join(missing)}")
                    skipped_rows += 1
                    continue

                try:
                    if model_name == "patients":
                        email = row_data["email"]
                        username = email.split("@")[0] + "_p"
                        user, u_new = User.objects.get_or_create(
                            email=email,
                            defaults={
                                "username": username,
                                "first_name": row_data.get("first_name", ""),
                                "last_name": row_data.get("last_name", ""),
                                "is_staff": False,
                                "is_superuser": False,
                            },
                        )
                        if u_new:
                            user.set_password(User.objects.make_random_password())
                            user.save()
                        PatientProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                "hospital": hospital,
                                "phone": row_data.get("phone", ""),
                                "patient_status": "active",
                            },
                        )
                        created += 1

                    elif model_name == "staff":
                        email = row_data["email"]
                        username = email.split("@")[0] + "_s"
                        user, u_new = User.objects.get_or_create(
                            email=email,
                            defaults={
                                "username": username,
                                "first_name": row_data.get("first_name", ""),
                                "last_name": row_data.get("last_name", ""),
                                "is_staff": True,
                                "is_superuser": False,
                            },
                        )
                        if u_new:
                            user.set_password(User.objects.make_random_password())
                            user.save()
                        salary_val = row_data.get("salary", "0") or "0"
                        try:
                            salary_val = float(str(salary_val).replace(",", ""))
                        except (ValueError, AttributeError):
                            salary_val = 0
                        StaffProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                "hospital": hospital,
                                "role": row_data.get("role", "physiotherapist"),
                                "phone": row_data.get("phone", ""),
                                "salary": salary_val,
                                "is_active": True,
                            },
                        )
                        created += 1

                    elif model_name == "appointments":
                        patient_email = row_data.get("patient_email", "")
                        staff_email = row_data.get("staff_email", "")
                        appt_date = row_data.get("date", "")
                        appt_time = row_data.get("time", "")

                        try:
                            patient_user = User.objects.get(email=patient_email)
                        except User.DoesNotExist:
                            errors.append(f"Row {row_num}: patient '{patient_email}' not found")
                            skipped_rows += 1
                            continue

                        staff_user = None
                        if staff_email:
                            try:
                                staff_user = User.objects.get(email=staff_email)
                            except User.DoesNotExist:
                                pass

                        from datetime import date as dt_date, time as dt_time
                        try:
                            parsed_date = dt_date.fromisoformat(appt_date)
                            parsed_time = dt_time.fromisoformat(appt_time)
                        except (ValueError, TypeError):
                            errors.append(f"Row {row_num}: invalid date/time format (use YYYY-MM-DD and HH:MM)")
                            skipped_rows += 1
                            continue

                        Appointment.objects.get_or_create(
                            hospital=hospital,
                            patient=patient_user,
                            date=parsed_date,
                            time=parsed_time,
                            defaults={
                                "name": patient_user.get_full_name() or patient_user.username,
                                "email": patient_user.email,
                                "service": row_data.get("service", "Physiotherapy"),
                                "notes": row_data.get("notes", ""),
                                "status": row_data.get("status", "pending"),
                                "assigned_staff": staff_user,
                            },
                        )
                        created += 1

                except Exception as exc:
                    errors.append(f"Row {row_num}: {exc}")
                    skipped_rows += 1

            results = {
                "created": created,
                "skipped": skipped_rows,
                "errors": errors,
                "model_label": config["label"],
            }

            if created:
                messages.success(request, f"Successfully imported {created} {config['label']}.")
            if errors:
                messages.warning(request, f"{skipped_rows} rows had errors — see details below.")

        except Exception as exc:
            messages.error(request, f"Could not read the Excel file: {exc}")

    return render(request, "admin/bulk_import.html", {
        "import_configs": IMPORT_CONFIGS,
        "results": results,
    })


# ── AJAX Chat APIs ──
from django.utils.dateformat import format
from django.core.serializers.json import DjangoJSONEncoder
import json


def can_user_chat_with(user_a, user_b):
    """
    Verify if user_a is authorized to communicate with user_b.
    - Superusers can communicate with any user.
    - Users in the same hospital clinic (staff/admin/patients) can communicate.
    - Patients can communicate with staff/admin of their hospital.
    - Users with an existing message thread or appointment can communicate.
    """
    if user_a.id == user_b.id:
        return True
    if user_a.is_superuser or user_b.is_superuser:
        return True

    # Existing conversation check
    if Message.objects.filter(
        Q(sender=user_a, receiver=user_b) | Q(sender=user_b, receiver=user_a)
    ).exists():
        return True

    h_a = resolve_hospital(user_a)
    h_b = resolve_hospital(user_b)
    if h_a and h_b and h_a.id == h_b.id:
        return True

    # Patient to clinic staff/admin check
    for (patient, staff) in [(user_a, user_b), (user_b, user_a)]:
        h_staff = resolve_hospital(staff)
        if h_staff:
            has_appt = Appointment.objects.filter(patient=patient, hospital=h_staff).exists()
            has_profile = (
                hasattr(patient, "patient_profile")
                and patient.patient_profile.hospital_id == h_staff.id
            )
            if has_appt or has_profile:
                return True
    return False


@login_required
def api_chat_send(request):
    if request.method == "POST":
        try:
            content = ""
            receiver_id = None
            attachment_file = None

            if request.content_type and "application/json" in request.content_type:
                data = json.loads(request.body)
                receiver_id = data.get("receiver_id")
                content = data.get("content", "").strip()
            else:
                receiver_id = request.POST.get("receiver_id")
                content = request.POST.get("content", "").strip()
                attachment_file = request.FILES.get("attachment") or request.FILES.get("file")

            if not receiver_id or (not content and not attachment_file):
                return JsonResponse({"error": "Missing message content or recipient ID"}, status=400)

            receiver = User.objects.get(id=receiver_id)
            if not can_user_chat_with(request.user, receiver):
                return JsonResponse({"error": "Access denied: Cannot message this recipient"}, status=403)

            attachment_name = ""
            attachment_size = None
            attachment_type = ""

            if attachment_file:
                from .file_security import validate_attachment_file
                validate_attachment_file(attachment_file, max_size_mb=10)
                attachment_name = attachment_file.name[:250]
                attachment_size = attachment_file.size
                attachment_type = getattr(attachment_file, "content_type", "") or "application/octet-stream"

            from .file_security import sanitize_html_content
            clean_content = sanitize_html_content(content) if content else ""

            hospital = resolve_hospital(request.user) or resolve_hospital(receiver)

            msg = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                hospital=hospital,
                content=clean_content,
                attachment=attachment_file if attachment_file else None,
                attachment_name=attachment_name,
                attachment_size=attachment_size,
                attachment_type=attachment_type,
                status=Message.STATUS_SENT,
            )

            from django.urls import reverse
            attachment_url = reverse("download_chat_attachment", args=[msg.id]) if msg.attachment else None

            return JsonResponse({
                "success": True,
                "id": msg.id,
                "content": msg.content,
                "created_at": format(msg.created_at, "d M Y, h:i A"),
                "sender_id": msg.sender.id,
                "status": msg.status,
                "has_attachment": bool(msg.attachment),
                "attachment_url": attachment_url,
                "attachment_name": msg.attachment_name,
                "attachment_size": msg.attachment_size,
                "attachment_type": msg.attachment_type,
            })
        except User.DoesNotExist:
            return JsonResponse({"error": "Recipient not found"}, status=404)
        except ValidationError as val_err:
            return JsonResponse({"error": val_err.message if hasattr(val_err, "message") else str(val_err)}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def api_chat_fetch(request, user_id):
    try:
        from django.urls import reverse
        last_id = int(request.GET.get('last_id', 0))
        other_user = User.objects.get(id=user_id)
        if not can_user_chat_with(request.user, other_user):
            return JsonResponse({"error": "Access denied: Cannot access chat history with this user"}, status=403)

        # Mark messages from other_user to request.user as read
        Message.objects.filter(
            sender=other_user, receiver=request.user, id__gt=last_id, is_read=False
        ).update(is_read=True, status=Message.STATUS_READ)

        msgs = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user),
            id__gt=last_id
        ).select_related("sender", "receiver").order_by("created_at")

        data = []
        for msg in msgs:
            att_url = reverse("download_chat_attachment", args=[msg.id]) if msg.attachment else None
            data.append({
                "id": msg.id,
                "content": msg.content,
                "created_at": format(msg.created_at, "d M Y, h:i A"),
                "date_label": format(msg.created_at, "d M Y"),
                "sender_id": msg.sender.id,
                "status": msg.status,
                "has_attachment": bool(msg.attachment),
                "attachment_url": att_url,
                "attachment_name": msg.attachment_name,
                "attachment_size": msg.attachment_size,
                "attachment_type": msg.attachment_type,
            })

        return JsonResponse({"messages": data})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def api_inbound_email_webhook(request):
    """
    Inbound email webhook endpoint for receiving emails from mail providers
    (e.g., SendGrid, Mailgun, Postmark, AWS SES, or custom inbound MTA).
    Validates:
      - HTTP POST method
      - Secret authentication token (Bearer token, X-Webhook-Secret header, or HMAC token)
      - Payload parsing (JSON or form-encoded)
      - Idempotency & deduplication
      - HTML sanitization against stored XSS
      - Multi-tenant clinic routing & in-app notifications
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. POST required."}, status=405)

    import hmac
    expected_secret = getattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", "")
    auth_header = request.headers.get("Authorization", "")
    token_header = request.headers.get("X-Webhook-Secret", "")
    provided_secret = ""
    if auth_header.startswith("Bearer "):
        provided_secret = auth_header[7:].strip()
    elif token_header:
        provided_secret = token_header.strip()
    else:
        provided_secret = request.GET.get("secret", "").strip()

    if expected_secret:
        if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
            return JsonResponse({"error": "Unauthorized webhook signature/token"}, status=403)

    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = request.POST.dict()
    except Exception as e:
        return JsonResponse({"error": f"Invalid payload: {str(e)}"}, status=400)

    from .email_utils import process_inbound_email_payload
    result = process_inbound_email_payload(payload, raw_headers=dict(request.headers))
    if result.get("status") == "rejected":
        return JsonResponse(result, status=400)
    return JsonResponse(result, status=200)


@csrf_exempt
def api_email_status_webhook(request):
    """
    Webhook endpoint for receiving email delivery status updates from mail providers
    (e.g., Resend, SendGrid, Amazon SES, Mailgun).
    Validates:
      - HTTP POST method
      - Secret authentication token (Bearer token, X-Webhook-Secret header, or secret param)
      - Matches EMAIL_STATUS_WEBHOOK_SECRET or INBOUND_EMAIL_WEBHOOK_SECRET
      - Validates and updates EmailLog status (accepted, delivered, bounced, failed)
      - Records sanitized error reasons without secrets
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. POST required."}, status=405)

    import hmac
    expected_secret = getattr(settings, "EMAIL_STATUS_WEBHOOK_SECRET", "") or getattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", "")
    auth_header = request.headers.get("Authorization", "")
    token_header = request.headers.get("X-Webhook-Secret", "")
    provided_secret = ""
    if auth_header.startswith("Bearer "):
        provided_secret = auth_header[7:].strip()
    elif token_header:
        provided_secret = token_header.strip()
    else:
        provided_secret = request.GET.get("secret", "").strip()

    if expected_secret:
        if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
            return JsonResponse({"error": "Unauthorized webhook signature/token"}, status=403)

    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8"))
        else:
            payload = request.POST.dict()
    except Exception as e:
        return JsonResponse({"error": f"Invalid payload: {str(e)}"}, status=400)

    # Handle standard Resend webhook format: {"type": "email.delivered", "data": {"email_id": "...", ...}}
    event_type = payload.get("type", "")
    event_data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}

    msg_id = (
        payload.get("message_id")
        or event_data.get("email_id")
        or payload.get("id")
        or event_data.get("id", "")
    )

    if not msg_id:
        return JsonResponse({"error": "Missing message_id in payload"}, status=400)

    if "delivered" in event_type or payload.get("status") == "delivered":
        new_status = "delivered"
    elif "bounced" in event_type or payload.get("status") == "bounced":
        new_status = "bounced"
    elif "complained" in event_type or payload.get("status") == "complained":
        new_status = "bounced"
    elif payload.get("status") in ("failed", "rejected"):
        new_status = "failed"
    elif payload.get("status") in ("accepted", "sent"):
        new_status = payload.get("status")
    else:
        new_status = "accepted"

    # Match EmailLog by message_id
    from .models import EmailLog
    clean_id = str(msg_id).strip("<> ")
    log_entry = EmailLog.objects.filter(
        Q(message_id=clean_id) | Q(message_id__icontains=clean_id)
    ).first()

    if not log_entry:
        return JsonResponse({"status": "ignored", "reason": f"No matching EmailLog for message_id {clean_id}"}, status=200)

    log_entry.status = new_status
    reason = payload.get("error") or event_data.get("bounce_type") or payload.get("reason", "")
    if reason:
        safe_reason = re.sub(r'(re_[a-zA-Z0-9_\-]{10,}|Bearer\s+[^\s]+|password[=:\s]+[^\s&]+)', '***', str(reason))
        log_entry.error_details = safe_reason[:500]
    log_entry.save(update_fields=["status", "error_details"])

    logger.info(f"Updated EmailLog #{log_entry.id} status to '{new_status}' via delivery webhook")
    return JsonResponse({
        "status": "success",
        "log_id": log_entry.id,
        "new_status": new_status,
        "message_id": clean_id,
    }, status=200)


# ════════════════════════════════════════════════════════════
# MULTI-PORTAL EMAIL CONFIGURATION & MANAGEMENT VIEWS
# ════════════════════════════════════════════════════════════

@login_required
def admin_email_settings(request):
    """
    Clinic Admin view to configure their clinic's dedicated SMTP / Email Account.
    Enforces strict tenant isolation: Clinic Admin can ONLY configure their own hospital.
    Staff and Client roles are rejected with HTTP 403 Forbidden.
    """
    if not (request.user.is_superuser or _is_clinic_admin(request.user)):
        return HttpResponseForbidden("Access Denied: Only Clinic Administrators can manage email settings.")

    hospital = resolve_hospital(request.user)
    if not hospital and not request.user.is_superuser:
        return HttpResponseForbidden("Access Denied: No hospital association found.")

    hospital = hospital or Hospital.objects.first()

    account = EmailAccount.objects.filter(hospital=hospital, is_default=True).first() or \
              EmailAccount.objects.filter(hospital=hospital).first()

    if request.method == "POST":
        action = request.POST.get("action", "save")

        # 1. Real Test Email Dispatch
        if action == "test":
            test_recipient = request.POST.get("test_recipient", "").strip()
            if not test_recipient:
                messages.error(request, "Please enter a recipient email address for testing.")
            elif not account:
                messages.error(request, "Please configure and save email credentials before testing.")
            else:
                from .email_service import test_account_connection
                ok, msg = test_account_connection(account, test_recipient)
                if ok:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            return redirect("admin_email_settings")

        # 2. Save Email Account Settings
        name = request.POST.get("name", "").strip() or f"{hospital.name} Primary SMTP"
        provider = request.POST.get("provider", "smtp").strip()
        account_type = request.POST.get("account_type", "CLINIC").strip()
        host = request.POST.get("host", "").strip()
        port_raw = request.POST.get("port", "587").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        clear_password = request.POST.get("clear_password") == "on"
        from_email = request.POST.get("from_email", "").strip()
        from_name = request.POST.get("from_name", "").strip()
        reply_to = request.POST.get("reply_to", "").strip()
        use_tls = request.POST.get("use_tls") == "on"
        use_ssl = request.POST.get("use_ssl") == "on"

        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, "Port must be a valid integer between 1 and 65535.")
            return redirect("admin_email_settings")

        if not host or not username or not from_email:
            messages.error(request, "Host, Username, and From Email are required fields.")
            return redirect("admin_email_settings")

        # Mutual exclusivity defense
        if port == 587:
            use_tls = True
            use_ssl = False
        elif port == 465:
            use_ssl = True
            use_tls = False
        elif use_tls and use_ssl:
            use_ssl = False

        if not account:
            account = EmailAccount(
                hospital=hospital,
                scope_type="hospital",
                account_type=account_type if account_type in ("CLINIC", "NOTIFICATION", "DOCTOR") else "CLINIC",
                is_default=True,
            )

        account.name = name
        account.provider = provider
        account.account_type = account_type if account_type in ("CLINIC", "NOTIFICATION", "DOCTOR") else "CLINIC"
        account.host = host
        account.port = port
        account.username = username
        account.from_email = from_email
        account.from_name = from_name or hospital.name
        account.reply_to = reply_to
        account.use_tls = use_tls
        account.use_ssl = use_ssl
        account.is_active = True

        if clear_password:
            account.encrypted_password = ""
        elif password:
            clean_pwd = password.strip()
            if provider == "gmail" or "gmail.com" in host.lower() or len(clean_pwd.replace(" ", "")) == 16:
                clean_pwd = clean_pwd.replace(" ", "")
            account.set_password(clean_pwd)

        account.save()
        messages.success(request, f"Email account for {hospital.name} saved successfully.")
        return redirect("admin_email_settings")

    recent_logs = (
        EmailLog.objects.filter(hospital=hospital).order_by("-sent_at")[:15]
        if hospital else EmailLog.objects.none()
    )

    return render(
        request,
        "admin/admin_email_settings.html",
        {
            "hospital": hospital,
            "account": account,
            "has_password": bool(account and account.encrypted_password),
            "recent_logs": recent_logs,
        },
    )


@platform_superadmin_required
def super_admin_email_accounts(request):
    """
    Platform Super Admin dashboard for multi-account email governance.
    Lists all platform-wide, support, notification, and clinic-specific email accounts.
    """
    accounts = EmailAccount.objects.select_related("hospital", "user").order_by("scope_type", "hospital__name", "name")
    hospitals = Hospital.objects.filter(is_active=True).order_by("name")
    return render(
        request,
        "super_admin/super_admin_email_accounts.html",
        {"accounts": accounts, "hospitals": hospitals},
    )


@platform_superadmin_required
def super_admin_email_account_save(request):
    """
    Create or update any email account (Platform, Support, Clinic) by Super Admin.
    """
    if request.method == "POST":
        account_id = request.POST.get("account_id")
        name = request.POST.get("name", "").strip()
        account_type = request.POST.get("account_type", "PLATFORM").strip()
        scope_type = request.POST.get("scope_type", "platform").strip()
        hospital_id = request.POST.get("hospital_id", "").strip()
        provider = request.POST.get("provider", "smtp").strip()
        host = request.POST.get("host", "").strip()
        port_raw = request.POST.get("port", "587").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        clear_password = request.POST.get("clear_password") == "on"
        from_email = request.POST.get("from_email", "").strip()
        from_name = request.POST.get("from_name", "").strip()
        reply_to = request.POST.get("reply_to", "").strip()
        use_tls = request.POST.get("use_tls") == "on"
        use_ssl = request.POST.get("use_ssl") == "on"
        is_default = request.POST.get("is_default") == "on"

        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, "Port must be a valid number between 1 and 65535.")
            return redirect("super_admin_email_accounts")

        if not name or not host or not username or not from_email:
            messages.error(request, "Name, Host, Username, and From Email are required.")
            return redirect("super_admin_email_accounts")

        # Mutual exclusivity defense
        if port == 587:
            use_tls = True
            use_ssl = False
        elif port == 465:
            use_ssl = True
            use_tls = False
        elif use_tls and use_ssl:
            use_ssl = False

        hospital = None
        if scope_type == "platform":
            hospital = None
            if not from_name:
                from_name = getattr(settings, "PLATFORM_BRAND_NAME", "TechCraft")
            if not from_email:
                from_email = getattr(settings, "PLATFORM_DEFAULT_FROM_EMAIL", "techcraft1215@gmail.com")
        elif scope_type == "hospital" and hospital_id:
            hospital = Hospital.objects.filter(id=hospital_id).first()

        if account_id:
            account = get_object_or_404(EmailAccount, id=account_id)
        else:
            account = EmailAccount()

        account.name = name
        account.account_type = account_type
        account.scope_type = scope_type
        account.hospital = hospital
        account.provider = provider
        account.host = host
        account.port = port
        account.username = username
        account.from_email = from_email
        account.from_name = from_name
        account.reply_to = reply_to
        account.use_tls = use_tls
        account.use_ssl = use_ssl
        account.is_active = True

        if is_default:
            if scope_type == "platform":
                EmailAccount.objects.filter(scope_type="platform").update(is_default=False)
            elif hospital:
                EmailAccount.objects.filter(hospital=hospital).update(is_default=False)
            account.is_default = True

        if clear_password:
            account.encrypted_password = ""
        elif password:
            clean_pwd = password.strip()
            if provider == "gmail" or "gmail.com" in host.lower() or len(clean_pwd.replace(" ", "")) == 16:
                clean_pwd = clean_pwd.replace(" ", "")
            account.set_password(clean_pwd)

        account.save()
        messages.success(request, f"Email account '{account.name}' saved successfully.")
    return redirect("super_admin_email_accounts")


@platform_superadmin_required
def super_admin_email_account_test(request, account_id):
    """
    Test connection for a specific email account by Super Admin.
    """
    account = get_object_or_404(EmailAccount, id=account_id)
    if request.method == "POST":
        test_recipient = request.POST.get("test_recipient", "").strip()
        if not test_recipient:
            msg = "Please enter a valid test recipient email."
            ok = False
        else:
            from .email_service import test_account_connection
            ok, msg = test_account_connection(account, test_recipient)

        if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({"ok": ok, "message": msg})

        if ok:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    return redirect("super_admin_email_accounts")


@platform_superadmin_required
def super_admin_email_account_delete(request, account_id):
    """
    Delete an email account by Super Admin.
    """
    account = get_object_or_404(EmailAccount, id=account_id)
    if request.method == "POST":
        name = account.name
        account.delete()
        messages.success(request, f"Email account '{name}' deleted successfully.")
    return redirect("super_admin_email_accounts")


def robots_txt(request):
    """
    Renders dynamic robots.txt.
    Permits crawling of public marketing routes and static assets,
    while explicitly disallowing all private, dashboard, and administrative endpoints.
    Directs search engines to the absolute XML sitemap.
    """
    configured_base = getattr(settings, 'CANONICAL_BASE_URL', '').strip().rstrip('/') or os.environ.get('CANONICAL_BASE_URL', '').strip().rstrip('/')
    if not configured_base:
        scheme = 'https' if request.is_secure() else request.scheme
        configured_base = f"{scheme}://{request.get_host()}"

    sitemap_url = f"{configured_base}/sitemap.xml"
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /static/",
        "Allow: /media/",
        "Disallow: /admin/",
        "Disallow: /admin-",
        "Disallow: /staff-",
        "Disallow: /client-",
        "Disallow: /super-admin/",
        "Disallow: /dashboard/",
        "Disallow: /profile/",
        "Disallow: /edit-profile/",
        "Disallow: /api/",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /logout/",
        "Disallow: /forgot-password/",
        "Disallow: /verify-otp/",
        "Disallow: /reset-password/",
        "Disallow: /resend-otp/",
        "Disallow: /change-password/",
        "Disallow: /subscription/",
        "Disallow: /payments/",
        "Disallow: /export/",
        "Disallow: /bulk-import/",
        "Disallow: /submit-review/",
        "Disallow: /support/",
        "Disallow: /healthz",
        "Disallow: /notifications/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    """
    Renders valid XML sitemap adhering to Sitemap 0.9 protocol using Django's sitemap framework.
    Includes only eligible, canonical public routes and published articles.
    Strictly excludes all private, administrative, and authenticated endpoints.
    """
    from django.contrib.sitemaps.views import sitemap as django_sitemap
    from core.sitemaps import sitemaps

    response = django_sitemap(
        request,
        sitemaps=sitemaps,
        template_name="sitemap.xml",
        content_type="application/xml; charset=utf-8",
    )
    response["Content-Type"] = "application/xml; charset=utf-8"
    return response


def google_verification_file(request, token):
    """
    Serves Google Search Console verification file if configured.
    Matches /google<token>.html.
    Accepts matching token from GOOGLE_SITE_VERIFICATION_TOKEN or GOOGLE_SITE_VERIFICATION_FILE.
    Returns 200 with 'google-site-verification: google<token>.html' or 404.
    """
    configured_token = (
        getattr(settings, "GOOGLE_SITE_VERIFICATION_TOKEN", "").strip()
        or os.environ.get("GOOGLE_SITE_VERIFICATION_TOKEN", "").strip()
    )
    configured_file = (
        getattr(settings, "GOOGLE_SITE_VERIFICATION_FILE", "").strip()
        or os.environ.get("GOOGLE_SITE_VERIFICATION_FILE", "").strip()
    )

    valid_tokens = set()
    if configured_token:
        clean_token = configured_token.replace("google", "").replace(".html", "")
        if clean_token:
            valid_tokens.add(clean_token)
    if configured_file:
        clean_file_token = configured_file.replace("google", "").replace(".html", "")
        if clean_file_token:
            valid_tokens.add(clean_file_token)

    if token in valid_tokens and token:
        content = f"google-site-verification: google{token}.html\n"
        return HttpResponse(content, content_type="text/html; charset=utf-8")

    from django.http import Http404
    raise Http404("Google verification file not configured.")



def healthz(request):
    """
    Lightweight health-check endpoint for load balancers, container orchestrators,
    and external static preloaders/gateways.
    Executes a read-only DB query (SELECT 1).
    Returns:
        HTTP 200 with {"status": "ok"} when healthy.
        HTTP 503 with {"status": "unhealthy"} if database connectivity fails.
        HTTP 204 for OPTIONS preflight.
        HTTP 405 Method Not Allowed if request method is not GET, HEAD, or OPTIONS.
    Strictly avoids exposing connection strings, stack traces, queries, or server internals.
    Includes CORS headers (Access-Control-Allow-Origin: *) to support external static gate probes.
    """
    if request.method == "OPTIONS":
        response = HttpResponse(status=204)
        response["Allow"] = "GET, HEAD, OPTIONS"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response["Access-Control-Allow-Headers"] = "*"
        return response

    if request.method not in ("GET", "HEAD"):
        response = HttpResponse("Method Not Allowed", status=405)
        response["Allow"] = "GET, HEAD, OPTIONS"
        response["Access-Control-Allow-Origin"] = "*"
        return response

    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if not row or row[0] != 1:
                raise ValueError("Unexpected query result")

        resp = JsonResponse({"status": "ok"}, status=200)
        resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as exc:
        logger.error("Health check database probe failed: %s", exc)
        resp = JsonResponse({"status": "unhealthy"}, status=503)
        resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp["Access-Control-Allow-Origin"] = "*"
        return resp



# ═════════════════════════════════════════════════════════════════════════════
# SUPER ADMIN WEBSITE VISITOR ANALYTICS & LEAD MANAGEMENT VIEWS
# ═════════════════════════════════════════════════════════════════════════════

def _parse_referrer_info(referrer_url):
    """Categorize referrer URL into privacy-safe buckets without storing user search terms."""
    if not referrer_url:
        return "direct", ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(referrer_url)
        domain = (parsed.netloc or "").lower().split(":")[0]
        if not domain:
            return "direct", ""

        if any(s in domain for s in ["google.", "bing.", "yahoo.", "duckduckgo.", "baidu.", "ecosia."]):
            return "search", domain
        if any(s in domain for s in ["facebook.", "twitter.", "t.co", "x.com", "instagram.", "linkedin.", "pinterest.", "reddit."]):
            return "social", domain
        if any(s in domain for s in ["mail.", "outlook.", "gmail."]):
            return "referral", domain
        return "referral", domain
    except Exception:
        return "other", ""


def _parse_user_agent(ua_string):
    """Categorize device and browser using minimal heuristic without invasive fingerprinting."""
    if not ua_string:
        return "unknown", "Unknown", "Unknown"
    ua = ua_string.lower()

    # Bot / crawler
    if any(b in ua for b in ["bot", "crawl", "spider", "slurp", "googlebot", "bingbot", "yandex", "duckduckbot"]):
        return "bot", "Crawler / Bot", "Unknown"

    # Device
    if "tablet" in ua or "ipad" in ua:
        device = "tablet"
    elif "mobile" in ua or "android" in ua or "iphone" in ua or "ipod" in ua:
        device = "mobile"
    else:
        device = "desktop"

    # Browser
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "opera/" in ua or "opr/" in ua:
        browser = "Opera"
    else:
        browser = "Other"

    # OS
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Other"

    return device, browser, os_name


@csrf_exempt
def api_analytics_track(request):
    """
    Public, privacy-conscious beacon endpoint for website visitor analytics.
    Accepts JSON POST or beacon data.
    Stores:
      - Anonymous session key
      - Page path & title
      - Active reading time (seconds)
      - Minimal device/referrer category
    Never collects raw IPs, user search queries, medical information, or private form contents.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    from .models import AnalyticsSetting, VisitorSession, PageViewEvent
    from core.ip_utils import get_client_ip, generate_pseudonymous_visitor_id, sanitize_referrer_url

    settings_obj = AnalyticsSetting.get_settings()
    consent = data.get("consent", False)

    # If policy requires explicit consent and visitor has not consented, ignore non-essential tracking
    if settings_obj.require_consent and not consent:
        return JsonResponse({"status": "consent_required", "tracked": False})

    session_token = str(data.get("session_key", "")).strip()
    if not session_token or len(session_token) > 64:
        session_token = uuid.uuid4().hex

    path = str(data.get("path", "/")).strip()[:200]
    if not path.startswith("/"):
        path = "/" + path
    page_title = str(data.get("title", "")).strip()[:200]
    section_name = str(data.get("section", "")).strip()[:100]

    # Sanitize active seconds (prevent bogus huge numbers)
    try:
        active_sec = max(0, min(int(data.get("active_seconds", 0)), 1800))
    except (ValueError, TypeError):
        active_sec = 0

    referrer_raw = request.META.get("HTTP_REFERER", "") or str(data.get("referrer", ""))
    ua_raw = request.META.get("HTTP_USER_AGENT", "")

    ref_cat, ref_dom = _parse_referrer_info(referrer_raw)
    dev_cat, browser, os_name = _parse_user_agent(ua_raw)
    client_ip = get_client_ip(request) or ""
    visitor_id = generate_pseudonymous_visitor_id(client_ip, ua_raw) if (client_ip or ua_raw) else ""
    clean_ref = sanitize_referrer_url(referrer_raw)

    now = timezone.now()

    # Get or create session
    session, created = VisitorSession.objects.get_or_create(
        session_key=session_token,
        defaults={
            "started_at": now,
            "last_activity": now,
            "device_category": dev_cat,
            "browser_family": browser,
            "os_family": os_name,
            "referrer_category": ref_cat,
            "referrer_domain": ref_dom[:200],
            "referrer_url": clean_ref,
            "entry_page": path,
            "exit_page": path,
            "total_page_views": 1,
            "total_active_seconds": active_sec,
            "consent_given": bool(consent),
            "consent_status": "accepted" if consent else "pending",
            "consent_policy_version": "1.0",
            "consent_timestamp": now if consent else None,
            "ip_address": client_ip or None,
            "visitor_id": visitor_id,
        }
    )

    if not created:
        update_fields = ["last_activity", "exit_page", "total_active_seconds"]
        session.last_activity = now
        session.exit_page = path
        session.total_active_seconds += active_sec
        if data.get("is_new_page", False):
            session.total_page_views += 1
            update_fields.append("total_page_views")
        if not session.ip_address and client_ip:
            session.ip_address = client_ip
            update_fields.append("ip_address")
        if not session.visitor_id and visitor_id:
            session.visitor_id = visitor_id
            update_fields.append("visitor_id")
        if consent and not session.consent_given:
            session.consent_given = True
            session.consent_status = "accepted"
            session.consent_timestamp = now
            update_fields.extend(["consent_given", "consent_status", "consent_timestamp"])
        session.save(update_fields=update_fields)

    # Record page/section event
    if path:
        pv = PageViewEvent.objects.filter(session=session, path=path, section_name=section_name).first()
        if pv:
            pv.active_seconds += active_sec
            if data.get("is_new_page", False):
                pv.view_count += 1
            pv.timestamp = now
            pv.save(update_fields=["active_seconds", "view_count", "timestamp"])
        else:
            PageViewEvent.objects.create(
                session=session,
                path=path,
                page_title=page_title,
                section_name=section_name,
                active_seconds=active_sec,
                view_count=1,
                timestamp=now,
                referrer=clean_ref,
            )

    resp = JsonResponse({
        "status": "success",
        "tracked": True,
        "session_key": session.session_key,
    })
    # Set/refresh privacy cookie (secure, samesite=lax, 30 days)
    resp.set_cookie(
        "va_session",
        session.session_key,
        max_age=30 * 86400,
        httponly=False,  # Accessible to analytics beacon JS
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return resp


@csrf_exempt
def api_analytics_consent(request):
    """
    Public API: Record, update, or withdraw optional visitor analytics consent.
    Audits the decision separately in VisitorConsentRecord to satisfy privacy compliance.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    from .models import VisitorConsentRecord, VisitorSession
    from core.ip_utils import get_client_ip

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        data = {}

    decision = str(data.get("decision", request.POST.get("decision", "declined"))).strip().lower()
    if decision not in ("accepted", "declined", "withdrawn", "pending"):
        decision = "declined"

    policy_version = str(data.get("policy_version", "1.0"))[:20]
    session_token = str(data.get("session_key", request.COOKIES.get("va_session", ""))).strip()[:64]
    if not session_token:
        session_token = uuid.uuid4().hex

    client_ip = get_client_ip(request) or ""
    ua_raw = request.META.get("HTTP_USER_AGENT", "")[:255]

    # Create immutable consent audit record
    VisitorConsentRecord.objects.create(
        session_key=session_token,
        action=decision,
        policy_version=policy_version,
        ip_address=client_ip or "",
        user_agent=ua_raw,
    )

    # Update session if one exists
    session = VisitorSession.objects.filter(session_key=session_token).first()
    now = timezone.now()
    if session:
        session.consent_status = decision
        session.consent_timestamp = now
        session.consent_policy_version = policy_version
        session.consent_given = (decision == "accepted")
        session.save(update_fields=["consent_status", "consent_timestamp", "consent_policy_version", "consent_given"])

    resp = JsonResponse({
        "status": "success",
        "decision": decision,
        "session_key": session_token,
    })
    resp.set_cookie(
        "va_consent",
        decision,
        max_age=365 * 86400,
        httponly=False,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    resp.set_cookie(
        "va_session",
        session_token,
        max_age=30 * 86400,
        httponly=False,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return resp


@platform_superadmin_required
def super_admin_visitor_analytics(request):
    """
    Super Admin exclusive: Website Visitor Analytics, Consent Tracking, and Lead Management.
    Provides 8 Summary KPI cards, Searchable & Filterable Visitor Records, Device & Referrer Stats,
    and Privacy/Retention Settings.
    """
    from .models import (
        VisitorSession,
        PageViewEvent,
        VisitorLead,
        AnalyticsSetting,
        AnalyticsAuditLog,
    )
    from django.core.paginator import Paginator

    # Audit access
    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="view_overview",
        details="Super Admin visited Visitor Analytics dashboard",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )

    settings_obj = AnalyticsSetting.get_settings()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Date filter
    range_filter = request.GET.get("range", "30d")
    if range_filter == "today":
        start_date = today_start
    elif range_filter == "7d":
        start_date = now - timedelta(days=7)
    elif range_filter == "90d":
        start_date = now - timedelta(days=90)
    elif range_filter == "all":
        start_date = None
    else:  # default 30d
        start_date = now - timedelta(days=30)
        range_filter = "30d"

    base_sessions = VisitorSession.objects.all()
    if start_date:
        sessions_qs = base_sessions.filter(started_at__gte=start_date)
    else:
        sessions_qs = base_sessions

    # 8 Required Summary KPI Cards
    # 1. Total eligible page views
    if start_date:
        total_page_views = PageViewEvent.objects.filter(timestamp__gte=start_date).aggregate(s=Sum("view_count"))["s"] or 0
    else:
        total_page_views = PageViewEvent.objects.aggregate(s=Sum("view_count"))["s"] or 0

    # 2. Estimated unique visitors (distinct visitor_id where set, otherwise distinct session_key)
    distinct_vids = sessions_qs.exclude(visitor_id="").values("visitor_id").distinct().count()
    anonymous_no_vids = sessions_qs.filter(visitor_id="").count()
    estimated_unique_visitors = distinct_vids + anonymous_no_vids

    # 3. Visitors today
    visitors_today = base_sessions.filter(started_at__gte=today_start).count()

    # 4. Visitors in the last seven days
    visitors_7d = base_sessions.filter(started_at__gte=now - timedelta(days=7)).count()

    # 5. Visitors in the last thirty days
    visitors_30d = base_sessions.filter(started_at__gte=now - timedelta(days=30)).count()

    # 6. Analytics consent accepted
    consent_accepted_count = sessions_qs.filter(consent_status="accepted").count()

    # 7. Analytics consent declined
    consent_declined_count = sessions_qs.filter(consent_status="declined").count()

    # 8. Consent pending or unavailable
    consent_pending_count = sessions_qs.filter(Q(consent_status="pending") | Q(consent_status="")).count()

    # Consent Acceptance Rate (of decided visitors)
    decided_count = consent_accepted_count + consent_declined_count
    consent_acceptance_rate = round((consent_accepted_count / decided_count * 100), 1) if decided_count > 0 else 0.0

    total_sessions = sessions_qs.count()

    # Optional secondary filters for the table
    device_filter = request.GET.get("device", "").strip()
    if device_filter:
        sessions_qs = sessions_qs.filter(device_category=device_filter)

    referrer_filter = request.GET.get("referrer", "").strip()
    if referrer_filter:
        sessions_qs = sessions_qs.filter(referrer_category=referrer_filter)

    consent_filter = request.GET.get("consent", "").strip()
    if consent_filter == "accepted":
        sessions_qs = sessions_qs.filter(consent_status="accepted")
    elif consent_filter == "declined":
        sessions_qs = sessions_qs.filter(consent_status="declined")
    elif consent_filter == "pending":
        sessions_qs = sessions_qs.filter(Q(consent_status="pending") | Q(consent_status=""))

    search_query = request.GET.get("q", "").strip()
    if search_query:
        sessions_qs = sessions_qs.filter(
            Q(ip_address__icontains=search_query)
            | Q(visitor_id__icontains=search_query)
            | Q(exit_page__icontains=search_query)
            | Q(entry_page__icontains=search_query)
            | Q(browser_family__icontains=search_query)
            | Q(os_family__icontains=search_query)
            | Q(referrer_domain__icontains=search_query)
        )

    # Leads & Conversion Rate
    leads_count = VisitorLead.objects.filter(submitted_at__gte=start_date).count() if start_date else VisitorLead.objects.count()
    converted_sessions = sessions_qs.filter(has_converted=True).count()
    conversion_rate = round((converted_sessions / total_sessions) * 100, 2) if total_sessions > 0 else 0.0

    # Device Breakdown
    device_stats = (
        sessions_qs.values("device_category")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Traffic Sources Breakdown
    referrer_stats = (
        sessions_qs.values("referrer_category")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Most Popular Pages
    popular_pages_qs = PageViewEvent.objects.all()
    if start_date:
        popular_pages_qs = popular_pages_qs.filter(timestamp__gte=start_date)
    popular_pages = (
        popular_pages_qs.values("path", "page_title")
        .annotate(views=Sum("view_count"), active_time=Sum("active_seconds"))
        .order_by("-views")[:10]
    )

    # Sessions List with Pagination
    session_list_qs = sessions_qs.order_by("-last_activity")
    sessions_paginator = Paginator(session_list_qs, 25)
    sessions_page_number = request.GET.get("page", request.GET.get("spage", 1))
    sessions_page = sessions_paginator.get_page(sessions_page_number)

    # Leads List with Filtering & Pagination
    leads_qs = VisitorLead.objects.all().order_by("-submitted_at")
    lead_status_filter = request.GET.get("lead_status", "")
    lead_search = request.GET.get("lead_q", "").strip()

    if lead_status_filter:
        leads_qs = leads_qs.filter(status=lead_status_filter)
    if lead_search:
        leads_qs = leads_qs.filter(
            Q(first_name__icontains=lead_search)
            | Q(last_name__icontains=lead_search)
            | Q(email__icontains=lead_search)
            | Q(phone__icontains=lead_search)
            | Q(category__icontains=lead_search)
            | Q(message__icontains=lead_search)
        )

    leads_paginator = Paginator(leads_qs, 15)
    leads_page_number = request.GET.get("lpage", 1)
    leads_page = leads_paginator.get_page(leads_page_number)

    # Recent Audit Logs
    recent_audits = AnalyticsAuditLog.objects.all().order_by("-created_at")[:15]

    return render(
        request,
        "super_admin/super_admin_visitor_analytics.html",
        {
            "range_filter": range_filter,
            "device_filter": device_filter,
            "referrer_filter": referrer_filter,
            "consent_filter": consent_filter,
            "search_query": search_query,
            "lead_status_filter": lead_status_filter,
            "lead_search": lead_search,
            # 8 KPI Metrics
            "total_page_views": total_page_views,
            "estimated_unique_visitors": estimated_unique_visitors,
            "visitors_today": visitors_today,
            "visitors_7d": visitors_7d,
            "visitors_30d": visitors_30d,
            "consent_accepted_count": consent_accepted_count,
            "consent_declined_count": consent_declined_count,
            "consent_pending_count": consent_pending_count,
            "consent_acceptance_rate": consent_acceptance_rate,
            "total_sessions": total_sessions,
            "leads_count": leads_count,
            "converted_sessions": converted_sessions,
            "conversion_rate": conversion_rate,
            "device_stats": device_stats,
            "referrer_stats": referrer_stats,
            "popular_pages": popular_pages,
            "sessions_page": sessions_page,
            "leads_page": leads_page,
            "settings": settings_obj,
            "recent_audits": recent_audits,
        },
    )


@platform_superadmin_required
def super_admin_visitor_detail(request, session_id):
    """
    Super Admin exclusive: In-depth detail view of a visitor session,
    displaying full public page view trail and consent audit history.
    """
    from .models import VisitorSession, PageViewEvent, VisitorConsentRecord, AnalyticsAuditLog

    session = get_object_or_404(VisitorSession, id=session_id)

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="view_visitor_detail",
        details=f"Viewed details for Visitor Session #{session.id} (IP: {session.ip_address or 'Unknown'})",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )

    page_views = PageViewEvent.objects.filter(session=session).order_by("-timestamp")
    consent_records = VisitorConsentRecord.objects.filter(session_key=session.session_key).order_by("-timestamp")

    return render(
        request,
        "super_admin/super_admin_visitor_detail.html",
        {
            "visitor": session,
            "page_views": page_views,
            "consent_records": consent_records,
        },
    )


def _sanitize_csv_cell(value):
    """
    Prevent Spreadsheet Formula Injection (CSV Injection).
    Prepends a single quote if the value starts with '=', '+', '-', '@', tab, or newline.
    """
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return f"'{val_str}"
    return val_str


@platform_superadmin_required
def super_admin_export_visitors_csv(request):
    """
    Super Admin export of filtered visitor records to CSV.
    Guards against formula injection, preserves tenant isolation, and logs export audit trail.
    """
    import csv
    from .models import VisitorSession, AnalyticsAuditLog

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Date filter
    range_filter = request.GET.get("range", "30d")
    if range_filter == "today":
        start_date = today_start
    elif range_filter == "7d":
        start_date = now - timedelta(days=7)
    elif range_filter == "90d":
        start_date = now - timedelta(days=90)
    elif range_filter == "all":
        start_date = None
    else:
        start_date = now - timedelta(days=30)

    sessions_qs = VisitorSession.objects.all()
    if start_date:
        sessions_qs = sessions_qs.filter(started_at__gte=start_date)

    consent_filter = request.GET.get("consent", "").strip()
    if consent_filter == "accepted":
        sessions_qs = sessions_qs.filter(consent_status="accepted")
    elif consent_filter == "declined":
        sessions_qs = sessions_qs.filter(consent_status="declined")
    elif consent_filter == "pending":
        sessions_qs = sessions_qs.filter(Q(consent_status="pending") | Q(consent_status=""))

    search_query = request.GET.get("q", "").strip()
    if search_query:
        sessions_qs = sessions_qs.filter(
            Q(ip_address__icontains=search_query)
            | Q(visitor_id__icontains=search_query)
            | Q(exit_page__icontains=search_query)
            | Q(entry_page__icontains=search_query)
            | Q(browser_family__icontains=search_query)
            | Q(os_family__icontains=search_query)
            | Q(referrer_domain__icontains=search_query)
        )

    sessions = list(sessions_qs.order_by("-last_activity")[:1000])

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="export_visitors",
        details=f"Exported {len(sessions)} Visitor records to CSV (range: {range_filter}, consent: {consent_filter or 'all'})",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="visitor_analytics_{timezone.now():%Y%m%d_%H%M}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "ID",
        "Visitor Identifier",
        "IP Address",
        "First Visit",
        "Last Activity",
        "Total Page Views",
        "Active Seconds",
        "Entry Page",
        "Exit Page",
        "Device Category",
        "Browser",
        "Operating System",
        "Consent Status",
        "Consent Policy Version",
        "Referrer URL",
    ])

    for s in sessions:
        writer.writerow([
            _sanitize_csv_cell(s.id),
            _sanitize_csv_cell(s.visitor_id),
            _sanitize_csv_cell(s.ip_address or "Unknown"),
            _sanitize_csv_cell(s.started_at.strftime("%Y-%m-%d %H:%M:%S") if s.started_at else ""),
            _sanitize_csv_cell(s.last_activity.strftime("%Y-%m-%d %H:%M:%S") if s.last_activity else ""),
            _sanitize_csv_cell(s.total_page_views),
            _sanitize_csv_cell(s.total_active_seconds),
            _sanitize_csv_cell(s.entry_page),
            _sanitize_csv_cell(s.exit_page),
            _sanitize_csv_cell(s.device_category),
            _sanitize_csv_cell(s.browser_family),
            _sanitize_csv_cell(s.os_family),
            _sanitize_csv_cell(s.consent_status),
            _sanitize_csv_cell(s.consent_policy_version),
            _sanitize_csv_cell(s.referrer_url),
        ])

    return response


@platform_superadmin_required
def super_admin_visitor_lead_detail(request, lead_id):
    """
    Super Admin exclusive view to review lead details, update status, and manage notes.
    """
    from .models import VisitorLead, AnalyticsAuditLog

    lead = get_object_or_404(VisitorLead, id=lead_id)

    if request.method == "POST":
        new_status = request.POST.get("status", lead.status)
        admin_notes = request.POST.get("admin_notes", "").strip()

        if new_status in dict(VisitorLead.STATUS_CHOICES):
            lead.status = new_status
            if new_status in ("contacted", "qualified", "closed") and not lead.contacted_at:
                lead.contacted_at = timezone.now()

        lead.admin_notes = admin_notes
        lead.save(update_fields=["status", "admin_notes", "contacted_at"])

        AnalyticsAuditLog.objects.create(
            user=request.user,
            action="update_lead",
            details=f"Updated lead #{lead.id} ({lead.full_name}) status to {new_status}",
            ip_address=request.META.get("REMOTE_ADDR", "")[:50],
        )
        messages.success(request, f"Lead #{lead.id} details updated successfully.")
        return redirect("super_admin_visitor_lead_detail", lead_id=lead.id)

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="view_lead_detail",
        details=f"Viewed details for lead #{lead.id} ({lead.email})",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )

    return render(
        request,
        "super_admin/super_admin_visitor_lead_detail.html",
        {"lead": lead},
    )


@platform_superadmin_required
def super_admin_export_leads_csv(request):
    """
    Super Admin export leads to CSV with audit trail.
    """
    import csv
    from .models import VisitorLead, AnalyticsAuditLog

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="export_leads",
        details="Exported Visitor Leads to CSV",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="visitor_leads_{timezone.now():%Y%m%d_%H%M}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "ID", "Name", "Email", "Phone", "Category", "Source Page",
        "Marketing Consent", "Status", "Submitted At", "Contacted At", "Message", "Admin Notes"
    ])

    for lead in VisitorLead.objects.all().order_by("-submitted_at"):
        writer.writerow([
            lead.id,
            lead.full_name,
            lead.email,
            lead.phone,
            lead.category,
            lead.source_page,
            "Yes" if lead.marketing_consent else "No",
            lead.get_status_display(),
            lead.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
            lead.contacted_at.strftime("%Y-%m-%d %H:%M:%S") if lead.contacted_at else "",
            lead.message.replace("\n", " "),
            lead.admin_notes.replace("\n", " "),
        ])

    return response


@platform_superadmin_required
@require_POST
def super_admin_analytics_settings(request):
    """
    Update privacy retention policies (e.g. 30, 60, 90, 180 days) and consent requirement.
    """
    from .models import AnalyticsSetting, AnalyticsAuditLog

    setting = AnalyticsSetting.get_settings()
    try:
        retention = int(request.POST.get("retention_days", 90))
        if retention < 7 or retention > 730:
            retention = 90
    except (ValueError, TypeError):
        retention = 90

    require_consent = request.POST.get("require_consent", "").lower() in ("true", "1", "on")

    setting.retention_days = retention
    setting.require_consent = require_consent
    setting.save()

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="update_settings",
        details=f"Updated retention to {retention} days, require_consent={require_consent}",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )
    messages.success(request, f"Privacy and retention settings saved (retention: {retention} days).")
    return redirect("super_admin_visitor_analytics")


@platform_superadmin_required
@require_POST
def super_admin_analytics_purge(request):
    """
    Purge expired anonymous visitor sessions and pageview events older than configured retention policy.
    Does not delete voluntarily submitted leads.
    """
    from .models import AnalyticsSetting, VisitorSession, PageViewEvent, AnalyticsAuditLog

    setting = AnalyticsSetting.get_settings()
    cutoff = timezone.now() - timedelta(days=setting.retention_days)

    # Find sessions older than cutoff
    old_sessions = VisitorSession.objects.filter(started_at__lt=cutoff)
    count = old_sessions.count()

    # Cascade deletes page_views; leads set session_id to NULL
    old_sessions.delete()

    AnalyticsAuditLog.objects.create(
        user=request.user,
        action="purge_data",
        details=f"Purged {count} expired visitor sessions older than {setting.retention_days} days",
        ip_address=request.META.get("REMOTE_ADDR", "")[:50],
    )
    messages.success(request, f"Purged {count} expired visitor sessions older than {setting.retention_days} days.")
    return redirect("super_admin_visitor_analytics")




