from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from core.decorators import doctor_required
from core.models import SessionNote, Appointment, Profile
from core.forms.medical_forms import SessionNoteForm
from core.tasks import send_email_task


@doctor_required
def progress_tracking(request):
    """Doctor dashboard & patient clinical progress tracking overview."""
    today = timezone.now().date()
    patient_id = request.GET.get('patient_id')
    selected_patient = None
    patient_notes = []

    # All registered patients
    patients = User.objects.filter(is_staff=False, is_superuser=False).order_by('first_name', 'last_name')

    if patient_id:
        selected_patient = get_object_or_404(User, id=patient_id)
        patient_notes = SessionNote.objects.filter(patient=selected_patient).order_by('-date')

    # Today's appointments for clinical queue
    today_appointments = Appointment.objects.filter(date=today).order_by('time')
    recent_notes = SessionNote.objects.order_by('-created_at')[:10]

    context = {
        'patients': patients,
        'selected_patient': selected_patient,
        'patient_notes': patient_notes,
        'today_appointments': today_appointments,
        'recent_notes': recent_notes,
    }
    return render(request, "doctor/progress_tracking.html", context)


@doctor_required
def reports_analytics(request):
    """Clinical reports & therapy statistics."""
    total_appointments = Appointment.objects.count()
    completed_appointments = Appointment.objects.filter(status='completed').count()
    total_patients = User.objects.filter(is_staff=False, is_superuser=False).count()
    total_notes = SessionNote.objects.count()

    context = {
        'total_appointments': total_appointments,
        'completed_appointments': completed_appointments,
        'total_patients': total_patients,
        'total_notes': total_notes,
    }
    return render(request, "doctor/reports_analytics.html", context)


@doctor_required
def add_session_note(request):
    """Add a medical session note for a patient."""
    if request.method == "POST":
        form = SessionNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.staff = request.user
            note.save()
            messages.success(request, f"🩺 Clinical session note recorded for {note.patient.get_full_name() or note.patient.username}.")
            return redirect("progress_tracking")
    else:
        patient_id = request.GET.get('patient_id')
        initial = {}
        if patient_id:
            initial['patient'] = patient_id
        form = SessionNoteForm(initial=initial)

    return render(request, "doctor/add_session_note.html", {"form": form})


@doctor_required
def edit_session_note(request, note_id):
    note = get_object_or_404(SessionNote, id=note_id)
    if request.method == "POST":
        form = SessionNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Session note updated successfully.")
            return redirect("progress_tracking")
    else:
        form = SessionNoteForm(instance=note)

    return render(request, "doctor/edit_session_note.html", {"form": form, "note": note})


@doctor_required
def delete_session_note(request, note_id):
    note = get_object_or_404(SessionNote, id=note_id)
    note.delete()
    messages.info(request, "🗑️ Session note deleted.")
    return redirect("progress_tracking")


@doctor_required
def send_exercise_reminder(request, patient_id):
    patient = get_object_or_404(User, id=patient_id)
    if patient.email:
        subject = "PhysioRehab — Friendly Home Exercise Reminder"
        body = (
            f"Dear {patient.first_name or patient.username},\n\n"
            f"This is a friendly reminder from your physiotherapist at PhysioRehab to complete your prescribed daily exercises.\n\n"
            f"Consistency is key to a fast and complete recovery!\n\n"
            f"Warm regards,\nPhysioRehab Medical Team"
        )
        send_email_task.delay(subject, body, [patient.email])
        messages.success(request, f"📨 Exercise reminder dispatched to {patient.email}.")
    else:
        messages.warning(request, "⚠️ Patient does not have an email address on file.")

    return redirect("progress_tracking")
