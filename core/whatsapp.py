"""
WhatsApp Integration Module for Physiotherapy Clinic Management.
Provides secure, reliable WhatsApp Click-to-Chat URL generation, message formatting,
destination number validation, and two-way clinic communication helpers.
"""
import os
import re
import urllib.parse
from django.conf import settings


def sanitize_phone_to_international(raw_phone):
    """
    Sanitize phone number to international format (digits only, no '+', spaces, or dashes).
    If a 10-digit Indian number is provided without country code, prepends '91'.
    Returns empty string if invalid or fewer than 7 digits.
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"[^\d]", "", str(raw_phone).strip())
    # If 10 digits starting with valid Indian mobile prefixes (6-9), prepend 91
    if len(digits) == 10 and digits[0] in ("6", "7", "8", "9"):
        digits = f"91{digits}"
    # Valid international phone numbers are between 7 and 15 digits (E.164 standard)
    if 7 <= len(digits) <= 15:
        return digits
    return ""


def get_doctor_whatsapp_number():
    """
    Retrieve configured Doctor/Admin WhatsApp destination number from settings/environment.
    Returns cleaned international digits string (e.g. '919409510501') or empty string if not configured.
    Never invents or hardcodes a default phone number.
    """
    configured = (
        getattr(settings, "DOCTOR_WHATSAPP_NUMBER", None)
        or os.getenv("DOCTOR_WHATSAPP_NUMBER", "")
        or getattr(settings, "CLINIC_WHATSAPP_NUMBER", None)
        or os.getenv("CLINIC_WHATSAPP_NUMBER", "")
    )
    if not configured:
        # Fallback to CLINIC_WHATSAPP if explicitly declared in settings
        configured = getattr(settings, "CLINIC_WHATSAPP", "")
    return sanitize_phone_to_international(configured)


def build_whatsapp_appointment_message(booking_obj):
    """
    Generate professional, minimal WhatsApp message text for a PublicAppointmentRequest.
    Contains only essential scheduling details (zero sensitive diagnostic or clinical records).
    """
    ref = getattr(booking_obj, "reference_id", "") or "Pending"
    patient_name = getattr(booking_obj, "patient_name", "") or "Visitor"
    phone = getattr(booking_obj, "phone", "") or "Not provided"
    email = getattr(booking_obj, "email", "") or "Not provided"

    pref_date = getattr(booking_obj, "preferred_date", None)
    if pref_date:
        if hasattr(pref_date, "strftime"):
            date_str = pref_date.strftime("%d %B %Y")
        else:
            date_str = str(pref_date)
    else:
        date_str = "Not specified"

    pref_time = getattr(booking_obj, "preferred_time", "") or "Not specified"
    reason = getattr(booking_obj, "service_or_reason", "")
    reason_str = reason.strip() if reason else "General Consultation"

    if hasattr(booking_obj, "get_preferred_contact_method_display"):
        contact_method = booking_obj.get_preferred_contact_method_display()
    else:
        contact_method = getattr(booking_obj, "preferred_contact_method", "Phone Call") or "Phone Call"

    message = (
        f"New Appointment Request\n"
        f"Reference: {ref}\n"
        f"Patient Name: {patient_name}\n"
        f"Phone: {phone}\n"
        f"Email: {email}\n"
        f"Preferred Date: {date_str}\n"
        f"Preferred Time: {pref_time}\n"
        f"Reason for Visit: {reason_str}\n"
        f"Preferred Contact Method: {contact_method}\n"
        f"Status: Pending Confirmation\n\n"
        f"Please review this request and contact the patient to confirm availability."
    )
    return message


def build_whatsapp_click_to_chat_url(booking_obj):
    """
    Generate the safe https://wa.me/ click-to-chat URL for an appointment request.
    Returns (url: str, is_configured: bool).
    If the destination number is not configured, returns ('', False).
    """
    dest_number = get_doctor_whatsapp_number()
    if not dest_number:
        return "", False

    raw_message = build_whatsapp_appointment_message(booking_obj)
    encoded_message = urllib.parse.quote(raw_message, safe="")
    url = f"https://wa.me/{dest_number}?text={encoded_message}"
    return url, True


def build_doctor_to_patient_whatsapp_url(record):
    """
    Generate click-to-chat URL for Doctor/Admin to contact patient regarding their request or appointment.
    Supports both PublicAppointmentRequest and Appointment models.
    """
    patient_phone = getattr(record, "phone", "")
    digits = sanitize_phone_to_international(patient_phone)
    if not digits:
        return ""

    patient_name = getattr(record, "patient_name", "") or getattr(record, "name", "Patient")
    ref = getattr(record, "reference_id", None)
    pref_date = getattr(record, "preferred_date", None) or getattr(record, "date", None)
    date_str = pref_date.strftime("%d %b %Y") if hasattr(pref_date, "strftime") else str(pref_date)

    if ref:
        text = (
            f"Hello {patient_name}, this is Dr. Dhvani Patalia Physio Rehab regarding "
            f"your appointment request {ref} for {date_str}. We are contacting you to confirm your consultation availability."
        )
    else:
        text = (
            f"Hello {patient_name}, this is Dr. Dhvani Patalia Physio Rehab regarding "
            f"your physiotherapy appointment scheduled for {date_str}. Please let us know if you have any questions."
        )

    encoded_text = urllib.parse.quote(text, safe="")
    return f"https://wa.me/{digits}?text={encoded_text}"
