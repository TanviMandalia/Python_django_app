from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Appointment
from django.utils import timezone
from .models import Appointment, Message

def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('/admin-dashboard')
            else:
                return redirect('/client-dashboard')
        else:
            messages.error(request, 'Invalid username or password!')
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        if password != confirm_password:
            messages.error(request, 'Passwords do not match!')
            return redirect('/register')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken!')
            return redirect('/register')
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name
        )
        user.save()
        messages.success(request, 'Account created! Please login.')
        return redirect('/login')
    return render(request, 'register.html')

def logout_view(request):
    logout(request)
    return redirect('/')

@login_required(login_url='/login')
def client_dashboard(request):
    appointments = Appointment.objects.filter(patient=request.user)
    upcoming = appointments.filter(status__in=['pending','confirmed'])
    completed = appointments.filter(status='completed')
    return render(request, 'client_dashboard.html', {
        'user': request.user,
        'appointments': appointments,
        'upcoming': upcoming,
        'completed': completed,
        'total': appointments.count(),
        'upcoming_count': upcoming.count(),
        'completed_count': completed.count(),
    })

@login_required(login_url='/login')
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    total_users = User.objects.filter(is_superuser=False).count()
    all_appointments = Appointment.objects.all()
    pending = all_appointments.filter(status='pending').count()
    return render(request, 'admin_dashboard.html', {
        'user': request.user,
        'total_users': total_users,
        'all_appointments': all_appointments,
        'total_appointments': all_appointments.count(),
        'pending': pending,
    })

@login_required(login_url='/login')
def book_appointment(request):
    if request.method == 'POST':
        service = request.POST['service']
        date = request.POST['date']
        time = request.POST['time']
        notes = request.POST.get('notes', '')
        Appointment.objects.create(
            patient=request.user,
            service=service,
            date=date,
            time=time,
            notes=notes,
            status='pending'
        )
        messages.success(request, '✅ Appointment booked successfully! We will confirm shortly.')
        return redirect('/my-appointments')
    return render(request, 'book_appointment.html')

@login_required(login_url='/login')
def my_appointments(request):
    appointments = Appointment.objects.filter(patient=request.user)
    return render(request, 'my_appointments.html', {
        'appointments': appointments,
        'user': request.user,
    })


@login_required(login_url='/login')
def admin_appointments(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    all_appointments = Appointment.objects.all().order_by('-created_at')
    pending = all_appointments.filter(status='pending')
    confirmed = all_appointments.filter(status='confirmed')
    completed = all_appointments.filter(status='completed')
    cancelled = all_appointments.filter(status='cancelled')
    return render(request, 'admin_appointments.html', {
        'user': request.user,
        'all_appointments': all_appointments,
        'pending_count': pending.count(),
        'confirmed_count': confirmed.count(),
        'completed_count': completed.count(),
        'cancelled_count': cancelled.count(),
    })

@login_required(login_url='/login')
def update_appointment(request, appt_id, status):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    try:
        appt = Appointment.objects.get(id=appt_id)
        appt.status = status
        appt.save()
        messages.success(request, f'Appointment status updated to {status}!')
    except Appointment.DoesNotExist:
        messages.error(request, 'Appointment not found!')
    return redirect('/admin-appointments')

@login_required(login_url='/login')
def admin_patients(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    patients = User.objects.filter(is_superuser=False).order_by('-date_joined')
    return render(request, 'admin_patients.html', {
        'user': request.user,
        'patients': patients,
    })


@login_required(login_url='/login')
def client_chat(request):
    admin = User.objects.filter(is_superuser=True).first()
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content and admin:
            Message.objects.create(
                sender=request.user,
                receiver=admin,
                content=content
            )
        return redirect('/chat')
    messages_list = Message.objects.filter(
        sender=request.user, receiver=admin
    ) | Message.objects.filter(
        sender=admin, receiver=request.user
    )
    messages_list = messages_list.order_by('created_at')
    # Mark admin messages as read
    messages_list.filter(sender=admin, is_read=False).update(is_read=True)
    return render(request, 'client_chat.html', {
        'user': request.user,
        'messages_list': messages_list,
        'admin': admin,
    })

@login_required(login_url='/login')
def admin_chat(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    patients = User.objects.filter(is_superuser=False)
    patient_chats = []
    for patient in patients:
        last_msg = Message.objects.filter(
            sender=patient, receiver=request.user
        ).order_by('-created_at').first()
        unread = Message.objects.filter(
            sender=patient, receiver=request.user, is_read=False
        ).count()
        patient_chats.append({
            'patient': patient,
            'last_msg': last_msg,
            'unread': unread,
        })
    return render(request, 'admin_chat.html', {
        'user': request.user,
        'patient_chats': patient_chats,
    })

@login_required(login_url='/login')
def admin_chat_detail(request, patient_id):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    patient = User.objects.get(id=patient_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=patient,
                content=content
            )
        return redirect(f'/admin-chat/{patient_id}')
    messages_list = Message.objects.filter(
        sender=patient, receiver=request.user
    ) | Message.objects.filter(
        sender=request.user, receiver=patient
    )
    messages_list = messages_list.order_by('created_at')
    messages_list.filter(sender=patient, is_read=False).update(is_read=True)
    return render(request, 'admin_chat_detail.html', {
        'user': request.user,
        'patient': patient,
        'messages_list': messages_list,
    })