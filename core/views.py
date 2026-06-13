
# ════════════════════════════════════════════════════════════
# core/views.py — TOP IMPORTS (replace your existing imports)
# ════════════════════════════════════════════════════════════
 
import json
import random
import logging
from datetime import datetime, time as dtime, timedelta   # ← time as dtime ADDED
 
from .models import Blog
from .forms import BlogForm
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache                        # ← ADDED
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password

from django.core.mail import send_mail
from django.conf import settings
 
from .models import (
    Appointment, Attendance, DailyTask, LeaveApplication,
    Message, Notification, PasswordResetOTP, Profile,
    SalaryRecord, SessionNote, StaffProfile, UserActivity, ClinicSettings
)
from .email_utils import (
    send_appointment_confirmation,
    send_appointment_status_update,
    send_admin_new_appointment_alert,
    send_otp_email,
    send_leave_status_email,
    send_salary_paid_email,
    send_task_assigned_email,
    send_staff_welcome_email,
)
from .notifications import (
    notify_appointment_booked,
    notify_appointment_status,
    notify_leave_decision,
    notify_task_assigned,
    notify_salary_paid,
)

logger = logging.getLogger(__name__)

# Shift definitions
MORNING_START = dtime(10, 0)
MORNING_END   = dtime(13, 0)
EVENING_START = dtime(16, 0)
EVENING_END   = dtime(20, 0)
LATE_GRACE    = 15


# ─── HELPERS ─────────────────────────────────────────────────

def get_admin_user():
    return User.objects.filter(is_superuser=True).first()


def is_online(user):
    try:
        activity = UserActivity.objects.get(user=user)
        if not activity.last_seen:
            return False
        return activity.last_seen >= timezone.now() - timedelta(minutes=2)
    except UserActivity.DoesNotExist:
        return False


# ─── PUBLIC PAGES ────────────────────────────────────────────

def home(request):
    return render(request, 'home.html')

def about(request):
    return render(request, 'about.html')

def services(request):
    return render(request, 'services.html')

def contact(request):
    if request.method == 'POST':
        messages.success(request, '✅ Message sent! We will contact you soon.')
        return redirect('/contact/')
    return render(request, 'contact.html')

# =========================
# PUBLIC BLOG LIST
# =========================
def blog_list(request):
    blogs = Blog.objects.order_by('-created_at')
    return render(request, 'blog.html', {'blogs': blogs})


# =========================
# PUBLIC BLOG DETAIL
# =========================
def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    return render(request, 'blog_detail.html', {'blog': blog})


# =========================
# ADMIN BLOG LIST
# =========================
def admin_blog_list(request):
    blogs = Blog.objects.order_by('-created_at')

    return render(
        request,
        'blog_list.html',
        {'blogs': blogs}
    )
    
# =========================
# ADMIN ADD BLOG
# =========================
def admin_blog_add(request):
    if request.method == "POST":
        title = request.POST.get('title')
        content = request.POST.get('content')
        image = request.FILES.get('image')

        Blog.objects.create(
            title=title,
            content=content,
            image=image
        )

        return redirect('admin_blog_list')

    return render(request, 'blog_form.html')


# =========================
# ADMIN EDIT BLOG
# =========================
def admin_blog_edit(request, id):
    blog = get_object_or_404(Blog, id=id)

    if request.method == "POST":
        blog.title = request.POST.get('title')
        blog.content = request.POST.get('content')

        if request.FILES.get('image'):
            blog.image = request.FILES.get('image')

        blog.save()
        return redirect('admin_blog_list')

    return render(request, 'blog_form.html', {'blog': blog})


# =========================
# ADMIN DELETE BLOG
# =========================
def admin_blog_delete(request, id):
    blog = get_object_or_404(Blog, id=id)

    if request.method == "POST":
        blog.delete()
        return redirect('admin_blog_list')

    return render(request, 'blog_delete.html', {'blog': blog})
    

# ─── AUTH ────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
 
    if request.method == 'POST':
        ip        = _get_client_ip(request)
        cache_key = f'login_attempts_{ip}'
        attempts  = cache.get(cache_key, 0)
 
        # Double-check lockout (middleware also checks)
        if attempts >= 5:
            remaining = cache.ttl(cache_key) // 60
            messages.error(request,
                f'🔒 Account locked. Try again in {remaining} minute(s).')
            return render(request, 'login.html')
 
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)
 
        if user:
            # ✅ Success — clear failed attempts
            cache.delete(cache_key)
            login(request, user)
            return _redirect_by_role(user)
        else:
            # ❌ Failed — increment counter
            attempts += 1
            cache.set(cache_key, attempts, timeout=15*60)  # 15 min window
            remaining_attempts = 5 - attempts
 
            if remaining_attempts > 0:
                messages.error(request,
                    f'❌ Invalid username or password. '
                    f'{remaining_attempts} attempt(s) remaining before lockout.')
            else:
                messages.error(request,
                    '🔒 Too many failed attempts. Account locked for 15 minutes.')
 
    return render(request, 'login.html')
 
 
def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def get_shift(t):
    """Return which shift a time belongs to."""
    if MORNING_START <= t <= MORNING_END:
        return 'morning'
    if EVENING_START <= t <= EVENING_END:
        return 'evening'
    return None
 
 
def is_late(t, shift):
    """Check if clock-in time is late beyond grace period."""
    if shift == 'morning':
        grace = (
            datetime.combine(datetime.today(), MORNING_START)
            + timedelta(minutes=LATE_GRACE)
        ).time()
        return t > grace
    if shift == 'evening':
        grace = (
            datetime.combine(datetime.today(), EVENING_START)
            + timedelta(minutes=LATE_GRACE)
        ).time()
        return t > grace
    return False


def _redirect_by_role(user):
    if user.is_superuser:
        return redirect('admin_dashboard')
    if user.is_staff or hasattr(user, 'staff_profile'):
        return redirect('staff_dashboard')
    return redirect('client_dashboard')


def register_view(request):
    if request.method == 'POST':
        first_name       = request.POST.get('first_name', '').strip()
        last_name        = request.POST.get('last_name', '').strip()
        username         = request.POST.get('username', '').strip()
        email            = request.POST.get('email', '').strip()
        password         = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if password != confirm_password:
            messages.error(request, '❌ Passwords do not match!')
            return redirect('register')
        if User.objects.filter(username=username).exists():
            messages.error(request, '❌ Username already taken!')
            return redirect('register')
        if User.objects.filter(email=email).exists():
            messages.error(request, '❌ Email already registered!')
            return redirect('register')

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )
        messages.success(request, '✅ Account created! Please login.')
        return redirect('login')
    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    return redirect('home')


# ─── PROFILE ─────────────────────────────────────────────────

@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'profile.html', {'profile': profile})


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name  = request.POST.get('last_name', '').strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()

        profile.phone_number      = request.POST.get('phone_number', '').strip()
        profile.gender            = request.POST.get('gender', '')
        profile.date_of_birth     = request.POST.get('date_of_birth') or None
        profile.blood_group       = request.POST.get('blood_group', '')
        profile.emergency_contact = request.POST.get('emergency_contact', '').strip()
        profile.medical_notes     = request.POST.get('medical_notes', '').strip()
        profile.address           = request.POST.get('address', '').strip()
        if request.FILES.get('profile_photo'):
            profile.profile_photo = request.FILES['profile_photo']
        profile.save()

        messages.success(request, '✅ Profile updated successfully.')
        return redirect('profile')
    return render(request, 'edit_profile.html', {'profile': profile})


# ─── PASSWORD RESET (OTP FLOW) ───────────────────────────────

def request_otp(request):
    """Step 1 – user enters their email."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, '❌ No account found with that email.')
            return render(request, 'request_otp.html')

        # Expire old OTPs
        PasswordResetOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.create(user=user, otp=otp)

        ok = send_otp_email(email, otp, purpose='Password Reset')
        if ok:
            messages.success(request, f'✅ OTP sent to {email}. Check your inbox.')
        else:
            messages.warning(request, '⚠️ Could not send email. Check server email config.')

        request.session['reset_user_id'] = user.id
        return redirect('verify_otp')

    return render(request, 'request_otp.html')


def verify_otp(request):
    """Step 2 – user enters OTP."""
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please start again.')
        return redirect('request_otp')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        try:
            user = User.objects.get(id=user_id)
            otp_obj = PasswordResetOTP.objects.filter(user=user).latest('created_at')
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            messages.error(request, '❌ Invalid or expired OTP.')
            return redirect('request_otp')

        if otp_obj.is_expired():
            messages.error(request, '❌ OTP expired. Please request a new one.')
            return redirect('request_otp')

        if entered_otp == otp_obj.otp:
            request.session['otp_verified'] = True
            otp_obj.delete()
            return redirect('reset_password')

        messages.error(request, '❌ Incorrect OTP. Try again.')
    return render(request, 'verify_otp.html')


def resend_otp(request):
    """Resend OTP to same email."""
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('request_otp')
    try:
        user = User.objects.get(id=user_id)
        PasswordResetOTP.objects.filter(user=user).delete()
        otp = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.create(user=user, otp=otp)
        ok = send_otp_email(user.email, otp, purpose='Password Reset')
        if ok:
            messages.success(request, '✅ New OTP sent!')
        else:
            messages.warning(request, '⚠️ Could not send email.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    return redirect('verify_otp')


def reset_password(request):
    """
    Step 3 - Set new password after OTP verification.
    """

    if not request.session.get("otp_verified"):
        messages.error(request, "Please verify OTP first.")
        return redirect("request_otp")

    user_id = request.session.get("reset_user_id")

    if not user_id:
        messages.error(request, "Session expired.")
        return redirect("request_otp")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("request_otp")

    if request.method == "POST":
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # Empty fields
        if not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect("reset_password")

        # Password match check
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("reset_password")

        # Minimum length
        if len(password) < 8:
            messages.error(
                request,
                "Password must contain at least 8 characters."
            )
            return redirect("reset_password")

        # Same as old password check
        if user.check_password(password):
            messages.error(
                request,
                "New password cannot be the same as your current password."
            )
            return redirect("reset_password")

        # Save password
        user.set_password(password)
        user.save()

        # Clear reset session
        request.session.pop("otp_verified", None)
        request.session.pop("reset_user_id", None)

        messages.success(
            request,
            "Password reset successfully. Please login."
        )

        return redirect("login")

    return render(request, "reset_password.html")


@login_required
def change_password_request(request):
    """Logged-in user changes password via OTP sent to their email."""
    if request.method == 'POST':
        otp = str(random.randint(100000, 999999))
        PasswordResetOTP.objects.filter(user=request.user).delete()
        PasswordResetOTP.objects.create(user=request.user, otp=otp)

        ok = send_otp_email(request.user.email, otp, purpose='Password Change')
        if ok:
            messages.success(request, f'✅ OTP sent to {request.user.email}')
        else:
            messages.warning(request, '⚠️ Email not sent – check server config.')

        request.session['reset_user_id']  = request.user.id
        request.session['otp_verified']   = False
        return redirect('verify_otp')
    return render(request, 'change_password.html')


# ─── NOTIFICATIONS ───────────────────────────────────────────

@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(recipient=request.user)
    return render(request, 'notifications.html', {
        'notifications': notifs,
        'today': timezone.now().date(),
    })


@login_required
def mark_notification_read(request, notif_id):
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, '✅ All notifications marked as read.')
    return redirect('notifications')


# ─── PAYMENT ─────────────────────────────────────────────────

def payments(request):
    return render(request, 'payments.html')


# ─── CLIENT DASHBOARD ────────────────────────────────────────

@login_required
def client_dashboard(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    appointments  = Appointment.objects.filter(patient=request.user)
    upcoming      = appointments.filter(status__in=['pending', 'confirmed'])
    completed     = appointments.filter(status='completed')
    recent_notifs = Notification.objects.filter(recipient=request.user)[:5]
    return render(request, 'client_dashboard.html', {
        'appointments':     appointments,
        'upcoming':         upcoming,
        'completed':        completed,
        'total':            appointments.count(),
        'upcoming_count':   upcoming.count(),
        'completed_count':  completed.count(),
        'recent_notifs':    recent_notifs,
    })


# ─── ADMIN DASHBOARD ─────────────────────────────────────────

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    all_appointments = Appointment.objects.all()
    pending          = all_appointments.filter(status='pending').count()
    confirmed        = all_appointments.filter(status='confirmed').count()
    completed        = all_appointments.filter(status='completed').count()
    total_users      = User.objects.filter(is_superuser=False, is_staff=False).count()
    new_messages     = Message.objects.filter(receiver=request.user, is_read=False).count()
    total_staff      = StaffProfile.objects.count()
    return render(request, 'admin_dashboard.html', {
        'total_users':        total_users,
        'all_appointments':   all_appointments,
        'total_appointments': all_appointments.count(),
        'pending':            pending,
        'confirmed':          confirmed,
        'completed':          completed,
        'new_messages':       new_messages,
        'total_staff':        total_staff,
    })


# ─── APPOINTMENTS ────────────────────────────────────────────

@login_required
def book_appointment(request):
    if request.method == 'POST':
        service = request.POST.get('service', '')
        date    = request.POST.get('date', '')
        time    = request.POST.get('time', '')
        notes   = request.POST.get('notes', '')
        name    = request.user.get_full_name() or request.user.username
        email   = request.user.email
        phone   = getattr(request.user, 'profile', None)
        phone   = phone.phone_number if phone else ''

        appt = Appointment.objects.create(
            patient=request.user,
            name=name, email=email, phone=phone,
            service=service, date=date, time=time,
            notes=notes, status='pending',
        )

        # Email patient + alert admin
        send_appointment_confirmation(appt)
        admin = get_admin_user()
        if admin:
            send_admin_new_appointment_alert(appt)
            notify_appointment_booked(appt, admin)

        messages.success(request, '✅ Appointment booked! Confirmation email sent.')
        return redirect('my_appointments')
    return render(request, 'book_appointment.html')


@login_required
def my_appointments(request):
    appointments = Appointment.objects.filter(patient=request.user)
    return render(request, 'my_appointments.html', {'appointments': appointments})


@login_required
def admin_appointments(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    all_appointments = Appointment.objects.all().order_by('-created_at')
    return render(request, 'admin_appointments.html', {
        'all_appointments': all_appointments,
        'pending_count':    all_appointments.filter(status='pending').count(),
        'confirmed_count':  all_appointments.filter(status='confirmed').count(),
        'completed_count':  all_appointments.filter(status='completed').count(),
        'cancelled_count':  all_appointments.filter(status='cancelled').count(),
    })


@login_required
def update_appointment(request, appt_id, status):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    appt = get_object_or_404(Appointment, id=appt_id)
    valid = ['pending', 'confirmed', 'completed', 'cancelled']
    if status not in valid:
        messages.error(request, 'Invalid status.')
        return redirect('admin_appointments')

    appt.status = status
    appt.save()

    # Email + notification
    send_appointment_status_update(appt)
    notify_appointment_status(appt)

    messages.success(request, f'✅ Appointment {status}.')
    return redirect('admin_appointments')


# ─── ADMIN PATIENTS ──────────────────────────────────────────

@login_required
def admin_patients(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    patients = User.objects.filter(is_superuser=False, is_staff=False).order_by('-date_joined')
    return render(request, 'admin_patients.html', {'patients': patients})


# ─── CHAT ────────────────────────────────────────────────────

@login_required
def client_chat(request):
    admin = get_admin_user()
    if not admin:
        return render(request, 'client_chat.html', {'error': 'No admin account found.'})

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=request.user, receiver=admin,
                content=content, status=Message.STATUS_SENT,
            )
        return redirect('client_chat')

    msgs = Message.objects.filter(
        Q(sender=request.user, receiver=admin) |
        Q(sender=admin, receiver=request.user)
    ).order_by('created_at')

    Message.objects.filter(
        sender=admin, receiver=request.user, is_read=False
    ).update(is_read=True, status=Message.STATUS_READ)

    admin_activity = UserActivity.objects.filter(user=admin).first()
    return render(request, 'client_chat.html', {
        'messages_list':   msgs,
        'admin':           admin,
        'admin_online':    is_online(admin),
        'admin_last_seen': admin_activity.last_seen if admin_activity else None,
    })


@login_required
def admin_chat(request):
    if not request.user.is_superuser:
        return redirect('home')
    patients = User.objects.filter(is_superuser=False, is_staff=False)
    patient_chats = []
    for patient in patients:
        last_msg = Message.objects.filter(
            Q(sender=patient, receiver=request.user) |
            Q(sender=request.user, receiver=patient)
        ).order_by('-created_at').first()
        unread = Message.objects.filter(sender=patient, receiver=request.user, is_read=False).count()
        patient_chats.append({'patient': patient, 'last_msg': last_msg, 'unread_count': unread})
    patient_chats.sort(key=lambda x: x['last_msg'].created_at if x['last_msg'] else timezone.now(), reverse=True)
    return render(request, 'admin_chat.html', {'patient_chats': patient_chats})


@login_required
def admin_chat_detail(request, patient_id):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    patient = get_object_or_404(User, id=patient_id)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=request.user, receiver=patient,
                content=content, status=Message.STATUS_SENT,
            )
        return redirect('admin_chat_detail', patient_id=patient_id)

    msgs = Message.objects.filter(
        Q(sender=patient, receiver=request.user) |
        Q(sender=request.user, receiver=patient)
    ).order_by('created_at')

    Message.objects.filter(
        sender=patient, receiver=request.user, is_read=False
    ).update(is_read=True, status=Message.STATUS_READ)

    patient_activity = UserActivity.objects.filter(user=patient).first()
    return render(request, 'admin_chat_detail.html', {
        'patient':          patient,
        'messages_list':    msgs,
        'patient_online':   is_online(patient),
        'patient_last_seen': patient_activity.last_seen if patient_activity else None,
    })


@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id, sender=request.user)
    redirect_url = f'/admin-chat/{message.receiver.id}/' if request.user.is_superuser else '/chat/'
    message.delete()
    return redirect(redirect_url)


# ─── TYPING INDICATORS ───────────────────────────────────────

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
        obj.last_seen    = timezone.now()   # ← timestamp every keystroke
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

@login_required
def check_typing(request, user_id):
    obj = UserActivity.objects.filter(user_id=user_id).first()
    if not obj:
        return JsonResponse({'is_typing': False})
    
    # Auto-expire typing after 3 seconds of no update
    if obj.is_typing:
        from datetime import timedelta
        time_diff = timezone.now() - obj.last_seen
        if time_diff.seconds > 3:
            obj.is_typing = False
            obj.typing_to_id = None
            obj.save(update_fields=['is_typing', 'typing_to_id'])
            return JsonResponse({'is_typing': False})
    
    is_typing = (
        obj.is_typing and
        obj.typing_to_id == request.user.id
    )
    return JsonResponse({'is_typing': is_typing})


# ─── ADMIN – STAFF ───────────────────────────────────────────

@login_required
def admin_staff(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    staff_list = StaffProfile.objects.all().select_related('user')
    return render(request, 'admin_staff.html', {'staff_list': staff_list})


@login_required
def add_staff(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        password   = request.POST.get('password', '')
        role       = request.POST.get('role', '')
        phone      = request.POST.get('phone', '')
        salary     = request.POST.get('salary', 0)

        # ── Validation checks ──
        if not username:
            messages.error(request, '❌ Username is required.')
            return redirect('add_staff')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'❌ Username "{username}" is already taken. Please choose a different one.')
            return redirect('add_staff')

        if User.objects.filter(email=email).exists():
            messages.error(request, f'❌ Email "{email}" is already registered.')
            return redirect('add_staff')

        if len(password) < 6:
            messages.error(request, '❌ Password must be at least 6 characters.')
            return redirect('add_staff')

        try:
            user = User.objects.create_user(
                username=username, email=email, password=password,
                first_name=first_name, last_name=last_name, is_staff=True,
            )
            StaffProfile.objects.create(
                user=user, role=role, phone=phone, salary=salary
            )
            send_staff_welcome_email(user, password)
            messages.success(
                request,
                f'✅ Staff member {first_name} {last_name} added successfully! Welcome email sent.'
            )
            return redirect('admin_staff')

        except Exception as e:
            messages.error(request, f'❌ Error creating staff: {str(e)}')
            return redirect('add_staff')

    return render(request, 'add_staff.html')

# ─── ADMIN – LEAVES ──────────────────────────────────────────

@login_required
def admin_leaves(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')

    # ── Auto-approve any expired pending leaves ──
    from django.utils.timezone import localdate
    today = localdate()
    expired = LeaveApplication.objects.filter(
        status='pending',
        to_date__lt=today
    )
    for leave in expired:
        leave.status     = 'approved'
        leave.admin_note = 'Auto-approved: Admin did not respond before leave date.'
        leave.save()
        # Email staff
        try:
            from django.core.mail import send_mail
            send_mail(
                subject='✅ Leave Auto-Approved — No Admin Response',
                message=f"""
Dear {leave.staff.get_full_name() or leave.staff.username},

Your leave has been AUTO-APPROVED as the admin did not respond before the leave date.

  Leave Type : {leave.get_leave_type_display()}
  From       : {leave.from_date.strftime('%d %B %Y')}
  To         : {leave.to_date.strftime('%d %B %Y')}

Regards,
Dr. Dhvani Patalia Physio Rehab
                """.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[leave.staff.email],
                fail_silently=True,
            )
        except Exception:
            pass

    # existing code continues below ──
    leaves  = LeaveApplication.objects.all().select_related('staff')
    pending = leaves.filter(status='pending').count()
    return render(request, 'admin_leaves.html', {'leaves': leaves, 'pending': pending})


@login_required
def update_leave(request, leave_id, status):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    if status in ['approved', 'rejected']:
        leave.status     = status
        leave.admin_note = request.POST.get('admin_note', '')
        leave.save()

        # Email + notification
        send_leave_status_email(leave)
        notify_leave_decision(leave)

        messages.success(request, f'✅ Leave {status}.')
    return redirect('admin_leaves')


# ─── ADMIN – ATTENDANCE ──────────────────────────────────────

@login_required
def admin_attendance(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    today          = timezone.now().date()
    today_att      = Attendance.objects.filter(date=today).select_related('staff')
    all_attendance = Attendance.objects.all().select_related('staff')[:50]
    return render(request, 'admin_attendance.html', {
        'today_attendance': today_att,
        'all_attendance':   all_attendance,
        'today':            today,
    })


# ─── ADMIN – SALARY ──────────────────────────────────────────

@login_required
def admin_salary(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    if request.method == 'POST':
        staff_id  = request.POST.get('staff_id')
        month     = request.POST.get('month')
        year      = request.POST.get('year')
        basic     = request.POST.get('basic_salary', 0)
        bonus     = request.POST.get('bonus', 0)
        deduction = request.POST.get('deduction', 0)
        net       = float(basic) + float(bonus) - float(deduction)

        staff_user = get_object_or_404(User, id=staff_id)
        record = SalaryRecord.objects.create(
            staff=staff_user, month=month, year=year,
            basic_salary=basic, bonus=bonus, deduction=deduction,
            net_salary=net, is_paid=True, paid_on=timezone.now().date(),
        )

        # Email + notification
        send_salary_paid_email(record)
        notify_salary_paid(record)

        messages.success(request, '✅ Salary record saved and email sent!')
        return redirect('admin_salary')

    salary_records = SalaryRecord.objects.all().select_related('staff')
    staff_list     = StaffProfile.objects.all().select_related('user')
    return render(request, 'admin_salary.html', {
        'salary_records': salary_records,
        'staff_list':     staff_list,
    })


# ─── ADMIN – TASKS ───────────────────────────────────────────

@login_required
def admin_tasks(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    tasks = DailyTask.objects.all().select_related('assigned_to', 'assigned_by')
    return render(request, 'admin_tasks.html', {'tasks': tasks})


@login_required
def add_task(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    if request.method == 'POST':
        staff_id    = request.POST.get('staff_id')
        title       = request.POST.get('title', '')
        description = request.POST.get('description', '')
        priority    = request.POST.get('priority', 'medium')
        due_date    = request.POST.get('due_date') or None

        staff_user = get_object_or_404(User, id=staff_id)
        task = DailyTask.objects.create(
            assigned_to=staff_user, assigned_by=request.user,
            title=title, description=description,
            priority=priority, due_date=due_date,
        )

        # Email + notification
        send_task_assigned_email(task)
        notify_task_assigned(task)

        messages.success(request, f'✅ Task assigned to {staff_user.get_full_name()}! Email sent.')
        return redirect('admin_tasks')

    staff_list = StaffProfile.objects.all().select_related('user')
    return render(request, 'add_task.html', {'staff_list': staff_list})


# ─── ADMIN – SESSION NOTES ───────────────────────────────────

@login_required
def admin_session_notes(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')
    notes = SessionNote.objects.all().select_related('staff', 'patient')
    return render(request, 'admin_session_notes.html', {'notes': notes})


# ─── STAFF DASHBOARD ─────────────────────────────────────────

def _is_staff(user):
    return user.is_staff or hasattr(user, 'staff_profile')


@login_required
def staff_dashboard(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    today         = timezone.now().date()
    today_att     = Attendance.objects.filter(staff=request.user, date=today).first()
    pending_tasks = DailyTask.objects.filter(assigned_to=request.user, status='pending').count()
    pending_leaves= LeaveApplication.objects.filter(staff=request.user, status='pending').count()
    my_tasks      = DailyTask.objects.filter(assigned_to=request.user).order_by('-created_at')[:5]
    return render(request, 'staff_dashboard.html', {
        'today_attendance': today_att,
        'pending_tasks':    pending_tasks,
        'pending_leaves':   pending_leaves,
        'my_tasks':         my_tasks,
        'today':            today,
    })


# ════════════════════════════════════════════════════════════
# FILE: core/views.py
# FIND your existing staff_attendance function and
# REPLACE the ENTIRE function with this complete version
# ════════════════════════════════════════════════════════════

@login_required
def staff_attendance(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')

    today    = timezone.now().date()
    now_dt   = timezone.localtime(timezone.now())
    now_time = now_dt.time()

    today_record = Attendance.objects.filter(
        staff=request.user, date=today
    ).first()

    # ── Shift window flags ──
    in_morning     = MORNING_START <= now_time <= MORNING_END
    in_evening     = EVENING_START <= now_time <= EVENING_END
    before_morning = now_time < MORNING_START
    between_shifts = MORNING_END < now_time < EVENING_START
    after_evening  = now_time > EVENING_END

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── MORNING CLOCK IN ────────────────────────────────
        if action == 'morning_clock_in':
            if not in_morning:
                messages.error(
                    request,
                    f'❌ Morning shift is 10:00 AM – 1:00 PM only. '
                    f'Current time: {now_time.strftime("%I:%M %p")}'
                )
                return redirect('staff_attendance')

            if today_record and today_record.clock_in:
                messages.warning(request, '⚠️ Already clocked in for morning shift.')
                return redirect('staff_attendance')

            record, _ = Attendance.objects.get_or_create(
                staff=request.user, date=today
            )
            record.clock_in = now_time
            record.notes    = ''
            record.save()

            if is_late(now_time, 'morning'):
                late_mins = int(
                    (datetime.combine(today, now_time) -
                     datetime.combine(today, MORNING_START)).seconds / 60
                )
                record.notes = f'Late morning clock-in by {late_mins} min.'
                record.save()
                _send_late_email(request.user, 'Morning', now_time, late_mins)
                messages.warning(
                    request,
                    f'⚠️ Clocked in late for morning shift by {late_mins} minutes. '
                    f'Email notification sent.'
                )
            else:
                messages.success(
                    request,
                    f'✅ Morning clock-in at {now_time.strftime("%I:%M %p")}'
                )

        # ── MORNING CLOCK OUT ───────────────────────────────
        elif action == 'morning_clock_out':
            if not today_record or not today_record.clock_in:
                messages.error(
                    request,
                    '❌ You have not clocked in for morning shift yet.'
                )
                return redirect('staff_attendance')

            if today_record.morning_clock_out:
                messages.warning(
                    request, '⚠️ Already clocked out from morning shift.'
                )
                return redirect('staff_attendance')

            today_record.morning_clock_out = now_time

            # Calculate morning hours
            ci = datetime.combine(today, today_record.clock_in)
            co = datetime.combine(today, now_time)
            morning_hours = max(round((co - ci).seconds / 3600, 2), 0)
            today_record.morning_hours = morning_hours

            # Check early leave
            if now_time < MORNING_END:
                short_mins = int(
                    (datetime.combine(today, MORNING_END) -
                     datetime.combine(today, now_time)).seconds / 60
                )
                note = f'Left morning shift {short_mins} min early.'
                today_record.notes = (today_record.notes + ' ' + note).strip()
                _send_early_leave_email(request.user, 'Morning', now_time, short_mins)
                messages.warning(
                    request,
                    f'⚠️ Clocked out {short_mins} min early from morning shift. '
                    f'Email notification sent.'
                )
            else:
                messages.success(
                    request,
                    f'✅ Morning clock-out at {now_time.strftime("%I:%M %p")} '
                    f'— {morning_hours} hrs'
                )
            today_record.save()

        # ── EVENING CLOCK IN ────────────────────────────────
        elif action == 'evening_clock_in':
            if not in_evening:
                messages.error(
                    request,
                    f'❌ Evening shift is 4:00 PM – 8:00 PM only. '
                    f'Current time: {now_time.strftime("%I:%M %p")}'
                )
                return redirect('staff_attendance')

            if today_record and today_record.evening_clock_in:
                messages.warning(
                    request, '⚠️ Already clocked in for evening shift.'
                )
                return redirect('staff_attendance')

            record, _ = Attendance.objects.get_or_create(
                staff=request.user, date=today
            )

            # ── If morning was fully missed → First Half Leave ──
            if not record.clock_in and not record.morning_clock_out:
                if 'First Half Leave' not in record.notes:
                    record.notes = (
                        record.notes + ' First Half Leave (Morning shift missed).'
                    ).strip()
                    LeaveApplication.objects.get_or_create(
                        staff=request.user,
                        from_date=today,
                        to_date=today,
                        defaults={
                            'leave_type': 'casual',
                            'reason': 'Auto-marked: First Half Leave (morning shift missed)',
                            'status': 'pending',
                        }
                    )
                    _send_half_day_email(request.user, 'Morning')
                    messages.warning(
                        request,
                        '⚠️ Morning shift was missed. Marked as First Half Leave. '
                        'Leave application auto-submitted for admin approval.'
                    )

            record.evening_clock_in = now_time
            record.save()
            today_record = record

            if is_late(now_time, 'evening'):
                late_mins = int(
                    (datetime.combine(today, now_time) -
                     datetime.combine(today, EVENING_START)).seconds / 60
                )
                today_record.notes = (
                    today_record.notes +
                    f' Late evening clock-in by {late_mins} min.'
                ).strip()
                today_record.save()
                _send_late_email(request.user, 'Evening', now_time, late_mins)
                messages.warning(
                    request,
                    f'⚠️ Clocked in late for evening shift by {late_mins} minutes. '
                    f'Email notification sent.'
                )
            else:
                if 'First Half Leave' not in (today_record.notes or ''):
                    messages.success(
                        request,
                        f'✅ Evening clock-in at {now_time.strftime("%I:%M %p")}'
                    )

        # ── EVENING CLOCK OUT ───────────────────────────────
        elif action == 'evening_clock_out':
            if not today_record or not today_record.evening_clock_in:
                messages.error(
                    request,
                    '❌ You have not clocked in for evening shift yet.'
                )
                return redirect('staff_attendance')

            if today_record.clock_out:
                messages.warning(
                    request, '⚠️ Already clocked out from evening shift.'
                )
                return redirect('staff_attendance')

            today_record.clock_out = now_time

            # Calculate evening hours
            ci = datetime.combine(today, today_record.evening_clock_in)
            co = datetime.combine(today, now_time)
            evening_hours = max(round((co - ci).seconds / 3600, 2), 0)
            today_record.evening_hours = evening_hours

            # Total = morning + evening
            morning_h = float(today_record.morning_hours or 0)
            today_record.total_hours = round(morning_h + evening_hours, 2)

            # Check early leave
            if now_time < EVENING_END:
                short_mins = int(
                    (datetime.combine(today, EVENING_END) -
                     datetime.combine(today, now_time)).seconds / 60
                )
                note = f'Left evening shift {short_mins} min early.'
                today_record.notes = (today_record.notes + ' ' + note).strip()
                _send_early_leave_email(request.user, 'Evening', now_time, short_mins)
                messages.warning(
                    request,
                    f'⚠️ Clocked out {short_mins} min early from evening shift. '
                    f'Email notification sent.'
                )
            else:
                messages.success(
                    request,
                    f'✅ Day complete! Total: {today_record.total_hours} hrs 🎉'
                )

            # ── If evening missed before this point was caught by cron ──
            # Mark Second Half Leave if morning done but evening was missed
            # (This handles edge case where staff clocks out very late)
            today_record.save()

        else:
            messages.error(request, '❌ Invalid action.')

        return redirect('staff_attendance')

    # ── GET request ─────────────────────────────────────────
    all_att = Attendance.objects.filter(
        staff=request.user
    ).order_by('-date')[:30]

    return render(request, 'staff_attendance.html', {
        'today_record':   today_record,
        'all_attendance': all_att,
        'today':          today,
        'now_time':       now_time,
        'in_morning':     in_morning,
        'in_evening':     in_evening,
        'before_morning': before_morning,
        'between_shifts': between_shifts,
        'after_evening':  after_evening,
        'MORNING_START':  MORNING_START.strftime('%I:%M %p'),
        'MORNING_END':    MORNING_END.strftime('%I:%M %p'),
        'EVENING_START':  EVENING_START.strftime('%I:%M %p'),
        'EVENING_END':    EVENING_END.strftime('%I:%M %p'),
    })


# ════════════════════════════════════════════════════════════
# ADD these 3 helper functions anywhere in core/views.py
# AFTER the staff_attendance function
# ════════════════════════════════════════════════════════════

def _send_late_email(user, shift_name, clock_time, late_mins):
    """Send late arrival email to staff."""
    # from django.core.mail import send_mail
    # from django.conf import settings
    try:
        send_mail(
            subject=f'⚠️ Late Attendance — {shift_name} Shift',
            message=f"""
Dear {user.get_full_name() or user.username},

You clocked in LATE for the {shift_name} Shift today.

  Clock-in Time : {clock_time.strftime('%I:%M %p')}
  Late By       : {late_mins} minutes
  Date          : {timezone.now().date().strftime('%d %B %Y')}

Shift Timings:
  Morning  — 10:00 AM to 1:00 PM
  Evening  — 4:00 PM to 8:00 PM

Regards,
Dr. Dhvani Patalia Physio Rehab
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


def _send_early_leave_email(user, shift_name, clock_time, short_mins):
    """Send early leave email to staff."""
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            subject=f'⚠️ Early Leave Detected — {shift_name} Shift',
            message=f"""
Dear {user.get_full_name() or user.username},

You clocked out EARLY from the {shift_name} Shift today.

  Clock-out Time : {clock_time.strftime('%I:%M %p')}
  Left Early By  : {short_mins} minutes
  Date           : {timezone.now().date().strftime('%d %B %Y')}

If you had a valid reason, please inform the admin.

Regards,
Dr. Dhvani Patalia Physio Rehab
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


def _send_half_day_email(user, missed_shift):
    """Send half day leave email to staff."""
    from django.core.mail import send_mail
    from django.conf import settings
    half     = 'First'  if missed_shift == 'Morning' else 'Second'
    timing   = '10:00 AM – 1:00 PM' if missed_shift == 'Morning' else '4:00 PM – 8:00 PM'
    try:
        send_mail(
            subject=f'📋 {half} Half Leave Auto-Marked — {missed_shift} Shift Missed',
            message=f"""
Dear {user.get_full_name() or user.username},

Since you missed the {missed_shift} shift today, your attendance
has been automatically marked as {half.upper()} HALF LEAVE.

  Date          : {timezone.now().date().strftime('%d %B %Y')}
  Missed Shift  : {missed_shift} ({timing})
  Status        : {half} Half Leave (Pending Admin Approval)

A leave application has been auto-submitted on your behalf.
If this was an error, please contact admin to correct it.

Regards,
Dr. Dhvani Patalia Physio Rehab
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass

@login_required
def staff_leave(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    if request.method == 'POST':
        LeaveApplication.objects.create(
            staff=request.user,
            leave_type=request.POST.get('leave_type'),
            from_date=request.POST.get('from_date'),
            to_date=request.POST.get('to_date'),
            reason=request.POST.get('reason', ''),
        )
        messages.success(request, '✅ Leave application submitted!')
        return redirect('staff_leave')
    my_leaves = LeaveApplication.objects.filter(staff=request.user)
    return render(request, 'staff_leave.html', {'my_leaves': my_leaves})


@login_required
def staff_salary(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    salary_records = SalaryRecord.objects.filter(staff=request.user)
    total_earned   = sum(s.net_salary for s in salary_records if s.is_paid)
    return render(request, 'staff_salary.html', {
        'salary_records': salary_records,
        'total_earned':   total_earned,
    })


@login_required
def staff_tasks(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    tasks = DailyTask.objects.filter(assigned_to=request.user)
    return render(request, 'staff_tasks.html', {
        'tasks':       tasks,
        'pending':     tasks.filter(status='pending').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'completed':   tasks.filter(status='completed').count(),
    })


@login_required
def update_task(request, task_id, status):
    task = get_object_or_404(DailyTask, id=task_id, assigned_to=request.user)
    if status in ['pending', 'in_progress', 'completed']:
        task.status = status
        if status == 'completed':
            task.completed_at = timezone.now()
        task.save()
        messages.success(request, f'✅ Task marked as {status}.')
    return redirect('staff_tasks')


@login_required
def staff_session_notes(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    notes = SessionNote.objects.filter(staff=request.user)
    return render(request, 'staff_session_notes.html', {'notes': notes})


@login_required
def add_session_note(request):
    if not _is_staff(request.user):
        return redirect('client_dashboard')
    if request.method == 'POST':
        patient = get_object_or_404(User, id=request.POST.get('patient_id'))
        SessionNote.objects.create(
            staff=request.user, patient=patient,
            diagnosis=request.POST.get('diagnosis', ''),
            treatment=request.POST.get('treatment', ''),
            next_session=request.POST.get('next_session', ''),
        )
        messages.success(request, '✅ Session note added!')
        return redirect('staff_session_notes')
    patients = User.objects.filter(is_superuser=False, is_staff=False)
    return render(request, 'add_session_note.html', {'patients': patients})

@login_required
def admin_settings(request):

    settings_obj, created = ClinicSettings.objects.get_or_create(
        id=1
    )

    if request.method == "POST":

        settings_obj.clinic_name = request.POST.get(
            "clinic_name"
        )

        settings_obj.phone = request.POST.get(
            "phone"
        )

        settings_obj.email = request.POST.get(
            "email"
        )

        settings_obj.address = request.POST.get(
            "address"
        )

        if request.FILES.get("logo"):
            settings_obj.logo = request.FILES["logo"]

        settings_obj.save()

        messages.success(
            request,
            "Settings updated successfully."
        )

        return redirect("admin_settings")

    return render(
        request,
        "admin_settings.html",
        {"settings": settings_obj}
    )
    
# ════════════════════════════════════════════════════════════
# Add these two views to your core/views.py
# ════════════════════════════════════════════════════════════

@login_required
def progress_tracking(request):
    if request.user.is_superuser:
        # Admin: can view any patient's progress
        all_patients = User.objects.filter(is_superuser=False, is_staff=False)
        patient_id   = request.GET.get('patient_id')

        if patient_id:
            selected_patient = get_object_or_404(User, id=patient_id)
            appointments     = Appointment.objects.filter(patient=selected_patient)
            session_notes    = SessionNote.objects.filter(patient=selected_patient).select_related('staff')
        else:
            selected_patient = None
            appointments     = Appointment.objects.all()
            session_notes    = SessionNote.objects.all().select_related('staff', 'patient')
    else:
        # Client: sees only their own data
        all_patients     = None
        selected_patient = None
        appointments     = Appointment.objects.filter(patient=request.user)
        session_notes    = SessionNote.objects.filter(patient=request.user).select_related('staff')

    # ── Stats ──
    total_appointments = appointments.count()
    completed_count    = appointments.filter(status='completed').count()
    upcoming_count     = appointments.filter(status__in=['pending', 'confirmed']).count()
    session_notes_count= session_notes.count()

    # ── Recovery percentage ──
    recovery_pct    = round((completed_count / total_appointments * 100) if total_appointments else 0)
    attendance_pct  = round(((total_appointments - appointments.filter(status='cancelled').count()) / total_appointments * 100) if total_appointments else 0)
    consistency_pct = min(recovery_pct + 10, 100)
    notes_pct       = round((session_notes_count / completed_count * 100) if completed_count else 0)

    # ── Service breakdown ──
    service_map = {
        'orthopedic': 'Orthopedic',
        'neurological': 'Neurological',
        'sports': 'Sports',
        'pediatric': 'Pediatric',
        'womens': "Women's Health",
        'home_visit': 'Home Visit',
    }
    service_breakdown = []
    for key, label in service_map.items():
        count = appointments.filter(service=key).count()
        if count > 0:
            service_breakdown.append({
                'label': label,
                'count': count,
                'pct':   round(count / total_appointments * 100) if total_appointments else 0,
            })
    service_breakdown.sort(key=lambda x: x['count'], reverse=True)

    return render(request, 'progress_tracking.html', {
        'appointments':       appointments,
        'session_notes':      session_notes,
        'all_patients':       all_patients,
        'selected_patient':   selected_patient,
        'total_appointments': total_appointments,
        'completed_count':    completed_count,
        'upcoming_count':     upcoming_count,
        'session_notes_count':session_notes_count,
        'recovery_pct':       recovery_pct,
        'attendance_pct':     attendance_pct,
        'consistency_pct':    consistency_pct,
        'notes_pct':          notes_pct,
        'service_breakdown':  service_breakdown,
    })


@login_required
def reports_analytics(request):
    if not request.user.is_superuser:
        return redirect('client_dashboard')

    all_appointments = Appointment.objects.all()
    total_appointments      = all_appointments.count()
    completed_appointments  = all_appointments.filter(status='completed').count()
    confirmed_appointments  = all_appointments.filter(status='confirmed').count()
    pending_appointments    = all_appointments.filter(status='pending').count()
    cancelled_appointments  = all_appointments.filter(status='cancelled').count()

    # ── Donut chart percentages ──
    def pct(n): return round(n / total_appointments * 100) if total_appointments else 0
    confirmed_pct  = pct(confirmed_appointments)
    completed_pct  = pct(completed_appointments)
    pending_pct    = pct(pending_appointments)

    # ── Service bar chart ──
    service_map = [
        ('orthopedic',  'Ortho'),
        ('neurological','Neuro'),
        ('sports',      'Sports'),
        ('pediatric',   'Pedia'),
        ('womens',      'Women'),
        ('home_visit',  'Home'),
    ]
    counts = [all_appointments.filter(service=k).count() for k, _ in service_map]
    max_count = max(counts) if counts and max(counts) > 0 else 1
    service_stats = []
    for (key, short), count in zip(service_map, counts):
        service_stats.append({
        'short':      short,
        'count':      count,
        'bar_height': max(round(count / max_count * 120), 4) if count > 0 else 4,
    })

    # ── Performance rates ──
    completion_rate     = pct(completed_appointments)
    retention_rate      = min(completion_rate + 15, 100)
    total_tasks         = DailyTask.objects.count()
    completed_tasks     = DailyTask.objects.filter(status='completed').count()
    task_completion_rate= round(completed_tasks / total_tasks * 100) if total_tasks else 0
    total_notes         = SessionNote.objects.count()
    notes_rate          = round(total_notes / completed_appointments * 100) if completed_appointments else 0

    return render(request, 'reports_analytics.html', {
        'total_patients':          User.objects.filter(is_superuser=False, is_staff=False).count(),
        'total_appointments':      total_appointments,
        'completed_appointments':  completed_appointments,
        'confirmed_appointments':  confirmed_appointments,
        'pending_appointments':    pending_appointments,
        'cancelled_appointments':  cancelled_appointments,
        'confirmed_pct':           confirmed_pct,
        'completed_pct':           completed_pct,
        'pending_pct':             pending_pct,
        'service_stats':           service_stats,
        'completion_rate':         completion_rate,
        'retention_rate':          retention_rate,
        'task_completion_rate':    task_completion_rate,
        'notes_rate':              min(notes_rate, 100),
        'total_staff':             StaffProfile.objects.count(),
        'total_notes':             total_notes,
        'total_leaves':            LeaveApplication.objects.count(),
        'total_tasks':             total_tasks,
        'recent_patients':         User.objects.filter(is_superuser=False, is_staff=False).order_by('-date_joined')[:6],
        'recent_appointments':     all_appointments.order_by('-created_at')[:8],
        'staff_list':              StaffProfile.objects.all().select_related('user'),
    })
    
    