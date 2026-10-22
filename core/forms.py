from django import forms
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from .models import Blog, PublicAppointmentRequest, Review, Treatment
from .appointment_slots import get_clinic_now, normalize_slot_time, format_slot_for_display

class BlogForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = ['title', 'content', 'image']


PUBLIC_TIME_SLOT_CHOICES = [
    ("", "-- Select Preferred Time Slot --"),
    (
        "Morning Shift (10:00 AM – 1:00 PM)",
        (
            ("10:00 AM", "10:00 AM"),
            ("10:30 AM", "10:30 AM"),
            ("11:00 AM", "11:00 AM"),
            ("11:30 AM", "11:30 AM"),
            ("12:00 PM", "12:00 PM"),
            ("12:30 PM", "12:30 PM"),
        ),
    ),
    (
        "Evening Shift (4:00 PM – 8:00 PM)",
        (
            ("04:00 PM", "04:00 PM"),
            ("04:30 PM", "04:30 PM"),
            ("05:00 PM", "05:00 PM"),
            ("05:30 PM", "05:30 PM"),
            ("06:00 PM", "06:00 PM"),
            ("06:30 PM", "06:30 PM"),
            ("07:00 PM", "07:00 PM"),
            ("07:30 PM", "07:30 PM"),
        ),
    ),
]


class PublicAppointmentRequestForm(forms.ModelForm):
    """
    Dedicated form for public website visitors to request an appointment.
    Requires no user authentication, account, or password.
    Includes comprehensive server-side validation and anti-spam protection.
    """
    # Honeypot field for bot spam deterrence
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off", "style": "display:none !important;"}),
    )

    consent = forms.BooleanField(
        required=True,
        error_messages={"required": "You must agree to be contacted regarding your appointment request and confirm you have read the privacy notice."},
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_consent", "required": True}),
    )

    email = forms.EmailField(
        required=True,
        error_messages={
            "required": "Please provide a valid email address.",
            "invalid": "Please provide a valid email address format.",
        },
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "id": "id_email",
            "placeholder": "e.g., rajesh@example.com",
            "autocomplete": "email",
            "required": True,
        }),
    )

    preferred_contact_method = forms.ChoiceField(
        choices=PublicAppointmentRequest.CONTACT_METHOD_CHOICES,
        initial="phone",
        required=False,
        widget=forms.RadioSelect(attrs={"class": "contact-method-radio"}),
    )

    class Meta:
        model = PublicAppointmentRequest
        fields = [
            "patient_name",
            "email",
            "phone",
            "preferred_date",
            "preferred_time",
            "service_or_reason",
            "preferred_contact_method",
        ]
        widgets = {
            "patient_name": forms.TextInput(attrs={
                "class": "form-control",
                "id": "id_patient_name",
                "placeholder": "e.g., Rajesh Patel",
                "autocomplete": "name",
                "required": True,
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "id": "id_email",
                "placeholder": "e.g., rajesh@example.com",
                "autocomplete": "email",
                "required": True,
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "id": "id_phone",
                "placeholder": "e.g., +91 94095 10501",
                "autocomplete": "tel",
                "required": True,
            }),
            "preferred_date": forms.DateInput(attrs={
                "class": "form-control",
                "id": "id_preferred_date",
                "type": "date",
                "required": True,
            }),
            "preferred_time": forms.Select(choices=PUBLIC_TIME_SLOT_CHOICES, attrs={
                "class": "form-control",
                "id": "id_preferred_time",
                "required": True,
            }),
            "service_or_reason": forms.Textarea(attrs={
                "class": "form-control",
                "id": "id_service_or_reason",
                "rows": 3,
                "maxlength": "500",
                "placeholder": "Briefly mention treatment required or symptoms (e.g., Back pain, Frozen shoulder, Knee rehab). Max 500 characters.",
            }),
            "preferred_contact_method": forms.RadioSelect(attrs={
                "class": "contact-method-radio",
            }),
        }

    def clean_website(self):
        val = self.cleaned_data.get("website", "").strip()
        if val:
            raise ValidationError("Automated submission detected.")
        return val

    def clean_patient_name(self):
        name = self.cleaned_data.get("patient_name", "").strip()
        if not name:
            raise ValidationError("Please provide the patient full name.")
        if len(name) < 2:
            raise ValidationError("Full name must be at least 2 characters.")
        if len(name) > 120:
            raise ValidationError("Full name cannot exceed 120 characters.")
        if re.search(r"[\r\n]", name):
            raise ValidationError("Invalid newline characters in patient name.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Please provide a valid email address.")
        if re.search(r"[\r\n]", email):
            raise ValidationError("Forbidden characters in email address.")
        try:
            django_validate_email(email)
        except ValidationError:
            raise ValidationError("Please provide a valid email address format.")
        if len(email) > 254:
            raise ValidationError("Email address exceeds maximum allowable length.")
        return email

    def clean_phone(self):
        raw_phone = self.cleaned_data.get("phone", "").strip()
        if not raw_phone:
            raise ValidationError("Please provide a contact phone number.")
        if re.search(r"[\r\n]", raw_phone):
            raise ValidationError("Forbidden characters in phone number.")
        digits = re.sub(r"[^\d]", "", raw_phone)
        if len(digits) < 7 or len(digits) > 15:
            raise ValidationError("Please enter a valid phone number (between 7 and 15 digits).")
        return raw_phone

    def clean_preferred_date(self):
        pref_date = self.cleaned_data.get("preferred_date")
        if not pref_date:
            raise ValidationError("Please choose an appointment date.")
        now_kolkata = get_clinic_now()
        today_kolkata = now_kolkata.date()
        if pref_date < today_kolkata:
            raise ValidationError("Cannot request an appointment for a past date.")
        return pref_date

    def clean_preferred_time(self):
        pref_time = self.cleaned_data.get("preferred_time", "").strip()
        if not pref_time:
            raise ValidationError("Please select a preferred clinic time slot.")
        norm = normalize_slot_time(pref_time)
        if not norm:
            raise ValidationError("Please select a valid clinic time slot from the list.")
        return format_slot_for_display(norm)

    def clean_service_or_reason(self):
        reason = self.cleaned_data.get("service_or_reason", "").strip()
        if reason and len(reason) > 500:
            raise ValidationError("Appointment reason cannot exceed 500 characters.")
        return reason

    def clean_preferred_contact_method(self):
        val = self.cleaned_data.get("preferred_contact_method")
        return val or "phone"

    def clean(self):
        cleaned_data = super().clean()
        pref_date = cleaned_data.get("preferred_date")
        pref_time = cleaned_data.get("preferred_time")

        if pref_date and pref_time:
            now_kolkata = get_clinic_now()
            today_kolkata = now_kolkata.date()
            if pref_date == today_kolkata:
                norm = normalize_slot_time(pref_time)
                if norm:
                    slot_hour, slot_minute = map(int, norm.split(":"))
                    from datetime import time as dt_time
                    if now_kolkata.time() >= dt_time(slot_hour, slot_minute):
                        self.add_error(
                            "preferred_time",
                            f"The {format_slot_for_display(norm)} time slot has already passed for today. Please select an upcoming slot.",
                        )
        return cleaned_data


class PublicReviewForm(forms.ModelForm):
    """
    Public-facing review submission form for Dr. Dhvani Patalia Physio Rehab.
    Requires no user authentication. Includes CSRF resilience, anti-spam honeypot,
    strict input sanitization, separate consent to publish, and pending moderation flag.
    """
    # Anti-spam honeypot
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off", "style": "display:none !important;"}),
    )

    reviewer_name = forms.CharField(
        required=False,
        max_length=100,
        label="Your Name",
        widget=forms.TextInput(attrs={
            "class": "review-form-input",
            "placeholder": "e.g. Anjali Mehta (leave blank to post as Verified Patient)",
            "autocomplete": "name",
            "id": "id_reviewer_name",
        }),
    )

    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        initial=5,
        label="Your Rating (1 to 5 Stars)",
        widget=forms.HiddenInput(attrs={"id": "id_rating_input"}),
    )

    treatment = forms.ModelChoiceField(
        queryset=Treatment.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="-- Select Therapy / Treatment (Optional) --",
        label="Treatment Received",
        widget=forms.Select(attrs={
            "class": "review-form-select",
            "id": "id_treatment",
        }),
    )

    message = forms.CharField(
        min_length=10,
        max_length=2000,
        label="Your Review & Experience",
        widget=forms.Textarea(attrs={
            "class": "review-form-textarea",
            "rows": 4,
            "placeholder": "Tell us about your recovery journey with Dr. Dhvani Patalia, the care received, or suggestions for our clinic...",
            "id": "id_message",
            "required": True,
        }),
        error_messages={
            "required": "Please provide a brief description of your experience.",
            "min_length": "Please provide at least 10 characters describing your experience.",
            "max_length": "Review text cannot exceed 2000 characters.",
        },
    )

    consent_to_publish = forms.BooleanField(
        required=False,
        initial=True,
        label="I consent to displaying this review publicly on the clinic website (no sensitive medical records will ever be shared).",
        widget=forms.CheckboxInput(attrs={
            "class": "review-checkbox-input",
            "id": "id_consent_to_publish",
        }),
    )

    class Meta:
        model = Review
        fields = ["reviewer_name", "rating", "treatment", "message", "consent_to_publish"]

    def clean_website(self):
        val = self.cleaned_data.get("website", "").strip()
        if val:
            raise ValidationError("Spam submission detected.")
        return val

    def clean_reviewer_name(self):
        name = self.cleaned_data.get("reviewer_name", "").strip()
        if not name:
            return "Verified Patient"
        # Sanitize against script injection and tags
        name = re.sub(r"<[^>]*>", "", name).strip()
        if not name:
            return "Verified Patient"
        if len(name) > 100:
            name = name[:100]
        return name

    def clean_message(self):
        msg = self.cleaned_data.get("message", "").strip()
        # Strip dangerous HTML tags
        clean_msg = re.sub(r"<[^>]*>", "", msg).strip()
        if len(clean_msg) < 10:
            raise ValidationError("Please provide at least 10 characters describing your experience.")
        return clean_msg

    def clean_rating(self):
        r = self.cleaned_data.get("rating", 5)
        try:
            r = int(r)
        except (ValueError, TypeError):
            r = 5
        if r < 1 or r > 5:
            raise ValidationError("Rating must be between 1 and 5 stars.")
        return r


