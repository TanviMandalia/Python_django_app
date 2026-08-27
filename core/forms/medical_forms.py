from django import forms
from core.models import SessionNote


class SessionNoteForm(forms.ModelForm):
    class Meta:
        model = SessionNote
        fields = ['patient', 'appointment', 'date', 'diagnosis', 'treatment', 'next_session']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'appointment': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Clinical diagnosis findings...'}),
            'treatment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Therapy performed, modalities, exercises...'}),
            'next_session': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Next session plan or date...'}),
        }
