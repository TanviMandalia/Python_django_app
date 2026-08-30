from .models import Notification, Message, Hospital, ClinicSettings


def unread_notifications(request):
    """Inject unread notification count, unread chat messages, and clinic branding into every template."""
    context = {
        'unread_notif_count': 0,
        'recent_notifications': [],
        'unread_messages_count': 0,
        'clinic_info': None,
        'user_role': None,
    }

    try:
        context['clinic_info'] = ClinicSettings.objects.first()
    except Exception:
        pass

    if not request.user.is_authenticated:
        return context

    try:
        unread_notifs = Notification.objects.filter(
            recipient=request.user, is_read=False
        )
        recent_notifs = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')[:6]

        unread_messages = Message.objects.filter(
            receiver=request.user, is_read=False
        ).count()

        context['unread_notif_count'] = unread_notifs.count()
        context['recent_notifications'] = recent_notifs
        context['unread_messages_count'] = unread_messages

        # Identify User Role for dynamic sidebar & navigation
        user = request.user
        if hasattr(user, 'profile') and user.profile.is_platform_admin:
            context['user_role'] = 'super_admin'
        elif user.is_superuser or hasattr(user, 'clinic_admin_profile'):
            context['user_role'] = 'admin'
        elif hasattr(user, 'staff_profile'):
            role = user.staff_profile.role
            if role == 'physiotherapist':
                context['user_role'] = 'doctor'
            else:
                context['user_role'] = 'staff'
        else:
            context['user_role'] = 'client'

    except Exception:
        pass

    return context

