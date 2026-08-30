from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Appointment, SessionNote, Review, ClinicPromo, ClinicSettings, PaymentRecord
from core.services.appointment_service import AppointmentService
from core.forms.appointment_forms import AppointmentBookingForm
from core.forms.clinic_forms import ReviewForm


@login_required
def client_dashboard(request):
    user = request.user
    today = timezone.now().date()

    # Client appointments
    appointments = Appointment.objects.filter(patient=user).order_by('-date', '-time')
    upcoming_appointment = appointments.filter(date__gte=today, status__in=['pending', 'confirmed']).first()
    past_appointments = appointments.filter(status='completed')

    # Clinical Session notes for this patient
    session_notes = SessionNote.objects.filter(patient=user).order_by('-date')[:5]

    # Active Clinic Promos
    active_promos = ClinicPromo.objects.filter(is_active=True).order_by('-created_at')[:3]
    clinic_info = ClinicSettings.objects.first()

    # Payment summary
    payments = PaymentRecord.objects.filter(patient=user).order_by('-created_at')[:5]

    context = {
        'upcoming_appointment': upcoming_appointment,
        'recent_appointments': appointments[:5],
        'total_appointments_count': appointments.count(),
        'completed_sessions_count': past_appointments.count(),
        'session_notes': session_notes,
        'active_promos': active_promos,
        'clinic_info': clinic_info,
        'recent_payments': payments,
    }
    return render(request, "client/client_dashboard.html", context)


def book_appointment(request):
    clinic_info = ClinicSettings.objects.first()
    if request.method == "POST":
        form = AppointmentBookingForm(request.POST)
        if form.is_valid():
            appt_date = form.cleaned_data['date']
            appt_time = form.cleaned_data['time']

            # Validate slot availability
            if not AppointmentService.is_slot_available(appt_date, appt_time):
                messages.error(request, f"⚠️ The slot on {appt_date} at {appt_time} is already booked. Please choose another time.")
                return render(request, "client/book_appointment.html", {"form": form, "clinic_info": clinic_info})

            patient_user = request.user if request.user.is_authenticated else None
            appointment = form.save(commit=False)
            if patient_user:
                appointment.patient = patient_user
            if clinic_info:
                appointment.consultation_fee = clinic_info.appointment_fee
            appointment.save()

            messages.success(request, f"🎉 Appointment booked successfully for {appointment.date} at {appointment.get_time_display()}! A confirmation email has been dispatched.")
            if request.user.is_authenticated:
                return redirect("my_appointments")
            return redirect("home")
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
                'phone': getattr(getattr(request.user, 'profile', None), 'phone_number', ''),
            }
        form = AppointmentBookingForm(initial=initial)

    return render(request, "client/book_appointment.html", {"form": form, "clinic_info": clinic_info})


@login_required
def my_appointments(request):
    status_filter = request.GET.get('status', '')
    appointments = Appointment.objects.filter(patient=request.user).order_by('-date', '-time')

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    return render(request, "client/my_appointments.html", {
        "appointments": appointments,
        "status_filter": status_filter,
    })


@login_required
def submit_review(request):
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.patient = request.user
            review.is_approved = False  # requires admin approval
            review.save()
            messages.success(request, "⭐ Thank you for your feedback! Your review has been submitted for moderation.")
            return redirect("client_dashboard")
    else:
        form = ReviewForm(initial={'reviewer_name': request.user.get_full_name() or request.user.username})

    return render(request, "client/client_dashboard.html", {"review_form": form})
