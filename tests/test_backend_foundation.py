from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TransactionTestCase

from core.models import Appointment, Hospital, PaymentRecord, StaffProfile
from core.tenancy import resolve_hospital


class BackendFoundationTests(TransactionTestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="North Clinic", email="north@example.com"
        )
        self.patient = User.objects.create_user(
            username="patient", password="test-password"
        )
        self.staff = User.objects.create_user(
            username="staff", password="test-password"
        )
        StaffProfile.objects.create(
            user=self.staff, hospital=self.hospital, role="physiotherapist"
        )

    def appointment(self, **overrides):
        values = {
            "hospital": self.hospital,
            "patient": self.patient,
            "name": "Patient",
            "email": "patient@example.com",
            "phone": "9999999999",
            "service": "orthopedic",
            "date": date(2026, 9, 22),
            "time": "10:00",
            "status": "pending",
        }
        values.update(overrides)
        return Appointment.objects.create(**values)

    def test_staff_hospital_is_resolved_from_profile(self):
        self.assertEqual(resolve_hospital(self.staff), self.hospital)

    def test_active_appointment_slot_is_unique_per_hospital(self):
        self.appointment()
        with self.assertRaises(IntegrityError):
            self.appointment()

    def test_cancelled_appointment_does_not_reserve_slot(self):
        self.appointment(status="cancelled")
        self.appointment()

    def test_payment_amount_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            PaymentRecord.objects.create(
                patient=self.patient,
                amount=Decimal("0.00"),
                method="cash",
            )

    def test_gateway_payment_id_is_unique_when_present(self):
        PaymentRecord.objects.create(
            patient=self.patient,
            amount=Decimal("100.00"),
            method="razorpay",
            razorpay_payment_id="pay_test_123",
        )
        with self.assertRaises(IntegrityError):
            PaymentRecord.objects.create(
                patient=self.patient,
                amount=Decimal("100.00"),
                method="razorpay",
                razorpay_payment_id="pay_test_123",
            )