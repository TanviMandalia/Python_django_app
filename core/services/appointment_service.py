from datetime import date
from django.db.models import Q
from core.models import Appointment, Hospital
from core.email_utils import (
    send_appointment_confirmation,
    send_appointment_status_update,
    send_admin_new_appointment_alert,
)
from core.notifications import (
    notify_appointment_booked,
    notify_appointment_status,
)


class AppointmentService:
    @staticmethod
    def get_available_slots(appointment_date, hospital=None):
        all_slots = [choice[0] for choice in Appointment.TIME_CHOICES]
        query = Q(date=appointment_date, status__in=['pending', 'confirmed'])
        if hospital:
            query &= Q(hospital=hospital)
        booked_slots = set(
            Appointment.objects.filter(query).values_list('time', flat=True)
        )
        return [
            {
                'slot': slot,
                'is_available': slot not in booked_slots
            }
            for slot in all_slots
        ]

    @staticmethod
    def is_slot_available(appointment_date, time_slot, hospital=None, exclude_id=None):
        query = Q(date=appointment_date, time=time_slot, status__in=['pending', 'confirmed'])
        if hospital:
            query &= Q(hospital=hospital)
        if exclude_id:
            query &= ~Q(id=exclude_id)
        return not Appointment.objects.filter(query).exists()

    @staticmethod
    def create_appointment(data, patient_user=None, hospital=None):
        appointment = Appointment.objects.create(
            hospital=hospital,
            patient=patient_user,
            name=data.get('name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            service=data.get('service', 'orthopedic'),
            date=data.get('date'),
            time=data.get('time'),
            notes=data.get('notes', ''),
            consultation_fee=data.get('consultation_fee'),
            status='pending'
        )

        try:
            notify_appointment_booked(appointment)
            send_appointment_confirmation(appointment)
            send_admin_new_appointment_alert(appointment)
        except Exception:
            pass

        return appointment

    @staticmethod
    def update_status(appointment, new_status):
        old_status = appointment.status
        appointment.status = new_status
        appointment.save()

        try:
            notify_appointment_status(appointment)
            send_appointment_status_update(appointment)
        except Exception:
            pass

        return appointment

