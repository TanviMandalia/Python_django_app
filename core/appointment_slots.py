"""
Dr. Dhvani Patalia Physio Rehab - Centralized Appointment Slot & Schedule Engine

Working Hours:
  - Monday to Friday:
      Morning Shift: 10:00 AM – 1:00 PM
      Evening Shift:  4:00 PM – 8:00 PM
  - Sunday: By Appointment (restricted public booking)
  - Saturday: Closed by default

Standard Appointment Slots (Start Times):
  - Morning:
      10:00 AM (10:00)
      10:30 AM (10:30)
      11:00 AM (11:00)
      11:30 AM (11:30)
      12:00 PM (12:00)
      12:30 PM (12:30)
  - Evening:
      04:00 PM (16:00 / 04:00)
      04:30 PM (16:30 / 04:30)
      05:00 PM (17:00 / 05:00)
      05:30 PM (17:30 / 05:30)
      06:00 PM (18:00 / 06:00)
      06:30 PM (18:30 / 06:30)
      07:00 PM (19:00 / 07:00)
      07:30 PM (19:30 / 07:30)

Explicitly Rejected Times:
  09:59 AM, 01:00 PM, 03:59 PM, 08:00 PM, 10:15 AM, 10:45 AM, 11:15 AM, 03:30 PM, 04:15 PM, etc.
"""

from datetime import datetime, date, time
from typing import List, Dict, Tuple, Optional, Any
from zoneinfo import ZoneInfo
from django.db.models import Q

CLINIC_TIMEZONE = ZoneInfo("Asia/Kolkata")

MORNING_SHIFT = {
    "name": "Morning Shift",
    "start_time": time(10, 0),
    "end_time": time(13, 0),
    "slots": [
        ("10:00", "10:00 AM"),
        ("10:30", "10:30 AM"),
        ("11:00", "11:00 AM"),
        ("11:30", "11:30 AM"),
        ("12:00", "12:00 PM"),
        ("12:30", "12:30 PM"),
    ],
}

EVENING_SHIFT = {
    "name": "Evening Shift",
    "start_time": time(16, 0),
    "end_time": time(20, 0),
    "slots": [
        ("16:00", "04:00 PM"),
        ("16:30", "04:30 PM"),
        ("17:00", "05:00 PM"),
        ("17:30", "05:30 PM"),
        ("18:00", "06:00 PM"),
        ("18:30", "06:30 PM"),
        ("19:00", "07:00 PM"),
        ("19:30", "07:30 PM"),
    ],
}

ALL_STANDARD_SLOTS = MORNING_SHIFT["slots"] + EVENING_SHIFT["slots"]
VALID_SLOT_CODES = [slot[0] for slot in ALL_STANDARD_SLOTS]

MORNING_SLOTS = [s[1] for s in MORNING_SHIFT["slots"]]
EVENING_SLOTS = [s[1] for s in EVENING_SHIFT["slots"]]
CLINIC_SLOTS = MORNING_SLOTS + EVENING_SLOTS

# Map aliases and variations (e.g. 12h vs 24h, with or without AM/PM)
SLOT_CANONICAL_MAP = {
    # Morning
    "10:00": "10:00",
    "10:00 AM": "10:00",
    "10:00:00": "10:00",
    "10:30": "10:30",
    "10:30 AM": "10:30",
    "10:30:00": "10:30",
    "11:00": "11:00",
    "11:00 AM": "11:00",
    "11:00:00": "11:00",
    "11:30": "11:30",
    "11:30 AM": "11:30",
    "11:30:00": "11:30",
    "12:00": "12:00",
    "12:00 PM": "12:00",
    "12:00:00": "12:00",
    "12:30": "12:30",
    "12:30 PM": "12:30",
    "12:30:00": "12:30",
    # Evening 24h
    "16:00": "16:00",
    "16:00:00": "16:00",
    "16:30": "16:30",
    "16:30:00": "16:30",
    "17:00": "17:00",
    "17:00:00": "17:00",
    "17:30": "17:30",
    "17:30:00": "17:30",
    "18:00": "18:00",
    "18:00:00": "18:00",
    "18:30": "18:30",
    "18:30:00": "18:30",
    "19:00": "19:00",
    "19:00:00": "19:00",
    "19:30": "19:30",
    "19:30:00": "19:30",
    # Evening 12h
    "04:00": "16:00",
    "4:00": "16:00",
    "04:00 PM": "16:00",
    "4:00 PM": "16:00",
    "04:30": "16:30",
    "4:30": "16:30",
    "04:30 PM": "16:30",
    "4:30 PM": "16:30",
    "05:00": "17:00",
    "5:00": "17:00",
    "05:00 PM": "17:00",
    "5:00 PM": "17:00",
    "05:30": "17:30",
    "5:30": "17:30",
    "05:30 PM": "17:30",
    "5:30 PM": "17:30",
    "06:00": "18:00",
    "6:00": "18:00",
    "06:00 PM": "18:00",
    "6:00 PM": "18:00",
    "06:30": "18:30",
    "6:30": "18:30",
    "06:30 PM": "18:30",
    "6:30 PM": "18:30",
    "07:00": "19:00",
    "7:00": "19:00",
    "07:00 PM": "19:00",
    "7:00 PM": "19:00",
    "07:30": "19:30",
    "7:30": "19:30",
    "07:30 PM": "19:30",
    "7:30 PM": "19:30",
}

# Reverse mapping for 12h format stored in legacy DB if needed
CANONICAL_TO_LEGACY_MAP = {
    "16:00": "04:00",
    "16:30": "04:30",
    "17:00": "05:00",
    "17:30": "05:30",
    "18:00": "06:00",
    "18:30": "06:30",
    "19:00": "07:00",
    "19:30": "07:30",
}

CANONICAL_TO_DISPLAY_MAP = {
    "10:00": "10:00 AM",
    "10:30": "10:30 AM",
    "11:00": "11:00 AM",
    "11:30": "11:30 AM",
    "12:00": "12:00 PM",
    "12:30": "12:30 PM",
    "16:00": "04:00 PM",
    "16:30": "04:30 PM",
    "17:00": "05:00 PM",
    "17:30": "05:30 PM",
    "18:00": "06:00 PM",
    "18:30": "06:30 PM",
    "19:00": "07:00 PM",
    "19:30": "07:30 PM",
}


def format_slot_for_display(canonical_slot: str) -> str:
    """Format canonical 24h slot (e.g. '16:00') into professional 12h display ('04:00 PM')."""
    return CANONICAL_TO_DISPLAY_MAP.get(canonical_slot, canonical_slot)


def get_clinic_now() -> datetime:
    """Return the current datetime in Asia/Kolkata timezone."""
    return datetime.now(CLINIC_TIMEZONE)


def normalize_slot_time(time_str: str) -> Optional[str]:
    """
    Normalizes a given time string to standard canonical slot code (e.g. '10:00', '16:00').
    Returns None if the slot is invalid or not in standard configuration.
    """
    if not time_str:
        return None
    cleaned = str(time_str).strip().upper()
    # Direct lookup
    if cleaned in SLOT_CANONICAL_MAP:
        return SLOT_CANONICAL_MAP[cleaned]
    # Try parsing common formats
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I:%M"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            std_24 = dt.strftime("%H:%M")
            if std_24 in VALID_SLOT_CODES:
                return std_24
        except ValueError:
            continue
    return None


def get_slot_aliases(canonical_slot: str) -> List[str]:
    """Returns all representations of a slot code for DB query matching."""
    aliases = [canonical_slot]
    for k, v in SLOT_CANONICAL_MAP.items():
        if v == canonical_slot:
            aliases.append(k)
    return list(set(aliases))


def validate_appointment_booking(
    date_val: Any = None,
    time_val: Any = None,
    hospital: Optional[Any] = None,
    allow_sunday: bool = False,
    allow_saturday: bool = False,
    exclude_appointment_id: Optional[int] = None,
    *,
    date_str: Any = None,
    time_str: Any = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Validates appointment date, shift, slot, working hours, and double booking.

    Returns:
        (is_valid: bool, error_message: str, normalized_display_time: Optional[str])
    """
    if date_val is None and date_str is not None:
        date_val = date_str
    if time_val is None and time_str is not None:
        time_val = time_str

    # 1. Parse and validate date
    if not date_val:
        return False, "Please select an appointment date.", None

    parsed_date: Optional[date] = None
    if isinstance(date_val, str):
        d_str = date_val.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed_date = datetime.strptime(d_str, fmt).date()
                break
            except ValueError:
                pass
        if not parsed_date:
            return False, "Invalid date format. Please use YYYY-MM-DD.", None
    elif isinstance(date_val, datetime):
        parsed_date = date_val.date()
    elif isinstance(date_val, date):
        parsed_date = date_val
    else:
        return False, "Invalid date format.", None

    # 2. Check past date (in Asia/Kolkata)
    now_kolkata = get_clinic_now()
    today_kolkata = now_kolkata.date()

    if parsed_date < today_kolkata:
        return False, "Cannot book appointment for a past date.", None

    # 3. Check day of week
    weekday = parsed_date.weekday()  # Monday is 0, Sunday is 6
    if weekday == 6 and not allow_sunday:
        return (
            False,
            "Sunday appointments are By Appointment only. Please contact Dr. Dhvani Patalia Physio Rehab directly at 94095 10501.",
            None,
        )
    if weekday == 5 and not allow_saturday:
        return (
            False,
            "The clinic is closed on Saturdays. Working days are Monday through Friday.",
            None,
        )

    # 4. Normalize and validate time slot
    if not time_val:
        return False, "Please select an appointment time slot.", None

    canonical_time = normalize_slot_time(time_val)
    if not canonical_time:
        return (
            False,
            f"'{time_val}' is not an authorized clinic slot. Standard slots are: Morning (10:00 AM – 1:00 PM) and Evening (4:00 PM – 8:00 PM).",
            None,
        )

    # 5. Check if today and slot has already passed
    if parsed_date == today_kolkata:
        slot_hour, slot_minute = map(int, canonical_time.split(":"))
        slot_time = time(slot_hour, slot_minute)
        if now_kolkata.time() >= slot_time:
            return (
                False,
                f"The {format_slot_for_display(canonical_time)} time slot has already passed for today. Please select an upcoming slot.",
                None,
            )

    # 6. Check double-booking / availability
    from core.models import Appointment

    aliases = get_slot_aliases(canonical_time)
    booking_query = Appointment.objects.filter(
        date=parsed_date,
        time__in=aliases,
        status__in=["pending", "confirmed"],
    )
    if hospital:
        booking_query = booking_query.filter(hospital=hospital)
    if exclude_appointment_id:
        booking_query = booking_query.exclude(id=exclude_appointment_id)

    if booking_query.exists():
        display_name = format_slot_for_display(canonical_time)
        return (
            False,
            f"The selected slot ({display_name}) on {parsed_date} is already booked. Please choose another time slot.",
            None,
        )

    normalized_display = format_slot_for_display(canonical_time)
    return True, "", normalized_display


def get_available_slots_for_date(
    hospital: Any,
    target_date: date,
    allow_sunday: bool = False,
    allow_saturday: bool = False,
) -> Dict[str, Any]:
    """
    Returns the status (available, booked, past, closed) for each shift and slot.
    """
    from core.models import Appointment

    weekday = target_date.weekday()
    now_kolkata = get_clinic_now()
    today_kolkata = now_kolkata.date()

    if weekday == 6 and not allow_sunday:
        return {
            "is_closed": True,
            "status_reason": "Sunday is By Appointment only. Please call 94095 10501.",
            "morning_slots": [],
            "evening_slots": [],
        }

    if weekday == 5 and not allow_saturday:
        return {
            "is_closed": True,
            "status_reason": "Closed on Saturday. Clinic operates Monday to Friday.",
            "morning_slots": [],
            "evening_slots": [],
        }

    # Fetch all occupied slots for this hospital and date
    booked_slots = set()
    appts = Appointment.objects.filter(
        date=target_date,
        status__in=["pending", "confirmed"],
    )
    if hospital:
        appts = appts.filter(hospital=hospital)

    for a in appts:
        norm = normalize_slot_time(a.time)
        if norm:
            booked_slots.add(norm)

    def process_slots(slot_tuples):
        result = []
        for code, label in slot_tuples:
            is_past = False
            if target_date < today_kolkata:
                is_past = True
            elif target_date == today_kolkata:
                h, m = map(int, code.split(":"))
                if now_kolkata.time() >= time(h, m):
                    is_past = True

            is_booked = code in booked_slots

            status = "available"
            if is_past:
                status = "past"
            elif is_booked:
                status = "booked"

            result.append(
                {
                    "code": code,
                    "label": label,
                    "status": status,
                    "is_available": (status == "available"),
                }
            )
        return result

    return {
        "is_closed": False,
        "status_reason": "",
        "morning_slots": process_slots(MORNING_SHIFT["slots"]),
        "evening_slots": process_slots(EVENING_SHIFT["slots"]),
    }
