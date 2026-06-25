from django.shortcuts import redirect

def admin_only(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            return redirect('client_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper