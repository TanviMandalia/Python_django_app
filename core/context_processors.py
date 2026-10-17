import os
from django.conf import settings
from .models import Notification, Message


def unread_notifications(request):
    """Inject unread notification count + recent notifications into every template."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    unread_notifs = Notification.objects.filter(
        recipient=user, is_read=False
    )
    recent_notifs = Notification.objects.filter(
        recipient=user
    )[:6]

    # Unread chat messages count
    unread_messages = Message.objects.filter(
        receiver=user, is_read=False
    ).count()

    return {
        'unread_notif_count': unread_notifs.count(),
        'recent_notifications': recent_notifs,
        'unread_messages_count': unread_messages,
    }


def seo_context(request):
    """
    Inject canonical base URL, absolute canonical page URL,
    and verified clinic NAP (Name, Address, Phone) metadata for SEO templates.
    """
    configured_base = getattr(settings, 'CANONICAL_BASE_URL', '').strip().rstrip('/')
    if not configured_base:
        configured_base = os.environ.get('CANONICAL_BASE_URL', '').strip().rstrip('/')

    if configured_base:
        canonical_base = configured_base
    else:
        scheme = 'https' if request.is_secure() else request.scheme
        host = request.get_host()
        canonical_base = f"{scheme}://{host}"

    # Strips query parameters to prevent duplicate indexed URLs
    canonical_url = f"{canonical_base}{request.path}"

    clinic_nap = {
        'name': 'Dr. Dhvani Patalia Physio Rehab',
        'doctor_name': 'Dr. Dhvani Patalia',
        'degrees': 'B.P.T, Certified Chiropractor, Fellowship in Neuromusculoskeletal Techniques',
        'job_title': 'Certified Chiropractor & Physiotherapist',
        'full_address': 'Ground Floor, Narayan Cottage, Bedi Rd, opposite New Super Medical, Panchasar, Pancheshwar Tower, Jamnagar, Gujarat 361006, India',
        'street_address': 'Ground Floor, Narayan Cottage, Bedi Rd, opposite New Super Medical, Panchasar, Pancheshwar Tower',
        'locality': 'Jamnagar',
        'region': 'Gujarat',
        'postal_code': '361006',
        'country': 'IN',
        'phone': '+91 94095 10501',
        'phone_raw': '9409510501',
        'email': 'physio.rehab.guj@gmail.com',
        'whatsapp_url': 'https://wa.me/919409510501',
        'geo_lat': '22.4707',
        'geo_lng': '70.0577',
    }

    google_site_verification = (
        getattr(settings, "GOOGLE_SITE_VERIFICATION_TOKEN", "").strip()
        or os.environ.get("GOOGLE_SITE_VERIFICATION_TOKEN", "").strip()
    )

    return {
        'canonical_base': canonical_base,
        'canonical_url': canonical_url,
        'clinic_nap': clinic_nap,
        'google_site_verification': google_site_verification,
    }
