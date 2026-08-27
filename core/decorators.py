from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """Allow only superusers or clinic admins."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or hasattr(request.user, 'clinic_admin_profile'):
            return view_func(request, *args, **kwargs)
        messages.error(request, '⛔ Access denied: Administrator permissions required.')
        return redirect('client_dashboard')
    return wrapper


# Alias for backwards compatibility
admin_only = admin_required


def doctor_required(view_func):
    """Allow doctors/physiotherapists, clinic admins, or superusers."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or hasattr(request.user, 'clinic_admin_profile'):
            return view_func(request, *args, **kwargs)
        if hasattr(request.user, 'staff_profile'):
            if request.user.staff_profile.role == 'physiotherapist':
                return view_func(request, *args, **kwargs)
        messages.error(request, '⛔ Access denied: Doctor / Physiotherapist access required.')
        return redirect('client_dashboard')
    return wrapper


def staff_required(view_func):
    """Allow all staff members (physiotherapist, receptionist, assistant) or admins."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or hasattr(request.user, 'clinic_admin_profile') or hasattr(request.user, 'staff_profile'):
            return view_func(request, *args, **kwargs)
        messages.error(request, '⛔ Access denied: Staff access required.')
        return redirect('client_dashboard')
    return wrapper


def client_required(view_func):
    """Require authenticated client/patient."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def super_admin_required(view_func):
    """Allow only platform super administrators."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            if hasattr(request.user, 'profile') and request.user.profile.is_platform_admin:
                return view_func(request, *args, **kwargs)
            # If standard superuser without explicit profile flag, also allow
            return view_func(request, *args, **kwargs)
        messages.error(request, '⛔ Access denied: Platform Super Admin privileges required.')
        return redirect('admin_dashboard')
    return wrapper