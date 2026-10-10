"""
Comprehensive automated tests for Dr. Dhvani Patalia Physio Rehab appointment slot generation,
shift timings, working hours matrix, Sunday restrictions, and double-booking prevention.
"""
from datetime import date, timedelta
from django.utils import timezone
import zoneinfo

from core.models import Appointment
from core.appointment_slots import (
    CLINIC_SLOTS,
    MORNING_SLOTS,
    EVENING_SLOTS,
    normalize_slot_time,
    validate_appointment_booking,
    get_available_slots_for_date,
    CLINIC_TIMEZONE,
)
from tests.test_helpers import BaseHospitalTestCase


class AppointmentSlotValidationTests(BaseHospitalTestCase):
    """Verifies that all 14 official slots are accepted and all invalid times are rejected."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Dr. Dhvani Patalia Physio Rehab")
        self.patient = self.create_patient(hospital=self.hospital, username="slot_patient")

    def _get_next_weekday(self, days_ahead=2):
        """Helper to get a future Monday-Friday date."""
        target = timezone.now().date() + timedelta(days=days_ahead)
        # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        while target.weekday() >= 5:  # Skip Sat & Sun
            target += timedelta(days=1)
        return target

    def test_all_14_official_slots_are_valid(self):
        """Verify all 6 morning and 8 evening slots are recognized as valid."""
        self.assertEqual(len(MORNING_SLOTS), 6)
        self.assertEqual(len(EVENING_SLOTS), 8)
        self.assertEqual(len(CLINIC_SLOTS), 14)

        expected_morning = [
            "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM"
        ]
        expected_evening = [
            "04:00 PM", "04:30 PM", "05:00 PM", "05:30 PM",
            "06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM"
        ]

        target_date = self._get_next_weekday(days_ahead=3)

        for slot in expected_morning:
            is_valid, err, norm = validate_appointment_booking(target_date, slot, hospital=self.hospital)
            self.assertTrue(is_valid, f"Slot {slot} should be valid, got error: {err}")
            self.assertEqual(norm, slot)

        for slot in expected_evening:
            is_valid, err, norm = validate_appointment_booking(target_date, slot, hospital=self.hospital)
            self.assertTrue(is_valid, f"Slot {slot} should be valid, got error: {err}")
            self.assertEqual(norm, slot)

    def test_working_hour_matrix_rejections(self):
        """
        Verify the exact working hour test matrix:
        9:59 AM  -> Reject
        10:00 AM -> Valid
        10:30 AM -> Valid
        12:30 PM -> Valid
        1:00 PM  -> Reject (shift end, not slot start)
        3:59 PM  -> Reject
        4:00 PM  -> Valid
        7:30 PM  -> Valid
        8:00 PM  -> Reject (shift end, not slot start)
        """
        target_date = self._get_next_weekday(days_ahead=3)

        matrix = [
            ("9:59 AM", False),
            ("10:00 AM", True),
            ("10:30 AM", True),
            ("12:30 PM", True),
            ("1:00 PM", False),
            ("3:59 PM", False),
            ("4:00 PM", True),
            ("7:30 PM", True),
            ("8:00 PM", False),
        ]

        for time_str, should_pass in matrix:
            is_valid, err, _ = validate_appointment_booking(target_date, time_str, hospital=self.hospital)
            if should_pass:
                self.assertTrue(is_valid, f"Time {time_str} should be accepted, but got: {err}")
            else:
                self.assertFalse(is_valid, f"Time {time_str} should be REJECTED, but was accepted.")

    def test_unauthorized_intermediate_slots_rejected(self):
        """Explicitly test 10:15 AM, 10:45 AM, 11:15 AM, 3:30 PM, 4:15 PM are rejected."""
        target_date = self._get_next_weekday(days_ahead=3)
        invalid_slots = ["10:15 AM", "10:45 AM", "11:15 AM", "3:30 PM", "4:15 PM"]

        for slot in invalid_slots:
            is_valid, err, _ = validate_appointment_booking(target_date, slot, hospital=self.hospital)
            self.assertFalse(is_valid, f"Intermediate slot {slot} must be rejected")
            self.assertIn("not an authorized clinic slot", err)

    def test_sunday_appointment_restrictions(self):
        """Sunday is By Appointment only. Public client booking rejected; admin booking allowed."""
        # Find next Sunday
        target = timezone.now().date() + timedelta(days=1)
        while target.weekday() != 6:  # 6 is Sunday
            target += timedelta(days=1)

        # Public booking (allow_sunday=False)
        is_valid, err, _ = validate_appointment_booking(
            target, "10:00 AM", hospital=self.hospital, allow_sunday=False
        )
        self.assertFalse(is_valid)
        self.assertIn("Sunday", err)

        # Admin booking (allow_sunday=True)
        is_valid_admin, err_admin, _ = validate_appointment_booking(
            target, "10:00 AM", hospital=self.hospital, allow_sunday=True
        )
        self.assertTrue(is_valid_admin, f"Admin should be able to book on Sunday: {err_admin}")

    def test_saturday_open_for_booking(self):
        """Saturday is an active working day (Monday to Saturday clinic operation)."""
        target = timezone.now().date() + timedelta(days=1)
        while target.weekday() != 5:  # 5 is Saturday
            target += timedelta(days=1)

        is_valid, err, norm = validate_appointment_booking(
            target, "10:00 AM", hospital=self.hospital, allow_sunday=False
        )
        self.assertTrue(is_valid, f"Saturday booking should be allowed: {err}")
        self.assertEqual(norm, "10:00 AM")

    def test_past_date_and_time_rejected(self):
        """Appointments in the past must be rejected."""
        past_date = timezone.now().date() - timedelta(days=2)
        is_valid, err, _ = validate_appointment_booking(
            past_date, "10:00 AM", hospital=self.hospital
        )
        self.assertFalse(is_valid)
        self.assertIn("past", err)


class AppointmentDoubleBookingTests(BaseHospitalTestCase):
    """Critical tests for preventing double booking and race conditions."""

    def setUp(self):
        super().setUp()
        self.hospital = self.create_hospital(name="Dr. Dhvani Patalia Physio Rehab")
        self.patient_a = self.create_patient(hospital=self.hospital, username="patient_a", email="a@example.com")
        self.patient_b = self.create_patient(hospital=self.hospital, username="patient_b", email="b@example.com")

        # Find next Tuesday (weekday)
        self.target_date = timezone.now().date() + timedelta(days=2)
        while self.target_date.weekday() >= 5:
            self.target_date += timedelta(days=1)

    def test_prevent_double_booking_same_slot(self):
        """
        Patient A -> 5:00 PM (Success)
        Patient B -> 5:00 PM (Rejected because slot already occupied)
        """
        slot = "05:00 PM"

        # Patient A books
        is_valid_a, _, norm_time = validate_appointment_booking(
            self.target_date, slot, hospital=self.hospital
        )
        self.assertTrue(is_valid_a)

        Appointment.objects.create(
            hospital=self.hospital,
            patient=self.patient_a,
            name="Patient A",
            email=self.patient_a.email,
            phone="9409510501",
            service="Chiropractic Care",
            date=self.target_date,
            time=norm_time,
            status="confirmed",
        )

        # Patient B attempts to book the same slot
        is_valid_b, err_b, _ = validate_appointment_booking(
            self.target_date, slot, hospital=self.hospital
        )
        self.assertFalse(is_valid_b, "Patient B should be blocked from double-booking 5:00 PM")
        self.assertIn("already booked", err_b)

    def test_client_portal_booking_endpoint_blocks_double_booking(self):
        """Verify HTTP POST to /book/ endpoint rejects duplicate booking."""
        self.client.force_login(self.patient_a)
        post_data = {
            "hospital_id": self.hospital.id,
            "service": "Chiropractic Rehabilitation",
            "date": self.target_date.strftime("%Y-%m-%d"),
            "time": "10:30 AM",
            "notes": "First booking",
        }
        res_a = self.client.post("/book/", post_data)
        self.assertEqual(res_a.status_code, 302)  # Redirect to my_appointments

        # Patient B logs in and posts identical date and slot
        self.client.force_login(self.patient_b)
        res_b = self.client.post("/book/", post_data)
        # Should stay on page (200) with error message
        self.assertEqual(res_b.status_code, 200)
        content = res_b.content.decode("utf-8")
        self.assertIn("already booked", content)
