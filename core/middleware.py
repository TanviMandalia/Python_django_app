from django.utils import timezone
from django.core.cache import cache
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.views.decorators.cache import add_never_cache_headers

from .models import UserActivity


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
            UserActivity.objects.update_or_create(
                user=request.user,
                defaults={'last_seen': timezone.now()}
            )

        return response


# ───────────────────────────────
# 2. SESSION TIMEOUT
# ───────────────────────────────
class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')

            if last_activity:
                from datetime import datetime

                last_dt = datetime.fromisoformat(last_activity)
                now_dt = timezone.now().replace(tzinfo=None)

                inactive = (now_dt - last_dt).seconds // 60

                if inactive >= SESSION_MINS:
                    logout(request)
                    messages.warning(
                        request,
                        f'⏱️ Logged out after {SESSION_MINS} minutes inactivity.'
                    )
                    return redirect('login')

            request.session['last_activity'] = timezone.now().replace(
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
            ip = self._get_ip(request)
            key = f'login_attempts_{ip}'
            attempts = cache.get(key, 0)

            if attempts >= MAX_ATTEMPTS:
                messages.error(
                    request,
                    '🔒 Too many failed login attempts. Try later.'
                )
                return redirect('login')

        return self.get_response(request)

    def _get_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


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
        except:
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