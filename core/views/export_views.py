from django.contrib.auth.models import User
from django.utils import timezone
from core.decorators import admin_required
from core.models import Appointment, PaymentRecord, ClinicSubscriptionPayment
from core.services.export_service import ExportService


@admin_required
def export_patients_excel(request):
    patients = User.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')
    headers = ["Patient ID", "Username", "First Name", "Last Name", "Email", "Phone", "Blood Group", "Date Joined"]
    rows = []
    for p in patients:
        profile = getattr(p, 'profile', None)
        rows.append([
            p.id,
            p.username,
            p.first_name,
            p.last_name,
            p.email,
            getattr(profile, 'phone_number', ''),
            getattr(profile, 'blood_group', ''),
            p.date_joined.strftime('%Y-%m-%d') if p.date_joined else ''
        ])
    return ExportService.create_excel_response("physiorehab_patients", "Patients", headers, rows)


@admin_required
def export_patients_pdf(request):
    patients = User.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')
    table_data = [["ID", "Name", "Email", "Phone", "Blood Group", "Joined Date"]]
    for p in patients:
        profile = getattr(p, 'profile', None)
        table_data.append([
            str(p.id),
            p.get_full_name() or p.username,
            p.email,
            getattr(profile, 'phone_number', '') or '-',
            getattr(profile, 'blood_group', '') or '-',
            p.date_joined.strftime('%d-%b-%Y') if p.date_joined else '-'
        ])
    return ExportService.create_pdf_response("physiorehab_patients", "Registered Patients Directory", table_data)


@admin_required
def export_appointments_excel(request):
    appointments = Appointment.objects.all().order_by('-date', '-time')
    headers = ["Appt ID", "Patient Name", "Email", "Phone", "Service", "Date", "Time", "Status", "Fee (₹)"]
    rows = []
    for a in appointments:
        rows.append([
            a.id,
            a.name,
            a.email,
            a.phone,
            a.get_service_display(),
            a.date.strftime('%Y-%m-%d'),
            a.get_time_display(),
            a.status.title(),
            float(a.consultation_fee or 0)
        ])
    return ExportService.create_excel_response("physiorehab_appointments", "Appointments", headers, rows)


@admin_required
def export_appointments_pdf(request):
    appointments = Appointment.objects.all().order_by('-date', '-time')[:50]
    table_data = [["ID", "Patient", "Service", "Date", "Time", "Status", "Fee"]]
    for a in appointments:
        table_data.append([
            str(a.id),
            a.name[:18],
            a.get_service_display()[:15],
            a.date.strftime('%d-%b-%y'),
            a.get_time_display(),
            a.status.title(),
            f"₹{a.consultation_fee or 0}"
        ])
    return ExportService.create_pdf_response("physiorehab_appointments", "Appointments Schedule", table_data, orientation='landscape')


@admin_required
def export_analytics_pdf(request):
    total_appts = Appointment.objects.count()
    completed_appts = Appointment.objects.filter(status='completed').count()
    total_patients = User.objects.filter(is_staff=False, is_superuser=False).count()

    table_data = [
        ["Metric", "Value"],
        ["Total Appointments", str(total_appts)],
        ["Completed Treatments", str(completed_appts)],
        ["Active Patients", str(total_patients)],
        ["Report Generated On", timezone.now().strftime('%d %B %Y %I:%M %p')]
    ]
    return ExportService.create_pdf_response("physiorehab_analytics", "Clinical Operations Summary", table_data)


@admin_required
def export_payments_excel(request):
    payments = PaymentRecord.objects.all().order_by('-created_at')
    headers = ["Payment ID", "Patient", "Amount (₹)", "Method", "Status", "Transaction ID", "Date"]
    rows = []
    for p in payments:
        rows.append([
            p.id,
            p.patient.username if p.patient else 'Guest',
            float(p.amount),
            p.method.upper(),
            p.status.title(),
            p.transaction_id or p.razorpay_payment_id or '-',
            p.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    return ExportService.create_excel_response("platform_payments", "Payments", headers, rows)


@admin_required
def export_payments_pdf(request):
    payments = PaymentRecord.objects.all().order_by('-created_at')[:50]
    table_data = [["ID", "Patient", "Amount", "Method", "Status", "Date"]]
    for p in payments:
        table_data.append([
            str(p.id),
            (p.patient.username if p.patient else 'Guest')[:15],
            f"₹{p.amount}",
            p.method.upper(),
            p.status.title(),
            p.created_at.strftime('%d-%b-%Y')
        ])
    return ExportService.create_pdf_response("platform_payments", "Platform Transactions Report", table_data)
