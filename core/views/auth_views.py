import random
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from core.models import Profile, PasswordResetOTP, UserActivity
from core.forms.auth_forms import UserRegistrationForm, UserLoginForm, ProfileEditForm
from core.email_utils import send_otp_email


def get_role_redirect_url(user):
    """Determine the appropriate landing dashboard based on user role."""
    if hasattr(user, 'profile') and user.profile.is_platform_admin:
        return 'super_admin_dashboard'
    if user.is_superuser or hasattr(user, 'clinic_admin_profile'):
        return 'admin_dashboard'
    if hasattr(user, 'staff_profile'):
        if user.staff_profile.role == 'physiotherapist':
            return 'progress_tracking'
        return 'staff_dashboard'
    return 'client_dashboard'


def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_redirect_url(request.user))

    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user_obj = User.objects.filter(username=username_or_email).first() or \
                       User.objects.filter(email__iexact=username_or_email).first()

            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)
                if user:
                    if not user.is_active:
                        messages.error(request, "⛔ Your account has been deactivated. Please contact clinic support.")
                        return render(request, "login.html", {"form": form})
                    login(request, user)
                    messages.success(request, f"👋 Welcome back, {user.first_name or user.username}!")
                    next_url = request.GET.get('next')
                    return redirect(next_url if next_url else get_role_redirect_url(user))

            messages.error(request, "❌ Invalid username/email or password.")
    else:
        form = UserLoginForm()

    return render(request, "login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_redirect_url(request.user))

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone_number = form.cleaned_data.get('phone_number', '')

            if User.objects.filter(username=username).exists():
                messages.error(request, "⚠️ Username is already taken.")
            elif User.objects.filter(email__iexact=email).exists():
                messages.error(request, "⚠️ An account with this email already exists.")
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                profile, _ = Profile.objects.get_or_create(user=user)
                if phone_number:
                    profile.phone_number = phone_number
                    profile.save()

                login(request, user)
                messages.success(request, "🎉 Account created successfully! Welcome to PhysioRehab.")
                return redirect("client_dashboard")
    else:
        form = UserRegistrationForm()

    return render(request, "register.html", {"form": form})


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "🔒 You have been safely logged out.")
    return redirect("home")


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "profile.html", {"profile": profile, "user": request.user})


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        first_name = request.POST.get("first_name", request.user.first_name)
        last_name = request.POST.get("last_name", request.user.last_name)
        email = request.POST.get("email", request.user.email)

        if form.is_valid():
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()
            form.save()
            messages.success(request, "✅ Profile updated successfully!")
            return redirect("profile")
    else:
        form = ProfileEditForm(instance=profile, initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })

    return render(request, "edit_profile.html", {"form": form, "profile": profile})


def request_otp(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            otp_code = f"{random.randint(100000, 999999)}"
            PasswordResetOTP.objects.filter(user=user).delete()
            PasswordResetOTP.objects.create(user=user, otp=otp_code)
            send_otp_email(email, otp_code)
            request.session['reset_user_id'] = user.id
            messages.success(request, "📧 OTP has been sent to your email address.")
            return redirect("verify_otp")
        else:
            messages.error(request, "⚠️ No account found with that email address.")
    return render(request, "request_otp.html")


def verify_otp(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, "Please enter your email first.")
        return redirect("request_otp")

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect("request_otp")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()
        otp_record = PasswordResetOTP.objects.filter(user=user, otp=entered_otp).first()

        if otp_record and not otp_record.is_expired():
            request.session['otp_verified'] = True
            otp_record.delete()
            messages.success(request, "✅ OTP verified. You may now reset your password.")
            return redirect("reset_password")
        else:
            messages.error(request, "❌ Invalid or expired OTP. Please try again.")

    return render(request, "verify_otp.html", {"email": user.email})


def resend_otp(request):
    user_id = request.session.get('reset_user_id')
    if user_id:
        user = User.objects.filter(id=user_id).first()
        if user:
            otp_code = f"{random.randint(100000, 999999)}"
            PasswordResetOTP.objects.filter(user=user).delete()
            PasswordResetOTP.objects.create(user=user, otp=otp_code)
            send_otp_email(user.email, otp_code)
            messages.info(request, "🔄 A new OTP has been sent to your email.")
    return redirect("verify_otp")


def reset_password(request):
    user_id = request.session.get('reset_user_id')
    is_verified = request.session.get('otp_verified')
    if not user_id or not is_verified:
        return redirect("request_otp")

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect("request_otp")

    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password and password == confirm_password:
            user.set_password(password)
            user.save()
            request.session.pop('reset_user_id', None)
            request.session.pop('otp_verified', None)
            messages.success(request, "🔑 Password successfully reset! Please log in with your new password.")
            return redirect("login")
        else:
            messages.error(request, "❌ Passwords do not match.")

    return render(request, "reset_password.html")


@login_required
def change_password_request(request):
    if request.method == "POST":
        old_password = request.POST.get("old_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not check_password(old_password, request.user.password):
            messages.error(request, "❌ Current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "❌ New passwords do not match.")
        elif len(new_password) < 6:
            messages.error(request, "⚠️ New password must be at least 6 characters.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "✅ Password changed successfully!")
            return redirect("profile")

    return render(request, "change_password.html")

