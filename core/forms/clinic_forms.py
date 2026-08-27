from django import forms
from core.models import Blog, ClinicSettings, Review, ClinicPromo


class BlogForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = [
            'title', 'excerpt', 'category', 'content',
            'image', 'before_image', 'after_image'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter blog title'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Short summary...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Full article content...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'before_image': forms.FileInput(attrs={'class': 'form-control'}),
            'after_image': forms.FileInput(attrs={'class': 'form-control'}),
        }


class ClinicSettingsForm(forms.ModelForm):
    class Meta:
        model = ClinicSettings
        fields = '__all__'
        widgets = {
            'clinic_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'appointment_fee': forms.NumberInput(attrs={'class': 'form-control'}),
            'followup_fee': forms.NumberInput(attrs={'class': 'form-control'}),
            'session_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'opening_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
            'enable_chat': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_payments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_otp_reset': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['reviewer_name', 'reviewer_title', 'rating', 'message']
        widgets = {
            'reviewer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}),
            'reviewer_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Patient / Athlete'}),
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your recovery story...'}),
        }


class PromoForm(forms.ModelForm):
    class Meta:
        model = ClinicPromo
        fields = ['title', 'message', 'is_active', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Promo headline'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Promo announcement text...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
