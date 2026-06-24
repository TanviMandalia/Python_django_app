# ════════════════════════════════════════════════════════════
# FEATURE 2 — Login Attempt Limit + Session Timeout
# FILE: core/middleware.py  (ADD to your existing middleware.py)
# ════════════════════════════════════════════════════════════
 
from django.utils import timezone
from django.core.cache import cache
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from .models import UserActivity
 
# ── How many failed attempts before lockout ──
MAX_ATTEMPTS  = 5
LOCKOUT_MINS  = 15   # lockout duration in minutes
SESSION_MINS  = 30   # auto logout after X mins of inactivity
 
 
class UpdateLastSeenMiddleware:
    """Update user last_seen on every request."""
    def __init__(self, get_response):
        self.get_response = get_response
 
    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            UserActivity.objects.update_or_create(
                user=request.user,
                defaults={'last_seen': timezone.now()}
            )
        return response
 
 
class SessionTimeoutMiddleware:
    """Auto logout after SESSION_MINS minutes of inactivity."""
    def __init__(self, get_response):
        self.get_response = get_response
 
    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
 
            if last_activity:
                from datetime import datetime
                last_dt  = datetime.fromisoformat(last_activity)
                now_dt   = timezone.now().replace(tzinfo=None)
                inactive = (now_dt - last_dt).seconds // 60
 
                if inactive >= SESSION_MINS:
                    logout(request)
                    messages.warning(
                        request,
                        f'⏱️ You were logged out after {SESSION_MINS} minutes of inactivity.'
                    )
                    return redirect('login')
 
            # Update last activity timestamp
            request.session['last_activity'] = timezone.now().replace(
                tzinfo=None
            ).isoformat()
 
        return self.get_response(request)
 
 
class LoginAttemptMiddleware:
    """
    Block IP after MAX_ATTEMPTS failed logins for LOCKOUT_MINS minutes.
    Works together with the login_view changes below.
    """
    def __init__(self, get_response):
        self.get_response = get_response
 
    def __call__(self, request):
        if request.path == '/login/' and request.method == 'POST':
            ip        = self._get_ip(request)
            cache_key = f'login_attempts_{ip}'
            attempts  = cache.get(cache_key, 0)
 
            if attempts >= MAX_ATTEMPTS:
                remaining = cache.ttl(cache_key) // 60
                messages.error(
                    request,
                    f'🔒 Too many failed login attempts. '
                    f'Please try again in {remaining} minute(s).'
                )
                return redirect('login')
 
        return self.get_response(request)
 
    def _get_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class SubscriptionGateMiddleware:
    """
    Block expired clinic-admin access. Redirect to subscription page.
    Trial admins may only access basic features; premium features are blocked.
    Platform superadmins are always allowed.
    """
    EXEMPT = [
        '/login/', '/logout/', '/register/', '/forgot-password/',
        '/verify-otp/', '/reset-password/', '/resend-otp/',
        '/subscription/', '/super-admin/', '/support/submit/',
        '/static/', '/media/', '/__mockup__/',
    ]

    PREMIUM_PATHS = [
        '/analytics/',
        '/export/',
        '/admin-salary/',
        '/admin-attendance/',
        '/admin-tasks/',
        '/admin-blog/',
        '/admin-session-notes/',
        '/admin-leaves/',
        '/admin-reviews/',
        '/admin-promos/',
        '/admin-staff/',
        '/add-staff/',
        '/progress/',
        '/admin-settings/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        for prefix in self.EXEMPT:
            if path.startswith(prefix):
                return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)

        try:
            if user.is_superuser and user.profile.is_platform_admin:
                return self.get_response(request)
        except Exception:
            pass

        if user.is_superuser:
            try:
                from .models import HospitalSubscription
                sub = user.clinic_admin_profile.hospital.subscription
                if sub.status == 'expired' or sub.is_expired:
                    return redirect('/subscription/?reason=expired')
                if sub.status == 'trial':
                    for premium in self.PREMIUM_PATHS:
                        if path.startswith(premium):
                            return redirect('/subscription/?reason=trial')
            except Exception:
                pass

        return self.get_response(request)


class SubscriptionExpiryNotifierMiddleware:
    """Send expiry warning email 5 days before subscription expires (once per day via cache)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = request.user
        if not user.is_authenticated or not user.is_superuser:
            return response
        try:
            from django.utils import timezone as tz
            from .email_utils import send_subscription_expiry_warning_email
            sub = user.clinic_admin_profile.hospital.subscription
            if sub.expires_at and sub.status == 'active':
                today = tz.now().date()
                days_left = (sub.expires_at - today).days
                if 0 < days_left <= 5:
                    key = f"expiry_warned_{user.clinic_admin_profile.hospital.id}_{sub.expires_at}"
                    if not cache.get(key):
                        send_subscription_expiry_warning_email(
                            user.clinic_admin_profile.hospital, sub.plan, sub.expires_at, days_left
                        )
                        cache.set(key, True, 60 * 60 * 20)
        except Exception:
            pass
        return response