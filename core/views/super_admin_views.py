from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone
from core.decorators import super_admin_required
from core.models import (
    Hospital, SubscriptionPlan, HospitalSubscription,
    ClinicSubscriptionPayment, SupportTicket, SupportReply, PaymentRecord
)
from core.tasks import send_email_task


@super_admin_required
def super_admin_dashboard(request):
    total_hospitals = Hospital.objects.count()
    active_hospitals = Hospital.objects.filter(is_active=True).count()
    total_subs = HospitalSubscription.objects.filter(status='active').count()

    total_revenue = ClinicSubscriptionPayment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0
    recent_hospitals = Hospital.objects.order_by('-created_at')[:5]
    open_tickets = SupportTicket.objects.filter(status='open').count()
    open_tickets_list = SupportTicket.objects.filter(status='open').order_by('-created_at')[:5]

    context = {
        'total_hospitals': total_hospitals,
        'active_hospitals': active_hospitals,
        'total_subs': total_subs,
        'total_revenue': total_revenue,
        'recent_hospitals': recent_hospitals,
        'open_tickets': open_tickets,
        'open_tickets_list': open_tickets_list,
    }
    return render(request, "super_admin/super_admin_dashboard.html", context)


@super_admin_required
def super_admin_hospitals(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    hospitals = Hospital.objects.all().order_by('-created_at')

    if search:
        hospitals = hospitals.filter(name__icontains=search)
    if status_filter == 'active':
        hospitals = hospitals.filter(is_active=True)
    elif status_filter == 'suspended':
        hospitals = hospitals.filter(is_active=False)

    return render(request, "super_admin/super_admin_hospitals.html", {
        "hospitals": hospitals,
        "search": search,
        "status_filter": status_filter,
    })


@super_admin_required
def super_admin_add_hospital(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        city = request.POST.get('city', '')
        address = request.POST.get('address', '')
        razorpay_key_id = request.POST.get('razorpay_key_id', '')
        razorpay_key_secret = request.POST.get('razorpay_key_secret', '')

        hospital = Hospital.objects.create(
            name=name, email=email, phone=phone, city=city, address=address,
            razorpay_key_id=razorpay_key_id, razorpay_key_secret=razorpay_key_secret,
            is_active=True
        )
        messages.success(request, f"Hospital '{hospital.name}' registered.")
        return redirect("super_admin_hospitals")
    return render(request, "super_admin/super_admin_hospitals.html")


@super_admin_required
def super_admin_edit_hospital(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    if request.method == "POST":
        hospital.name = request.POST.get('name', hospital.name)
        hospital.email = request.POST.get('email', hospital.email)
        hospital.phone = request.POST.get('phone', hospital.phone)
        hospital.city = request.POST.get('city', hospital.city)
        hospital.address = request.POST.get('address', hospital.address)
        hospital.razorpay_key_id = request.POST.get('razorpay_key_id', hospital.razorpay_key_id)
        hospital.razorpay_key_secret = request.POST.get('razorpay_key_secret', hospital.razorpay_key_secret)
        hospital.is_active = request.POST.get('is_active') == 'on'
        hospital.save()
        messages.success(request, f"Hospital '{hospital.name}' updated.")
        return redirect("super_admin_hospitals")
    return render(request, "super_admin/super_admin_hospitals.html", {"hospital": hospital})


@super_admin_required
def super_admin_delete_hospital(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    hospital.is_active = False
    hospital.save()
    messages.info(request, f"Hospital '{hospital.name}' deactivated.")
    return redirect("super_admin_hospitals")


@super_admin_required
def super_admin_subscriptions(request):
    subscriptions = HospitalSubscription.objects.all().order_by('-started_at')
    pending_payments = ClinicSubscriptionPayment.objects.filter(status='pending').order_by('-created_at')
    plans = SubscriptionPlan.objects.all()
    unpaid_clinics = Hospital.objects.filter(subscription__status__in=['trial', 'expired'])

    return render(request, "super_admin/super_admin_subscriptions.html", {
        "subscriptions": subscriptions,
        "pending_payments": pending_payments,
        "plans": plans,
        "unpaid_clinics": unpaid_clinics,
    })


@super_admin_required
def super_admin_confirm_sub_payment(request, payment_id):
    payment = get_object_or_404(ClinicSubscriptionPayment, id=payment_id)
    payment.status = 'paid'
    payment.paid_at = timezone.now()
    payment.save()

    # Update hospital subscription status
    sub, _ = HospitalSubscription.objects.get_or_create(hospital=payment.hospital)
    sub.plan = payment.plan
    sub.status = 'active'
    sub.started_at = timezone.now().date()
    sub.expires_at = timezone.now().date() + timezone.timedelta(days=30 * payment.duration_months)
    sub.save()

    messages.success(request, f"Subscription activated for {payment.hospital.name}.")
    return redirect("super_admin_subscriptions")


@super_admin_required
def super_admin_reject_sub_payment(request, payment_id):
    payment = get_object_or_404(ClinicSubscriptionPayment, id=payment_id)
    payment.status = 'failed'
    payment.save()
    messages.info(request, "Subscription payment rejected.")
    return redirect("super_admin_subscriptions")


@super_admin_required
def super_admin_hospital_payments(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    payments = ClinicSubscriptionPayment.objects.filter(hospital=hospital).order_by('-created_at')
    return render(request, "super_admin/super_admin_payments.html", {"hospital": hospital, "payments": payments})


@super_admin_required
def super_admin_analytics(request):
    total_hospitals = Hospital.objects.count()
    active_hospitals = Hospital.objects.filter(is_active=True).count()
    total_subs = HospitalSubscription.objects.filter(status='active').count()
    active_subs = total_subs
    trial_subs = HospitalSubscription.objects.filter(status='trial').count()
    expired_subs = HospitalSubscription.objects.filter(status='expired').count()
    total_patients = User.objects.filter(is_staff=False, is_superuser=False).count()
    total_staff = User.objects.filter(is_staff=True).count()
    total_appointments = Appointment.objects.count() if 'Appointment' in globals() else 0
    hospitals = Hospital.objects.all()

    return render(request, "super_admin/super_admin_analytics.html", {
        "total_hospitals": total_hospitals,
        "active_hospitals": active_hospitals,
        "total_subs": total_subs,
        "active_subs": active_subs,
        "trial_subs": trial_subs,
        "expired_subs": expired_subs,
        "total_patients": total_patients,
        "total_staff": total_staff,
        "total_appointments": total_appointments,
        "hospitals": hospitals,
    })


@super_admin_required
def super_admin_all_payments(request):
    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')
    payments = PaymentRecord.objects.all().order_by('-created_at')

    if status_filter:
        payments = payments.filter(status=status_filter)
    if method_filter:
        payments = payments.filter(method=method_filter)

    total_paid = payments.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0
    total_pending = payments.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
    paid_count = payments.filter(status='paid').count()
    pending_count = payments.filter(status='pending').count()
    failed_count = payments.filter(status='failed').count()

    return render(request, "super_admin/super_admin_payments.html", {
        "payments": payments,
        "status_filter": status_filter,
        "method_filter": method_filter,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "paid_count": paid_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
    })


@super_admin_required
def send_subscription_reminder(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    if hospital.email:
        subject = "PhysioRehab Platform — Subscription Renewal Notice"
        body = (
            f"Dear {hospital.name} Administration,\n\n"
            f"Your clinic software subscription is due for renewal. "
            f"Please visit your clinic settings or contact support to ensure uninterrupted service.\n\n"
            f"Warm regards,\nPhysioRehab Platform Team"
        )
        send_email_task.delay(subject, body, [hospital.email])
        messages.success(request, f"Renewal reminder dispatched to {hospital.email}.")
    return redirect("super_admin_subscriptions")


@super_admin_required
def super_admin_support(request):
    status_filter = request.GET.get('status', '')
    tickets = SupportTicket.objects.all().order_by('-created_at')
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    open_count = SupportTicket.objects.filter(status='open').count()
    in_progress_count = SupportTicket.objects.filter(status='in_progress').count()
    resolved_count = SupportTicket.objects.filter(status='resolved').count()

    return render(request, "super_admin/super_admin_support.html", {
        "tickets": tickets,
        "status_filter": status_filter,
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "resolved_count": resolved_count,
    })


@super_admin_required
def super_admin_support_reply(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == "POST":
        message_text = request.POST.get('message', '')
        if message_text:
            SupportReply.objects.create(
                ticket=ticket,
                replier=request.user,
                message=message_text
            )
            ticket.status = 'in_progress'
            ticket.save()
            messages.success(request, "Reply recorded.")
            return redirect("super_admin_support")
    return render(request, "super_admin/super_admin_support.html", {"ticket": ticket})


def subscription_page(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, "super_admin/super_admin_subscriptions.html", {"plans": plans})
