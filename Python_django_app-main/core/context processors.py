from .models import Notification, Message
from django.db.models import Q


def unread_notifications(request):
    """Inject unread notification count + recent notifications into every template."""
    if not request.user.is_authenticated:
        return {}

    unread_notifs = Notification.objects.filter(
        recipient=request.user, is_read=False
    )
    recent_notifs = Notification.objects.filter(
        recipient=request.user
    )[:6]

    # Unread chat messages count
    unread_messages = Message.objects.filter(
        receiver=request.user, is_read=False
    ).count()

    return {
        'unread_notif_count': unread_notifs.count(),
        'recent_notifications': recent_notifs,
        'unread_messages_count': unread_messages,
    }