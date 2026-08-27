from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
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

    context = {
        'total_hospitals': total_hospitals,
        'active_hospitals': active_hospitals,
        'total_subs': total_subs,
        'total_revenue': total_revenue,
        'recent_hospitals': recent_hospitals,
        'open_tickets': open_tickets,
    }
    return render(request, "super_admin_dashboard.html", context)


@super_admin_required
def super_admin_hospitals(request):
    hospitals = Hospital.objects.all().order_by('-created_at')
    return render(request, "super_admin_hospitals.html", {"hospitals": hospitals})


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
    return render(request, "super_admin_add_hospital.html")


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
    return render(request, "super_admin_edit_hospital.html", {"hospital": hospital})


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
    payments = ClinicSubscriptionPayment.objects.all().order_by('-created_at')[:10]
    return render(request, "super_admin_subscriptions.html", {
        "subscriptions": subscriptions,
        "payments": payments,
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
    return render(request, "super_admin_hospital_payments.html", {"hospital": hospital, "payments": payments})


@super_admin_required
def super_admin_analytics(request):
    total_hospitals = Hospital.objects.count()
    total_subs = HospitalSubscription.objects.filter(status='active').count()
    revenue = ClinicSubscriptionPayment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0

    return render(request, "super_admin_analytics.html", {
        "total_hospitals": total_hospitals,
        "total_subs": total_subs,
        "revenue": revenue,
    })


@super_admin_required
def super_admin_all_payments(request):
    payments = ClinicSubscriptionPayment.objects.all().order_by('-created_at')
    patient_payments = PaymentRecord.objects.all().order_by('-created_at')[:50]
    return render(request, "super_admin_all_payments.html", {
        "payments": payments,
        "patient_payments": patient_payments,
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
    tickets = SupportTicket.objects.all().order_by('-created_at')
    return render(request, "super_admin_support.html", {"tickets": tickets})


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
    return render(request, "super_admin_support_reply.html", {"ticket": ticket})


def subscription_page(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, "subscription_page.html", {"plans": plans})

