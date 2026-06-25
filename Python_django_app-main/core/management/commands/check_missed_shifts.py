# core/management/commands/check_missed_shifts.py — COMPLETE FILE

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import time as dtime
from core.models import Attendance, LeaveApplication

MORNING_END  = dtime(13, 0)
EVENING_END  = dtime(20, 0)


class Command(BaseCommand):
    help = 'Check missed shifts, auto-mark leaves, auto-approve expired leaves'

def handle(self, *args, **kwargs):
    today     = timezone.localdate()
    now_time  = timezone.localtime(timezone.now()).time()
    staff_users = User.objects.filter(is_staff=True, is_superuser=False)

    for user in staff_users:
        if not user.email:
            continue

        record = Attendance.objects.filter(staff=user, date=today).first()

        # ── After morning ends ──────────────────────────────
        if now_time > MORNING_END:
            if not record or not record.clock_in:
                # Morning missed — mark first half leave
                att, _ = Attendance.objects.get_or_create(
                    staff=user, date=today
                )
                if 'First Half Leave' not in att.notes:
                    att.notes = (att.notes + ' First Half Leave (Morning shift missed).').strip()
                    att.save()
                    LeaveApplication.objects.get_or_create(
                        staff=user,
                        from_date=today,
                        to_date=today,
                        defaults={
                            'leave_type': 'casual',
                            'reason': 'Auto-marked: First Half Leave (morning shift missed)',
                            'status': 'pending',
                        }
                    )
                    self._send_missed_email(user, 'Morning', '10:00 AM – 1:00 PM', 'First')
                    self.stdout.write(f'  ❌ First half leave: {user.username}')

            elif record and record.clock_in and not record.morning_clock_out:
                # Clocked in but forgot to clock out morning
                self._send_forgot_clockout(user, 'Morning')
                self.stdout.write(f'  ⚠️ Forgot morning clock-out: {user.username}')

        # ── After evening ends ──────────────────────────────
        if now_time > EVENING_END:
            if not record or not record.evening_clock_in:
                # Evening missed — mark second half leave
                att, _ = Attendance.objects.get_or_create(
                    staff=user, date=today
                )
                if 'Second Half Leave' not in att.notes:
                    att.notes = (att.notes + ' Second Half Leave (Evening shift missed).').strip()
                    att.save()
                    # Only create leave if not already full day absent
                    if 'First Half Leave' not in att.notes:
                        LeaveApplication.objects.get_or_create(
                            staff=user,
                            from_date=today,
                            to_date=today,
                            defaults={
                                'leave_type': 'casual',
                                'reason': 'Auto-marked: Second Half Leave (evening shift missed)',
                                'status': 'pending',
                            }
                        )
                    self._send_missed_email(user, 'Evening', '4:00 PM – 8:00 PM', 'Second')
                    self.stdout.write(f'  ❌ Second half leave: {user.username}')

            elif record and record.evening_clock_in and not record.clock_out:
                # Clocked in evening but forgot to clock out
                self._send_forgot_clockout(user, 'Evening')
                self.stdout.write(f'  ⚠️ Forgot evening clock-out: {user.username}')

        self.stdout.write(f'✅ Checked: {user.username}')

    self.stdout.write(self.style.SUCCESS('Done checking all shifts.'))
    
def _auto_approve_expired_leaves(self):
        today = timezone.localdate()
        expired = LeaveApplication.objects.filter(
            status='pending',
            to_date__lt=today
        )
        for leave in expired:
            leave.status     = 'approved'
            leave.admin_note = 'Auto-approved: Admin did not respond before leave date.'
            leave.save()
            self._send_auto_approved_email(leave)
            self.stdout.write(
                f'  ✅ Auto-approved leave: {leave.staff.username} '
                f'({leave.from_date} – {leave.to_date})'
            )

def _send_missed_email(self, user, shift, timing, half):
    try:
        send_mail(
            subject=f'📋 {half} Half Leave Auto-Marked — {shift} Shift Missed',
            message=f"""
Dear {user.get_full_name() or user.username},

Since you missed the {shift} shift today, your attendance
has been automatically marked as {half.upper()} HALF LEAVE.

  Date          : {timezone.localdate().strftime('%d %B %Y')}
  Missed Shift  : {shift} ({timing})
  Status        : {half} Half Leave (Pending Admin Approval)

A leave application has been auto-submitted on your behalf.
If this was an error, please contact admin to correct your record.

Shift Timings:
  Morning  — 10:00 AM to 1:00 PM
  Evening  — 4:00 PM to 8:00 PM

Regards,
Dr. Dhvani Patalia
Physio Rehab Clinic
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        self.stdout.write(f'  Email failed for {user.username}: {e}')

def _send_forgot_clockout(self, user, shift):
        try:
            send_mail(
                subject=f'⚠️ Forgot to Clock Out — {shift} Shift',
                message=f"""
Dear {user.get_full_name() or user.username},

It appears you FORGOT TO CLOCK OUT from the {shift} Shift today.

  Shift : {shift}
  Date  : {timezone.localdate().strftime('%d %B %Y')}

Please log in and clock out, or contact admin to fix your record.

Regards,
Dr. Dhvani Patalia
Physio Rehab Clinic
                """.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            self.stdout.write(f'  Email failed for {user.username}: {e}')

def _send_auto_approved_email(self, leave):
        try:
            send_mail(
                subject='✅ Leave Auto-Approved — No Admin Response',
                message=f"""
Dear {leave.staff.get_full_name() or leave.staff.username},

Your leave application has been AUTOMATICALLY APPROVED because
the admin did not respond before your leave date passed.

  Leave Type  : {leave.get_leave_type_display()}
  From Date   : {leave.from_date.strftime('%d %B %Y')}
  To Date     : {leave.to_date.strftime('%d %B %Y')}
  Reason      : {leave.reason}
  Note        : Admin did not respond before leave date.

Regards,
Dr. Dhvani Patalia
Physio Rehab Clinic
                """.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[leave.staff.email],
                fail_silently=True,
            )
        except Exception as e:
            self.stdout.write(f'  Auto-approve email failed: {e}')