from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Appointment, Hospital
from core.services.appointment_service import AppointmentService


class AppointmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(name="Test Clinic", email="clinic@test.com")
        self.patient = User.objects.create_user(
            username="patient1", email="patient1@test.com", password="password123"
        )
        self.today = timezone.now().date()

    def test_create_appointment_service(self):
        data = {
            "name": "Jane Doe",
            "email": "jane@test.com",
            "phone": "+91 98765 00000",
            "service": "orthopedic",
            "date": self.today,
            "time": "10:00",
            "consultation_fee": 500.00,
        }
        appt = AppointmentService.create_appointment(data, patient_user=self.patient, hospital=self.hospital)
        self.assertIsNotNone(appt.id)
        self.assertEqual(appt.status, "pending")
        self.assertEqual(appt.service, "orthopedic")

    def test_slot_availability_check(self):
        Appointment.objects.create(
            hospital=self.hospital,
            name="Existing Patient",
            email="existing@test.com",
            phone="9999999999",
            date=self.today,
            time="11:00",
            service="sports",
            status="confirmed"
        )

        is_available = AppointmentService.is_slot_available(self.today, "11:00", hospital=self.hospital)
        self.assertFalse(is_available)

        is_other_available = AppointmentService.is_slot_available(self.today, "12:00", hospital=self.hospital)
        self.assertTrue(is_other_available)

    def test_status_update(self):
        appt = Appointment.objects.create(
            name="John Doe",
            email="john@test.com",
            phone="8888888888",
            date=self.today,
            time="10:30",
            service="pediatric",
            status="pending"
        )
        updated = AppointmentService.update_status(appt, "confirmed")
        self.assertEqual(updated.status, "confirmed")

