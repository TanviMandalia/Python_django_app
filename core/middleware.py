from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.views.decorators.cache import add_never_cache_headers

from .models import Profile


MAX_ATTEMPTS = 5
LOCKOUT_MINS = 15
SESSION_MINS = 30


# ───────────────────────────────
# 1. LAST SEEN TRACKING
# ───────────────────────────────
class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            Profile.objects.filter(user=request.user).update(last_seen=timezone.now())

        return response


# ───────────────────────────────
# 2. SESSION TIMEOUT
# ───────────────────────────────
class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # If the user selected "Remember Me", their session is persistent across
            # browser restarts and days, governed by the 14-day persistent cookie expiry.
            # Do not force a premature 30-minute idle logout on remembered sessions.
            is_remembered = request.session.get("remember_me", False)

            if not is_remembered:
                last_activity = request.session.get("last_activity")

                if last_activity:
                    from datetime import datetime

                    last_dt = datetime.fromisoformat(last_activity)
                    now_dt = timezone.now().replace(tzinfo=None)

                    # Use total_seconds() to accurately compute gaps >= 24 hours
                    inactive_seconds = (now_dt - last_dt).total_seconds()
                    inactive_mins = int(inactive_seconds // 60)

                    if inactive_mins >= SESSION_MINS:
                        logout(request)
                        messages.warning(
                            request,
                            f"⏱️ Logged out after {SESSION_MINS} minutes inactivity."
                        )
                        return redirect("login")

            request.session["last_activity"] = timezone.now().replace(
                tzinfo=None
            ).isoformat()

        return self.get_response(request)


# ───────────────────────────────
# 3. LOGIN ATTEMPT LIMIT
# ───────────────────────────────
class LoginAttemptMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/login/' and request.method == 'POST':
            from core.ip_utils import get_client_ip
            ip = get_client_ip(request) or request.META.get('REMOTE_ADDR', '0.0.0.0')
            key = f'login_attempts_{ip}'
            attempts = cache.get(key, 0)

            if attempts >= MAX_ATTEMPTS:
                messages.error(
                    request,
                    '🔒 Too many failed login attempts. Try later.'
                )
                return redirect('login')

        return self.get_response(request)


# ───────────────────────────────
# 4. SUBSCRIPTION GATE
# ───────────────────────────────
class SubscriptionGateMiddleware:
    EXEMPT = [
        '/login/', '/logout/', '/register/', '/forgot-password/',
        '/verify-otp/', '/reset-password/', '/resend-otp/',
        '/subscription/', '/super-admin/', '/support/submit/',
        '/static/', '/media/',
    ]

    PREMIUM_PATHS = [
        '/analytics/', '/export/', '/admin-salary/', '/admin-attendance/',
        '/admin-tasks/', '/admin-blog/', '/admin-session-notes/',
        '/admin-leaves/', '/admin-reviews/', '/admin-promos/',
        '/admin-staff/', '/add-staff/', '/progress/', '/admin-settings/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if any(path.startswith(x) for x in self.EXEMPT):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)

        try:
            if user.is_superuser and user.profile.is_platform_admin:
                return self.get_response(request)
        except (AttributeError, ObjectDoesNotExist):
            # No profile yet, or profile has no is_platform_admin — treat
            # as "not a platform admin" and fall through, rather than
            # silently swallowing every possible exception here.
            pass

        return self.get_response(request)


# ───────────────────────────────
# 5. PREVENT BACK AFTER LOGOUT
# ───────────────────────────────
class PreventBackAfterLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        add_never_cache_headers(response)
        return response


# ───────────────────────────────
# 6. SEO & PRIVACY ROBOTS TAG
# ───────────────────────────────
class SEORobotsTagMiddleware:
    """
    Guarantees privacy for non-public endpoints.
    Emits 'X-Robots-Tag: noindex, nofollow, noarchive' on all administrative,
    staff, patient, authentication, and API endpoints so search engines
    never index private healthcare or administrative records.
    """
    INDEXABLE_PATHS = {
        '/',
        '/about/',
        '/services/',
        '/contact/',
        '/blogs/',
        '/robots.txt',
        '/sitemap.xml',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path

        # If static or media asset, do not restrict indexing
        if path.startswith('/static/') or path.startswith('/media/'):
            return response

        # Check if path is an eligible public page
        is_indexable = (
            path in self.INDEXABLE_PATHS
            or (path.startswith('/services/') and not path.startswith('/admin-'))
            or (path.startswith('/blogs/') and not path.startswith('/admin-blog/'))
            or (path.startswith('/google') and path.endswith('.html'))
        )

        if not is_indexable:
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'

        return response



# ───────────────────────────────
# 7. SECURE PUBLIC VISITOR TRACKING
# ───────────────────────────────
class PublicVisitorTrackingMiddleware:
    """
    Server-side visitor analytics middleware.
    Accurately records eligible visits to public marketing pages with real client IP,
    device category, referrer, and consent status.
    Excludes:
      - Authenticated Super Admin requests (strictly server-side verified; never client-driven)
      - Static/media files, health checks, robots.txt, sitemap.xml, favicon
      - Private admin, staff, patient dashboards, auth endpoints, APIs
      - Non-GET requests and non-200 responses
    """
    EXCLUDED_PREFIXES = (
        '/admin/',
        '/super-admin/',
        '/staff/',
        '/client/',
        '/api/',
        '/static/',
        '/media/',
        '/login/',
        '/logout/',
        '/register/',
        '/profile/',
        '/change-password/',
        '/forgot-password/',
        '/verify-otp/',
        '/resend-otp/',
        '/reset-password/',
        '/notifications/',
        '/payments/',
        '/subscription/',
        '/healthz',
        '/robots.txt',
        '/sitemap.xml',
        '/favicon.ico',
        '/bulk-import/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only track HTTP GET requests with status 200
        if request.method != "GET" or response.status_code != 200:
            return response

        path = request.path
        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return response

        # Exclude authenticated Super Admin (server-side verification)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if user.is_superuser:
                return response
            try:
                if getattr(user, "profile", None) and user.profile.is_platform_admin:
                    return response
            except Exception:
                pass

        # Avoid duplicate middleware execution within a single request cycle
        if getattr(request, "_visitor_tracked", False):
            return response
        request._visitor_tracked = True

        try:
            self._track_visit(request, response, path)
        except Exception as e:
            # Analytics recording must never crash or block public page delivery
            import logging
            logging.getLogger("core.visitor_analytics").error("Error in visitor tracking: %s", e)

        return response

    def _track_visit(self, request, response, path):
        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from core.ip_utils import get_client_ip, generate_pseudonymous_visitor_id, sanitize_referrer_url
        from core.models import VisitorSession, PageViewEvent

        now = timezone.now()
        client_ip = get_client_ip(request)

        # Consent choice from cookie or header
        consent_choice = request.COOKIES.get("va_consent_choice", "").strip().lower()
        if consent_choice == "accepted":
            consent_status = "accepted"
            consent_given = True
        elif consent_choice == "declined":
            consent_status = "declined"
            consent_given = False
        else:
            consent_status = "pending"
            consent_given = False

        session_key = request.COOKIES.get("va_session", "").strip()
        is_new_cookie = False
        if not session_key or len(session_key) > 64:
            session_key = "vs_" + uuid.uuid4().hex[:28]
            is_new_cookie = True

        ua_raw = request.META.get("HTTP_USER_AGENT", "")
        from core.views import _parse_user_agent, _parse_referrer_info
        dev_cat, browser, os_name = _parse_user_agent(ua_raw)

        raw_referrer = request.META.get("HTTP_REFERER", "")
        ref_cat, ref_dom = _parse_referrer_info(raw_referrer)
        clean_ref_url = sanitize_referrer_url(raw_referrer)

        visitor_id = generate_pseudonymous_visitor_id(client_ip, ua_raw, now.strftime("%Y-%m-%d"))

        # Look up existing active session
        session = VisitorSession.objects.filter(session_key=session_key).first()
        if session:
            # Active session continuation
            session.last_activity = now
            session.exit_page = path[:200]
            session.total_page_views += 1
            if client_ip and not session.ip_address:
                session.ip_address = client_ip
            if consent_choice in ("accepted", "declined"):
                session.consent_status = consent_status
                session.consent_given = consent_given
            session.save(update_fields=[
                "last_activity", "exit_page", "total_page_views",
                "ip_address", "consent_status", "consent_given"
            ])
        else:
            session = VisitorSession.objects.create(
                session_key=session_key,
                visitor_id=visitor_id,
                ip_address=client_ip,
                started_at=now,
                last_activity=now,
                device_category=dev_cat,
                browser_family=browser,
                os_family=os_name,
                referrer_category=ref_cat,
                referrer_domain=ref_dom[:200],
                referrer_url=clean_ref_url,
                entry_page=path[:200],
                exit_page=path[:200],
                total_page_views=1,
                total_active_seconds=0,
                consent_status=consent_status,
                consent_given=consent_given,
            )

        # Record PageViewEvent
        PageViewEvent.objects.create(
            session=session,
            path=path[:200],
            referrer=clean_ref_url,
            view_count=1,
            active_seconds=0,
            timestamp=now,
        )

        # Set session cookie if new
        if is_new_cookie:
            from django.conf import settings
            response.set_cookie(
                "va_session",
                session_key,
                max_age=30 * 86400,
                httponly=False,
                samesite="Lax",
                secure=not settings.DEBUG,
            )
