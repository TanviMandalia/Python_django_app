import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from core.decorators import admin_required
from core.models import PaymentRecord, Appointment, ClinicSettings
from core.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


@login_required
def payments(request):
    """Patient payment history and pending bills."""
    user = request.user
    pending_appointments = Appointment.objects.filter(
        patient=user,
        status__in=['confirmed', 'completed']
    ).exclude(payments__status='paid')

    payment_history = PaymentRecord.objects.filter(patient=user).order_by('-created_at')
    clinic_info = ClinicSettings.objects.first()

    context = {
        'pending_appointments': pending_appointments,
        'payment_history': payment_history,
        'clinic_info': clinic_info,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }
    return render(request, "payments.html", context)


@login_required
def razorpay_create_order(request):
    """AJAX endpoint: Generates Razorpay order."""
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            amount = Decimal(str(data.get('amount', 500)))
            appointment_id = data.get('appointment_id')

            appointment = None
            if appointment_id:
                appointment = Appointment.objects.filter(id=appointment_id).first()

            # Create Razorpay order via service
            order = PaymentService.create_razorpay_order(
                amount_inr=amount,
                receipt_id=f"appt_{appointment_id or request.user.id}"
            )

            # Record pending payment record
            PaymentRecord.objects.create(
                appointment=appointment,
                patient=request.user,
                amount=amount,
                method='razorpay',
                status='pending',
                razorpay_order_id=order.get('id', '')
            )

            return JsonResponse({
                'status': 'success',
                'order_id': order.get('id'),
                'amount': order.get('amount'),
                'currency': order.get('currency', 'INR'),
                'key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
            })
        except Exception as e:
            logger.error(f"Error creating razorpay order: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)


@login_required
def razorpay_verify_payment(request):
    """AJAX endpoint: Verifies signature and marks payment paid."""
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            order_id = data.get('razorpay_order_id', '')
            payment_id = data.get('razorpay_payment_id', '')
            signature = data.get('razorpay_signature', '')

            is_valid = PaymentService.verify_payment_signature(order_id, payment_id, signature)
            if is_valid:
                payment_record = PaymentRecord.objects.filter(razorpay_order_id=order_id).first()
                if payment_record:
                    payment_record.status = 'paid'
                    payment_record.razorpay_payment_id = payment_id
                    payment_record.razorpay_signature = signature
                    payment_record.save()

                return JsonResponse({'status': 'success', 'message': 'Payment successfully verified!'})
            else:
                return JsonResponse({'status': 'failed', 'message': 'Invalid payment signature.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)


@csrf_exempt
def razorpay_webhook(request):
    """Webhook endpoint for Razorpay asynchronous payment capture."""
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            event = data.get('event')
            if event == 'payment.captured':
                payload = data.get('payload', {}).get('payment', {}).get('entity', {})
                order_id = payload.get('order_id')
                payment_id = payload.get('id')

                payment_record = PaymentRecord.objects.filter(razorpay_order_id=order_id).first()
                if payment_record:
                    payment_record.status = 'paid'
                    payment_record.razorpay_payment_id = payment_id
                    payment_record.save()

            return HttpResponse(status=200)
        except Exception as e:
            logger.error(f"Razorpay webhook error: {e}")
            return HttpResponse(status=400)

    return HttpResponse(status=405)


@login_required
def record_cash_payment(request):
    if request.method == "POST":
        appointment_id = request.POST.get('appointment_id')
        amount = request.POST.get('amount', 500)
        notes = request.POST.get('notes', 'Paid in cash at clinic reception')

        appointment = get_object_or_404(Appointment, id=appointment_id)
        PaymentRecord.objects.create(
            appointment=appointment,
            patient=appointment.patient or request.user,
            amount=amount,
            method='cash',
            status='paid',
            notes=notes
        )
        messages.success(request, f"Cash payment of ₹{amount} recorded.")
    return redirect("admin_payments")


@login_required
def record_upi_payment(request):
    if request.method == "POST":
        appointment_id = request.POST.get('appointment_id')
        amount = request.POST.get('amount', 500)
        txn_id = request.POST.get('transaction_id', '')

        appointment = get_object_or_404(Appointment, id=appointment_id)
        PaymentRecord.objects.create(
            appointment=appointment,
            patient=request.user,
            amount=amount,
            method='upi',
            status='pending',
            transaction_id=txn_id
        )
        messages.success(request, f"UPI reference {txn_id} submitted. Verification is pending.")
    return redirect("payments")


@admin_required
def admin_payments(request):
    payments_list = PaymentRecord.objects.all().order_by('-created_at')
    return render(request, "admin_payments.html", {"payments": payments_list})


@admin_required
def confirm_payment(request, payment_id):
    payment = get_object_or_404(PaymentRecord, id=payment_id)
    payment.status = 'paid'
    payment.save()
    messages.success(request, f"Payment #{payment.id} confirmed.")
    return redirect("admin_payments")


@admin_required
def reject_payment(request, payment_id):
    payment = get_object_or_404(PaymentRecord, id=payment_id)
    payment.status = 'failed'
    payment.save()
    messages.info(request, f"Payment #{payment.id} rejected.")
    return redirect("admin_payments")

