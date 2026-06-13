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