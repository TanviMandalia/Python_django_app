from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from core.decorators import admin_required
from core.models import Message, UserActivity


def get_admin_user():
    return User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()


@login_required
def client_chat(request):
    admin_user = get_admin_user()
    if not admin_user:
        messages.error(request, "Clinic staff is currently offline.")
        return redirect("client_dashboard")

    if request.method == "POST":
        content = request.POST.get("message", "").strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=admin_user,
                content=content,
                status=Message.STATUS_SENT
            )
            return redirect("client_chat")

    chat_messages = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=admin_user)) |
        (Q(sender=admin_user) & Q(receiver=request.user))
    ).order_by("created_at")

    Message.objects.filter(sender=admin_user, receiver=request.user, is_read=False).update(is_read=True)

    return render(request, "client_chat.html", {
        "admin": admin_user,
        "messages_list": chat_messages,
    })


@admin_required
def admin_chat(request):
    patient_ids = Message.objects.filter(
        Q(receiver=request.user) | Q(sender=request.user)
    ).values_list('sender_id', 'receiver_id')

    unique_ids = set()
    for s_id, r_id in patient_ids:
        if s_id != request.user.id:
            unique_ids.add(s_id)
        if r_id != request.user.id:
            unique_ids.add(r_id)

    conversations = []
    for p_id in unique_ids:
        patient = User.objects.filter(id=p_id).first()
        if patient:
            last_msg = Message.objects.filter(
                (Q(sender=request.user) & Q(receiver=patient)) |
                (Q(sender=patient) & Q(receiver=request.user))
            ).order_by('-created_at').first()
            unread_count = Message.objects.filter(sender=patient, receiver=request.user, is_read=False).count()
            conversations.append({
                'patient': patient,
                'last_message': last_msg,
                'unread_count': unread_count
            })

    return render(request, "admin_chat.html", {"conversations": conversations})


@admin_required
def admin_chat_detail(request, patient_id):
    patient = get_object_or_404(User, id=patient_id)

    if request.method == "POST":
        content = request.POST.get("message", "").strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=patient,
                content=content,
                status=Message.STATUS_SENT
            )
            return redirect("admin_chat_detail", patient_id=patient.id)

    chat_messages = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=patient)) |
        (Q(sender=patient) & Q(receiver=request.user))
    ).order_by("created_at")

    Message.objects.filter(sender=patient, receiver=request.user, is_read=False).update(is_read=True)

    return render(request, "admin_chat_detail.html", {
        "patient": patient,
        "messages_list": chat_messages,
    })


@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(Message, id=message_id)
    if msg.sender == request.user or request.user.is_superuser:
        msg.delete()
        messages.info(request, "Message deleted.")
    if request.user.is_superuser or hasattr(request.user, 'clinic_admin_profile'):
        return redirect("admin_chat")
    return redirect("client_chat")


@login_required
def start_typing(request):
    receiver_id = request.GET.get('receiver_id')
    receiver = User.objects.filter(id=receiver_id).first() if receiver_id else None
    UserActivity.objects.update_or_create(
        user=request.user,
        defaults={'is_typing': True, 'typing_to': receiver, 'last_seen': timezone.now()}
    )
    return JsonResponse({'status': 'ok'})


@login_required
def stop_typing(request):
    UserActivity.objects.update_or_create(
        user=request.user,
        defaults={'is_typing': False, 'typing_to': None, 'last_seen': timezone.now()}
    )
    return JsonResponse({'status': 'ok'})


@login_required
def check_typing(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if target_user:
        activity = UserActivity.objects.filter(user=target_user, typing_to=request.user, is_typing=True).first()
        return JsonResponse({'is_typing': bool(activity)})
    return JsonResponse({'is_typing': False})

