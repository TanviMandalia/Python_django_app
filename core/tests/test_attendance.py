from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import time as dtime
from decimal import Decimal
from core.models import Attendance
from core.services.attendance_service import AttendanceService


class AttendanceTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="nurse_staff", email="nurse@test.com", password="password123"
        )
        self.today = timezone.now().date()

    def test_calculate_hours(self):
        hours = AttendanceService.calculate_hours(dtime(10, 0), dtime(13, 0))
        self.assertEqual(hours, Decimal('3.00'))

    def test_process_shift_record(self):
        attendance = Attendance.objects.create(
            staff=self.staff_user,
            date=self.today,
            clock_in=dtime(10, 0),
            morning_clock_out=dtime(13, 0),
            evening_clock_in=dtime(16, 0),
            clock_out=dtime(20, 0)
        )
        AttendanceService.process_shift_record(attendance)
        self.assertEqual(attendance.morning_hours, Decimal('3.00'))
        self.assertEqual(attendance.evening_hours, Decimal('4.00'))
        self.assertEqual(attendance.total_hours, Decimal('7.00'))

    def test_late_detection(self):
        # Morning shift starts at 10:00 AM with 15 min grace (10:15)
        on_time = AttendanceService.is_late('morning', dtime(10, 10))
        self.assertFalse(on_time)

        late = AttendanceService.is_late('morning', dtime(10, 20))
        self.assertTrue(late)

