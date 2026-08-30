from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from core.decorators import staff_required
from core.models import Attendance, LeaveApplication, SalaryRecord, DailyTask, SessionNote
from core.services.attendance_service import AttendanceService
from core.forms.staff_forms import LeaveApplicationForm


@staff_required
def staff_dashboard(request):
    user = request.user
    today = timezone.now().date()

    # Today's attendance record
    today_attendance = Attendance.objects.filter(staff=user, date=today).first()

    # Staff tasks
    pending_tasks = DailyTask.objects.filter(assigned_to=user, status__in=['pending', 'in_progress']).order_by('due_date')
    completed_tasks_count = DailyTask.objects.filter(assigned_to=user, status='completed').count()

    # Recent leave requests
    recent_leaves = LeaveApplication.objects.filter(staff=user).order_by('-applied_on')[:5]

    # Recent salary records
    recent_salaries = SalaryRecord.objects.filter(staff=user).order_by('-year', '-month')[:3]

    context = {
        'today_attendance': today_attendance,
        'pending_tasks': pending_tasks,
        'completed_tasks_count': completed_tasks_count,
        'recent_leaves': recent_leaves,
        'recent_salaries': recent_salaries,
    }
    return render(request, "staff/staff_dashboard.html", context)


@staff_required
def staff_attendance(request):
    user = request.user
    today = timezone.now().date()
    now_time = timezone.localtime().time()

    attendance, created = Attendance.objects.get_or_create(staff=user, date=today)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "morning_clock_in":
            if not attendance.clock_in:
                attendance.clock_in = now_time
                messages.success(request, f"☀️ Morning Shift Clocked-in at {now_time.strftime('%I:%M %p')}")
        elif action == "morning_clock_out":
            if not attendance.morning_clock_out:
                attendance.morning_clock_out = now_time
                messages.success(request, f"🌤️ Morning Shift Clocked-out at {now_time.strftime('%I:%M %p')}")
        elif action == "evening_clock_in":
            if not attendance.evening_clock_in:
                attendance.evening_clock_in = now_time
                messages.success(request, f"🌙 Evening Shift Clocked-in at {now_time.strftime('%I:%M %p')}")
        elif action == "evening_clock_out":
            if not attendance.clock_out:
                attendance.clock_out = now_time
                messages.success(request, f"⭐ Evening Shift Clocked-out at {now_time.strftime('%I:%M %p')}")

        # Recalculate hours
        AttendanceService.process_shift_record(attendance)
        return redirect("staff_attendance")

    history = Attendance.objects.filter(staff=user).order_by('-date')[:30]
    return render(request, "staff/staff_attendance.html", {
        "today_attendance": attendance,
        "history": history,
    })


@staff_required
def staff_leave(request):
    user = request.user
    if request.method == "POST":
        form = LeaveApplicationForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.staff = user
            leave.status = 'pending'
            leave.save()
            messages.success(request, "📋 Leave application submitted successfully.")
            return redirect("staff_leave")
    else:
        form = LeaveApplicationForm()

    leaves = LeaveApplication.objects.filter(staff=user).order_by('-applied_on')
    return render(request, "staff/staff_leave.html", {"form": form, "leaves": leaves})


@staff_required
def staff_salary(request):
    salaries = SalaryRecord.objects.filter(staff=request.user).order_by('-year', '-month')
    return render(request, "staff/staff_salary.html", {"salaries": salaries})


@staff_required
def staff_tasks(request):
    tasks = DailyTask.objects.filter(assigned_to=request.user).order_by('-created_at')
    return render(request, "staff/staff_tasks.html", {"tasks": tasks})


@staff_required
def update_task(request, task_id, status):
    task = get_object_or_404(DailyTask, id=task_id, assigned_to=request.user)
    if status in ['pending', 'in_progress', 'completed']:
        task.status = status
        if status == 'completed':
            task.completed_at = timezone.now()
        task.save()
        messages.success(request, f"Task marked as {status.replace('_', ' ').title()}.")
    return redirect("staff_tasks")


@staff_required
def staff_session_notes(request):
    notes = SessionNote.objects.filter(staff=request.user).order_by('-date')
    return render(request, "staff/staff_session_notes.html", {"notes": notes})
