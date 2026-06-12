# ════════════════════════════════════════════════════════════
# FILE 1 — core/middleware.py   (NEW FILE — create this)
# ════════════════════════════════════════════════════════════
#
# This fixes Issue 6: last_seen never updates for logged-in users
# Users were always showing as "offline" even when browsing the site
#
# STEP 1: Create this file at:  core/middleware.py
# STEP 2: Add to settings.py MIDDLEWARE list (see bottom of this file)

from django.utils import timezone
from .models import UserActivity

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


# ════════════════════════════════════════════════════════════
# FILE 2 — myproject/settings.py  (EDIT this)
# ════════════════════════════════════════════════════════════
#
# Find your MIDDLEWARE list and add this ONE line at the END:
#
# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     ...
#     'core.middleware.UpdateLastSeenMiddleware',   ← ADD THIS
# ]


# ════════════════════════════════════════════════════════════
# FILE 3 — core/views.py   (FIX these two functions)
# ════════════════════════════════════════════════════════════
#
# Issue 5: start_typing saves typing_to_id but stop_typing
# saves typing_to — inconsistent field names causing errors
#
# Find start_typing in views.py and REPLACE the whole function:

"""
@csrf_exempt
@login_required
def start_typing(request):
    if request.method == 'POST':
        try:
            data        = json.loads(request.body)
            receiver_id = data.get('receiver_id')
        except Exception:
            receiver_id = None
        obj, _ = UserActivity.objects.get_or_create(user=request.user)
        obj.is_typing    = True
        obj.typing_to_id = receiver_id
        obj.last_seen    = timezone.now()
        obj.save(update_fields=['is_typing', 'typing_to_id', 'last_seen'])
        return JsonResponse({'status': 'started'})
    return JsonResponse({'status': 'invalid'}, status=400)


@csrf_exempt
@login_required
def stop_typing(request):
    if request.method == 'POST':
        obj, _ = UserActivity.objects.get_or_create(user=request.user)
        obj.is_typing    = False
        obj.typing_to_id = None
        obj.last_seen    = timezone.now()
        obj.save(update_fields=['is_typing', 'typing_to_id', 'last_seen'])
        return JsonResponse({'status': 'stopped'})
    return JsonResponse({'status': 'invalid'}, status=400)
"""