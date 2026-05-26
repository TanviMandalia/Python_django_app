from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Appointment
from django.utils import timezone
from .models import Appointment, Message,  StaffProfile, Attendance, LeaveApplication, SalaryRecord, SessionNote, DailyTask
from django.utils.timezone import make_aware
import datetime

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
            elif user.is_staff:
                return redirect('/staff-dashboard')
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
    try:
        admin = User.objects.get(username='admin')
    except User.DoesNotExist:
        admin = User.objects.filter(is_superuser=True).order_by('id').last()

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content and admin:
            Message.objects.create(
                sender=request.user,
                receiver=admin,
                content=content
            )
        return redirect('/chat')

    if admin:
        messages_list = Message.objects.filter(
            sender=request.user, receiver=admin
        ) | Message.objects.filter(
            sender=admin, receiver=request.user
        )
        messages_list = messages_list.order_by('created_at')
        Message.objects.filter(
            sender=admin,
            receiver=request.user,
            is_read=False
        ).update(is_read=True)
    else:
        messages_list = Message.objects.none()

    return render(request, 'client_chat.html', {
        'user': request.user,
        'messages_list': messages_list,
        'admin': admin,
    })


@login_required(login_url='/login')
def admin_chat(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')

    # Only show real patients (non-superusers)
    patients = User.objects.filter(is_superuser=False)
    patient_chats = []

    for patient in patients:
        all_msgs = Message.objects.filter(
            sender=patient, receiver=request.user
        ) | Message.objects.filter(
            sender=request.user, receiver=patient
        )
        last_msg = all_msgs.order_by('-created_at').first()
        unread = Message.objects.filter(
            sender=patient,
            receiver=request.user,
            is_read=False
        ).count()
        patient_chats.append({
            'patient': patient,
            'last_msg': last_msg,
            'unread': unread,
        })

    # Sort — patients with messages appear first
    patient_chats.sort(
        key=lambda x: x['last_msg'].created_at if x['last_msg'] else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
        reverse=True
    )

    return render(request, 'admin_chat.html', {
        'user': request.user,
        'patient_chats': patient_chats,
    })


@login_required(login_url='/login')
def admin_chat_detail(request, patient_id):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')

    try:
        patient = User.objects.get(id=patient_id)
    except User.DoesNotExist:
        return redirect('/admin-chat')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=patient,
                content=content
            )
        return redirect(f'/admin-chat/{patient_id}')

    # Get ALL messages between admin and this patient
    messages_list = Message.objects.filter(
        sender=patient, receiver=request.user
    ) | Message.objects.filter(
        sender=request.user, receiver=patient
    )
    messages_list = messages_list.order_by('created_at')

    # Mark patient messages as read
    Message.objects.filter(
        sender=patient,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)

    return render(request, 'admin_chat_detail.html', {
        'user': request.user,
        'patient': patient,
        'messages_list': messages_list,
    })
    
    
    # ─── ADMIN STAFF VIEWS ───────────────────────────────────────

@login_required(login_url='/login')
def admin_staff(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    staff_list = StaffProfile.objects.all().select_related('user')
    return render(request, 'admin_staff.html', {
        'user': request.user,
        'staff_list': staff_list,
    })


@login_required(login_url='/login')
def add_staff(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        role = request.POST['role']
        phone = request.POST.get('phone', '')
        salary = request.POST.get('salary', 0)

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken!')
            return redirect('/add-staff')

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
            is_staff=True
        )
        StaffProfile.objects.create(
            user=user, role=role, phone=phone, salary=salary
        )
        messages.success(request, f'Staff member {first_name} added successfully!')
        return redirect('/admin-staff')
    return render(request, 'add_staff.html', {'user': request.user})


@login_required(login_url='/login')
def admin_leaves(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    leaves = LeaveApplication.objects.all().select_related('staff')
    pending = leaves.filter(status='pending').count()
    return render(request, 'admin_leaves.html', {
        'user': request.user,
        'leaves': leaves,
        'pending': pending,
    })


@login_required(login_url='/login')
def update_leave(request, leave_id, status):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    try:
        leave = LeaveApplication.objects.get(id=leave_id)
        leave.status = status
        leave.save()
        messages.success(request, f'Leave {status} successfully!')
    except LeaveApplication.DoesNotExist:
        messages.error(request, 'Leave not found!')
    return redirect('/admin-leaves')


@login_required(login_url='/login')
def admin_attendance(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    today = timezone.now().date()
    attendance = Attendance.objects.filter(date=today).select_related('staff')
    all_attendance = Attendance.objects.all().select_related('staff')[:50]
    return render(request, 'admin_attendance.html', {
        'user': request.user,
        'today_attendance': attendance,
        'all_attendance': all_attendance,
        'today': today,
    })


@login_required(login_url='/login')
def admin_salary(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    if request.method == 'POST':
        staff_id = request.POST['staff_id']
        month = request.POST['month']
        year = request.POST['year']
        basic = request.POST['basic_salary']
        bonus = request.POST.get('bonus', 0)
        deduction = request.POST.get('deduction', 0)
        net = float(basic) + float(bonus) - float(deduction)
        staff_user = User.objects.get(id=staff_id)
        SalaryRecord.objects.create(
            staff=staff_user, month=month, year=year,
            basic_salary=basic, bonus=bonus,
            deduction=deduction, net_salary=net,
            is_paid=True, paid_on=timezone.now().date()
        )
        messages.success(request, 'Salary record added!')
        return redirect('/admin-salary')
    salary_records = SalaryRecord.objects.all().select_related('staff')
    staff_list = StaffProfile.objects.all().select_related('user')
    return render(request, 'admin_salary.html', {
        'user': request.user,
        'salary_records': salary_records,
        'staff_list': staff_list,
    })


@login_required(login_url='/login')
def admin_tasks(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    tasks = DailyTask.objects.all().select_related('assigned_to', 'assigned_by')
    return render(request, 'admin_tasks.html', {
        'user': request.user,
        'tasks': tasks,
    })


@login_required(login_url='/login')
def add_task(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    if request.method == 'POST':
        staff_id = request.POST['staff_id']
        title = request.POST['title']
        description = request.POST.get('description', '')
        priority = request.POST['priority']
        due_date = request.POST.get('due_date', None)
        staff_user = User.objects.get(id=staff_id)
        DailyTask.objects.create(
            assigned_to=staff_user,
            assigned_by=request.user,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date if due_date else None
        )
        messages.success(request, f'Task assigned to {staff_user.get_full_name()}!')
        return redirect('/admin-tasks')
    staff_list = StaffProfile.objects.all().select_related('user')
    return render(request, 'add_task.html', {
        'user': request.user,
        'staff_list': staff_list,
    })


@login_required(login_url='/login')
def admin_session_notes(request):
    if not request.user.is_superuser:
        return redirect('/client-dashboard')
    notes = SessionNote.objects.all().select_related('staff', 'patient')
    return render(request, 'admin_session_notes.html', {
        'user': request.user,
        'notes': notes,
    })


# ─── STAFF DASHBOARD VIEWS ───────────────────────────────────

def is_staff_member(user):
    return hasattr(user, 'staff_profile') or user.is_staff

@login_required(login_url='/login')
def staff_dashboard(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    today = timezone.now().date()
    try:
        today_attendance = Attendance.objects.get(staff=request.user, date=today)
    except Attendance.DoesNotExist:
        today_attendance = None
    pending_tasks = DailyTask.objects.filter(assigned_to=request.user, status='pending').count()
    pending_leaves = LeaveApplication.objects.filter(staff=request.user, status='pending').count()
    my_tasks = DailyTask.objects.filter(assigned_to=request.user).order_by('-created_at')[:5]
    return render(request, 'staff_dashboard.html', {
        'user': request.user,
        'today_attendance': today_attendance,
        'pending_tasks': pending_tasks,
        'pending_leaves': pending_leaves,
        'my_tasks': my_tasks,
        'today': today,
    })


@login_required(login_url='/login')
def staff_attendance(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    today = timezone.now().date()
    now_time = timezone.now().time()

    try:
        today_record = Attendance.objects.get(staff=request.user, date=today)
    except Attendance.DoesNotExist:
        today_record = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'clock_in':
            if not today_record:
                Attendance.objects.create(
                    staff=request.user,
                    date=today,
                    clock_in=now_time
                )
                messages.success(request, f'✅ Clocked In at {now_time.strftime("%I:%M %p")}')
            else:
                messages.error(request, 'Already clocked in today!')

        elif action == 'lunch_start' and today_record and not today_record.lunch_start:
            today_record.lunch_start = now_time
            today_record.save()
            messages.success(request, f'🍽️ Lunch started at {now_time.strftime("%I:%M %p")}')

        elif action == 'lunch_end' and today_record and today_record.lunch_start and not today_record.lunch_end:
            today_record.lunch_end = now_time
            today_record.save()
            messages.success(request, f'✅ Lunch ended at {now_time.strftime("%I:%M %p")}')

        elif action == 'clock_out' and today_record and not today_record.clock_out:
            today_record.clock_out = now_time
            # Calculate total hours
            if today_record.clock_in:
                from datetime import datetime, timedelta
                ci = datetime.combine(today, today_record.clock_in)
                co = datetime.combine(today, now_time)
                total = co - ci
                # Subtract lunch
                if today_record.lunch_start and today_record.lunch_end:
                    ls = datetime.combine(today, today_record.lunch_start)
                    le = datetime.combine(today, today_record.lunch_end)
                    total -= (le - ls)
                today_record.total_hours = round(total.seconds / 3600, 2)
            today_record.clock_out = now_time
            today_record.save()
            messages.success(request, f'👋 Clocked Out at {now_time.strftime("%I:%M %p")}. Total: {today_record.total_hours} hrs')

        return redirect('/staff-attendance')

    all_attendance = Attendance.objects.filter(staff=request.user).order_by('-date')[:30]
    return render(request, 'staff_attendance.html', {
        'user': request.user,
        'today_record': today_record,
        'all_attendance': all_attendance,
        'today': today,
    })


@login_required(login_url='/login')
def staff_leave(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    if request.method == 'POST':
        leave_type = request.POST['leave_type']
        from_date = request.POST['from_date']
        to_date = request.POST['to_date']
        reason = request.POST['reason']
        LeaveApplication.objects.create(
            staff=request.user,
            leave_type=leave_type,
            from_date=from_date,
            to_date=to_date,
            reason=reason
        )
        messages.success(request, '✅ Leave application submitted!')
        return redirect('/staff-leave')
    my_leaves = LeaveApplication.objects.filter(staff=request.user)
    return render(request, 'staff_leave.html', {
        'user': request.user,
        'my_leaves': my_leaves,
    })


@login_required(login_url='/login')
def staff_salary(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    salary_records = SalaryRecord.objects.filter(staff=request.user)
    total_earned = sum([s.net_salary for s in salary_records if s.is_paid])
    return render(request, 'staff_salary.html', {
        'user': request.user,
        'salary_records': salary_records,
        'total_earned': total_earned,
    })


@login_required(login_url='/login')
def staff_tasks(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    tasks = DailyTask.objects.filter(assigned_to=request.user)
    pending = tasks.filter(status='pending').count()
    in_progress = tasks.filter(status='in_progress').count()
    completed = tasks.filter(status='completed').count()
    return render(request, 'staff_tasks.html', {
        'user': request.user,
        'tasks': tasks,
        'pending': pending,
        'in_progress': in_progress,
        'completed': completed,
    })


@login_required(login_url='/login')
def update_task(request, task_id, status):
    try:
        task = DailyTask.objects.get(id=task_id, assigned_to=request.user)
        task.status = status
        if status == 'completed':
            task.completed_at = timezone.now()
        task.save()
        messages.success(request, f'Task marked as {status}!')
    except DailyTask.DoesNotExist:
        messages.error(request, 'Task not found!')
    return redirect('/staff-tasks')


@login_required(login_url='/login')
def staff_session_notes(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    notes = SessionNote.objects.filter(staff=request.user)
    return render(request, 'staff_session_notes.html', {
        'user': request.user,
        'notes': notes,
    })


@login_required(login_url='/login')
def add_session_note(request):
    if not (request.user.is_staff or hasattr(request.user, 'staff_profile')):
        return redirect('/client-dashboard')
    if request.method == 'POST':
        patient_id = request.POST['patient_id']
        diagnosis = request.POST['diagnosis']
        treatment = request.POST['treatment']
        next_session = request.POST.get('next_session', '')
        patient = User.objects.get(id=patient_id)
        SessionNote.objects.create(
            staff=request.user,
            patient=patient,
            diagnosis=diagnosis,
            treatment=treatment,
            next_session=next_session
        )
        messages.success(request, '✅ Session note added!')
        return redirect('/staff-session-notes')
    patients = User.objects.filter(is_superuser=False, is_staff=False)
    return render(request, 'add_session_note.html', {
        'user': request.user,
        'patients': patients,
    })
    
# ─── PUBLIC PAGE VIEWS ───────────────────────────────────────

def about(request):
    return render(request, 'about.html')


def services(request):
    return render(request, 'services.html')


def contact(request):
    if request.method == 'POST':
        messages.success(request, '✅ Message sent! We will contact you soon.')
        return redirect('/contact')
    return render(request, 'contact.html')


def blog(request):
    return render(request, 'blog.html')