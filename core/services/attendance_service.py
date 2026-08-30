from datetime import datetime, time as dtime, timedelta
from decimal import Decimal
from django.utils import timezone
from core.models import Attendance

MORNING_START = dtime(10, 0)
MORNING_END = dtime(13, 0)
EVENING_START = dtime(16, 0)
EVENING_END = dtime(20, 0)
LATE_GRACE_MINUTES = 15


class AttendanceService:
    @staticmethod
    def calculate_hours(clock_in, clock_out):
        if not clock_in or not clock_out:
            return Decimal('0.00')
        dummy_date = timezone.now().date()
        dt_in = datetime.combine(dummy_date, clock_in)
        dt_out = datetime.combine(dummy_date, clock_out)
        if dt_out < dt_in:
            dt_out += timedelta(days=1)
        duration_seconds = (dt_out - dt_in).total_seconds()
        hours = duration_seconds / 3600.0
        return Decimal(f"{hours:.2f}")

    @classmethod
    def process_shift_record(cls, attendance):
        m_hours = cls.calculate_hours(attendance.clock_in, attendance.morning_clock_out)
        e_hours = cls.calculate_hours(attendance.evening_clock_in, attendance.clock_out)
        attendance.morning_hours = m_hours
        attendance.evening_hours = e_hours
        attendance.total_hours = m_hours + e_hours
        attendance.save()
        return attendance

    @staticmethod
    def is_late(shift_type, clock_in_time):
        if not clock_in_time:
            return False
        scheduled = MORNING_START if shift_type == 'morning' else EVENING_START
        dummy_date = timezone.now().date()
        dt_scheduled = datetime.combine(dummy_date, scheduled) + timedelta(minutes=LATE_GRACE_MINUTES)
        dt_actual = datetime.combine(dummy_date, clock_in_time)
        return dt_actual > dt_scheduled

