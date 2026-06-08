from django.utils import timezone


class UpdateLastSeenMiddleware:
    """Auto-updates UserActivity.last_seen for every authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            try:
                from core.models import UserActivity
                UserActivity.objects.filter(user=request.user).update(last_seen=timezone.now())
            except Exception:
                pass
        return response