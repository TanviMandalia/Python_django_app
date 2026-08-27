from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from core.decorators import admin_required
from core.models import (
    Appointment, StaffProfile, Attendance, LeaveApplication, SalaryRecord,
    DailyTask, SessionNote, ClinicSettings, ClinicPromo, Review, Blog,
    SupportTicket, Profile, PaymentRecord
)
from core.services.appointment_service import AppointmentService
from core.forms.clinic_forms import ClinicSettingsForm, PromoForm, ReviewForm, BlogForm
from core.forms.appointment_forms import AppointmentBookingForm, AppointmentUpdateForm
from core.forms.staff_forms import StaffProfileForm, AttendanceForm, SalaryRecordForm, DailyTaskForm
from core.forms.medical_forms import SessionNoteForm


@admin_required
def admin_dashboard(request):
    today = timezone.now().date()

    # Core Stats
    total_appointments = Appointment.objects.count()
    today_appointments = Appointment.objects.filter(date=today).order_by('time')
    pending_appointments = Appointment.objects.filter(status='pending').count()
    total_patients = User.objects.filter(is_staff=False, is_superuser=False).count()
    total_staff = StaffProfile.objects.filter(is_active=True).count()
    pending_leaves = LeaveApplication.objects.filter(status='pending').count()

    # Financial Stats
    revenue_data = PaymentRecord.objects.filter(status='paid').aggregate(total=Sum('amount'))
    total_revenue = revenue_data['total'] or 0

    # Recent items
    recent_appointments = Appointment.objects.order_by('-created_at')[:8]
    recent_reviews = Review.objects.order_by('-created_at')[:5]

    context = {
        'total_appointments': total_appointments,
        'today_appointments': today_appointments,
        'pending_appointments': pending_appointments,
        'total_patients': total_patients,
        'total_staff': total_staff,
        'pending_leaves': pending_leaves,
        'total_revenue': total_revenue,
        'recent_appointments': recent_appointments,
        'recent_reviews': recent_reviews,
    }
    return render(request, "admin_dashboard.html", context)


# ─── APPOINTMENTS MANAGEMENT ──────────────────────────────────────────

@admin_required
def admin_appointments(request):
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    appointments = Appointment.objects.order_by('-date', '-time')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if search_query:
        appointments = appointments.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    return render(request, "admin_appointments.html", {
        "appointments": appointments,
        "status_filter": status_filter,
        "search_query": search_query,
    })


@admin_required
def update_appointment(request, appt_id, status):
    appt = get_object_or_404(Appointment, id=appt_id)
    if status in ['pending', 'confirmed', 'completed', 'cancelled']:
        AppointmentService.update_status(appt, status)
        messages.success(request, f"Appointment #{appt.id} marked as {status.title()}.")
    return redirect("admin_appointments")


@admin_required
def add_appointment(request):
    if request.method == "POST":
        form = AppointmentBookingForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.status = 'confirmed'
            appointment.save()
            messages.success(request, f"Appointment added for {appointment.name}.")
            return redirect("admin_appointments")
    else:
        form = AppointmentBookingForm()
    return render(request, "add_appointment.html", {"form": form})


@admin_required
def edit_appointment(request, appt_id):
    appt = get_object_or_404(Appointment, id=appt_id)
    if request.method == "POST":
        form = AppointmentUpdateForm(request.POST, instance=appt)
        if form.is_valid():
            form.save()
            messages.success(request, f"Appointment #{appt.id} updated.")
            return redirect("admin_appointments")
    else:
        form = AppointmentUpdateForm(instance=appt)
    return render(request, "edit_appointment.html", {"form": form, "appointment": appt})


@admin_required
def delete_appointment(request, appt_id):
    appt = get_object_or_404(Appointment, id=appt_id)
    appt.delete()
    messages.info(request, "Appointment deleted.")
    return redirect("admin_appointments")


# ─── PATIENTS MANAGEMENT ──────────────────────────────────────────────

@admin_required
def admin_patients(request):
    search = request.GET.get('search', '')
    patients = User.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')
    if search:
        patients = patients.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    return render(request, "admin_patients.html", {"patients": patients, "search": search})


@admin_required
def edit_patient(request, user_id):
    patient_user = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=patient_user)

    if request.method == "POST":
        patient_user.first_name = request.POST.get('first_name', patient_user.first_name)
        patient_user.last_name = request.POST.get('last_name', patient_user.last_name)
        patient_user.email = request.POST.get('email', patient_user.email)
        patient_user.save()

        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.gender = request.POST.get('gender', profile.gender)
        profile.blood_group = request.POST.get('blood_group', profile.blood_group)
        profile.emergency_contact = request.POST.get('emergency_contact', profile.emergency_contact)
        profile.medical_notes = request.POST.get('medical_notes', profile.medical_notes)
        profile.address = request.POST.get('address', profile.address)
        profile.save()

        messages.success(request, f"Patient profile for {patient_user.username} updated.")
        return redirect("admin_patients")

    return render(request, "edit_patient.html", {"patient_user": patient_user, "profile": profile})


@admin_required
def delete_patient(request, user_id):
    patient_user = get_object_or_404(User, id=user_id)
    patient_user.is_active = False
    patient_user.save()
    messages.info(request, f"Patient {patient_user.username} deactivated.")
    return redirect("admin_patients")


@admin_required
def reactivate_patient(request, user_id):
    patient_user = get_object_or_404(User, id=user_id)
    patient_user.is_active = True
    patient_user.save()
    messages.success(request, f"Patient {patient_user.username} reactivated.")
    return redirect("admin_patients")


# ─── STAFF MANAGEMENT ─────────────────────────────────────────────────

@admin_required
def admin_staff(request):
    staff_members = StaffProfile.objects.all().order_by('-joining_date')
    return render(request, "admin_staff.html", {"staff_members": staff_members})


@admin_required
def add_staff(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role', 'physiotherapist')
        phone = request.POST.get('phone', '')
        salary = request.POST.get('salary', 0)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password,
                first_name=first_name, last_name=last_name, is_staff=True
            )
            StaffProfile.objects.create(
                user=user, role=role, phone=phone, salary=salary, is_active=True
            )
            messages.success(request, f"Staff member {user.get_full_name() or user.username} registered.")
            return redirect("admin_staff")
    return render(request, "add_staff.html")


@admin_required
def edit_staff(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    if request.method == "POST":
        form = StaffProfileForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, f"Staff profile updated.")
            return redirect("admin_staff")
    else:
        form = StaffProfileForm(instance=staff)
    return render(request, "edit_staff.html", {"form": form, "staff": staff})


@admin_required
def delete_staff(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    staff.is_active = False
    staff.save()
    messages.info(request, "Staff member deactivated.")
    return redirect("admin_staff")


# ─── LEAVES & ATTENDANCE ──────────────────────────────────────────────

@admin_required
def admin_leaves(request):
    leaves = LeaveApplication.objects.all().order_by('-applied_on')
    return render(request, "admin_leaves.html", {"leaves": leaves})


@admin_required
def update_leave(request, leave_id, status):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    if status in ['approved', 'rejected', 'pending']:
        leave.status = status
        leave.save()
        messages.success(request, f"Leave application marked as {status.title()}.")
    return redirect("admin_leaves")


@admin_required
def delete_leave(request, leave_id):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    leave.delete()
    messages.info(request, "Leave record deleted.")
    return redirect("admin_leaves")


@admin_required
def admin_attendance(request):
    date_filter = request.GET.get('date', timezone.now().date().isoformat())
    attendances = Attendance.objects.filter(date=date_filter).order_by('staff__username')
    return render(request, "admin_attendance.html", {
        "attendances": attendances,
        "date_filter": date_filter
    })


@admin_required
def add_attendance(request):
    if request.method == "POST":
        form = AttendanceForm(request.POST)
        if form.is_valid():
            att = form.save()
            messages.success(request, "Attendance record created.")
            return redirect("admin_attendance")
    else:
        form = AttendanceForm(initial={'date': timezone.now().date()})
    return render(request, "add_attendance.html", {"form": form})


@admin_required
def edit_attendance(request, att_id):
    att = get_object_or_404(Attendance, id=att_id)
    if request.method == "POST":
        form = AttendanceForm(request.POST, instance=att)
        if form.is_valid():
            form.save()
            messages.success(request, "Attendance record updated.")
            return redirect("admin_attendance")
    else:
        form = AttendanceForm(instance=att)
    return render(request, "edit_attendance.html", {"form": form, "att": att})


@admin_required
def delete_attendance(request, att_id):
    att = get_object_or_404(Attendance, id=att_id)
    att.delete()
    messages.info(request, "Attendance record deleted.")
    return redirect("admin_attendance")


# ─── SALARY MANAGEMENT ────────────────────────────────────────────────

@admin_required
def admin_salary(request):
    salaries = SalaryRecord.objects.all().order_by('-year', '-month')
    return render(request, "admin_salary.html", {"salaries": salaries})


@admin_required
def edit_salary(request, record_id):
    salary = get_object_or_404(SalaryRecord, id=record_id)
    if request.method == "POST":
        form = SalaryRecordForm(request.POST, instance=salary)
        if form.is_valid():
            form.save()
            messages.success(request, "Salary record updated.")
            return redirect("admin_salary")
    else:
        form = SalaryRecordForm(instance=salary)
    return render(request, "edit_salary.html", {"form": form, "salary": salary})


@admin_required
def delete_salary(request, record_id):
    salary = get_object_or_404(SalaryRecord, id=record_id)
    salary.delete()
    messages.info(request, "Salary record deleted.")
    return redirect("admin_salary")


# ─── TASKS MANAGEMENT ─────────────────────────────────────────────────

@admin_required
def admin_tasks(request):
    tasks = DailyTask.objects.all().order_by('-created_at')
    return render(request, "admin_tasks.html", {"tasks": tasks})


@admin_required
def add_task(request):
    if request.method == "POST":
        form = DailyTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.assigned_by = request.user
            task.save()
            messages.success(request, f"Task '{task.title}' assigned.")
            return redirect("admin_tasks")
    else:
        form = DailyTaskForm()
    return render(request, "add_task.html", {"form": form})


@admin_required
def edit_task_admin(request, task_id):
    task = get_object_or_404(DailyTask, id=task_id)
    if request.method == "POST":
        form = DailyTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated.")
            return redirect("admin_tasks")
    else:
        form = DailyTaskForm(instance=task)
    return render(request, "edit_task.html", {"form": form, "task": task})


@admin_required
def delete_task_admin(request, task_id):
    task = get_object_or_404(DailyTask, id=task_id)
    task.delete()
    messages.info(request, "Task deleted.")
    return redirect("admin_tasks")


# ─── CLINIC SETTINGS, PROMOS, REVIEWS, BLOG ───────────────────────────

@admin_required
def admin_settings(request):
    settings_obj = ClinicSettings.objects.first()
    if request.method == "POST":
        form = ClinicSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Clinic settings saved successfully.")
            return redirect("admin_settings")
    else:
        form = ClinicSettingsForm(instance=settings_obj)
    return render(request, "admin_settings.html", {"form": form})


@admin_required
def admin_promos(request):
    promos = ClinicPromo.objects.all().order_by('-created_at')
    return render(request, "admin_promos.html", {"promos": promos})


@admin_required
def admin_promo_add(request):
    if request.method == "POST":
        form = PromoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Promo announcement created.")
            return redirect("admin_promos")
    else:
        form = PromoForm()
    return render(request, "admin_promo_add.html", {"form": form})


@admin_required
def admin_promo_delete(request, promo_id):
    promo = get_object_or_404(ClinicPromo, id=promo_id)
    promo.delete()
    messages.info(request, "Promo deleted.")
    return redirect("admin_promos")


def dismiss_promo(request):
    return JsonResponse({'status': 'dismissed'})


@admin_required
def admin_reviews(request):
    reviews = Review.objects.all().order_by('-created_at')
    return render(request, "admin_reviews.html", {"reviews": reviews})


@admin_required
def admin_add_review(request):
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.is_approved = True
            review.added_by_admin = True
            review.save()
            messages.success(request, "Review published.")
            return redirect("admin_reviews")
    else:
        form = ReviewForm()
    return render(request, "admin_add_review.html", {"form": form})


@admin_required
def toggle_review_approval(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = not review.is_approved
    review.save()
    status = "approved" if review.is_approved else "hidden"
    messages.success(request, f"Review marked as {status}.")
    return redirect("admin_reviews")


@admin_required
def admin_delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    messages.info(request, "Review removed.")
    return redirect("admin_reviews")


# ─── ADMIN BLOG CRUD ──────────────────────────────────────────────────

@admin_required
def admin_blog_list(request):
    blogs = Blog.objects.order_by("-created_at")
    return render(request, "blog_list.html", {"blogs": blogs})


@admin_required
def admin_blog_add(request):
    if request.method == "POST":
        form = BlogForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Blog post published.")
            return redirect("admin_blog_list")
    else:
        form = BlogForm()
    return render(request, "blog_form.html", {"form": form, "categories": Blog.CATEGORY_CHOICES})


@admin_required
def admin_blog_edit(request, id):
    blog = get_object_or_404(Blog, id=id)
    if request.method == "POST":
        form = BlogForm(request.POST, request.FILES, instance=blog)
        if form.is_valid():
            form.save()
            messages.success(request, "Blog post updated.")
            return redirect("admin_blog_list")
    else:
        form = BlogForm(instance=blog)
    return render(request, "blog_form.html", {"form": form, "blog": blog, "categories": Blog.CATEGORY_CHOICES})


@admin_required
def admin_blog_delete(request, id):
    blog = get_object_or_404(Blog, id=id)
    blog.delete()
    messages.info(request, "Blog post deleted.")
    return redirect("admin_blog_list")


# ─── ADMIN SESSION NOTES CRUD ─────────────────────────────────────────

@admin_required
def admin_session_notes(request):
    notes = SessionNote.objects.all().order_by('-date')
    return render(request, "admin_session_notes.html", {"notes": notes})


@admin_required
def admin_add_session_note(request):
    if request.method == "POST":
        form = SessionNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.staff = request.user
            note.save()
            messages.success(request, "Session note recorded.")
            return redirect("admin_session_notes")
    else:
        form = SessionNoteForm()
    return render(request, "admin_add_session_note.html", {"form": form})


# ─── SUPPORT TICKETS ──────────────────────────────────────────────────

@admin_required
def submit_support_ticket(request):
    if request.method == "POST":
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')
        if subject and message:
            SupportTicket.objects.create(
                submitted_by=request.user,
                subject=subject,
                message=message,
                status='open'
            )
            messages.success(request, "Support request sent to platform administration.")
    return redirect("admin_settings")

