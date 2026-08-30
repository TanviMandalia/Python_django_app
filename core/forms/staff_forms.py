from django import forms
from core.models import LeaveApplication, DailyTask, StaffProfile, Attendance, SalaryRecord


class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = ['leave_type', 'from_date', 'to_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'from_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'to_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for leave...'}),
        }


class DailyTaskForm(forms.ModelForm):
    class Meta:
        model = DailyTask
        fields = ['assigned_to', 'title', 'description', 'priority', 'due_date']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Task description...'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = StaffProfile
        fields = ['role', 'phone', 'address', 'salary', 'joining_date', 'is_active']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = [
            'staff', 'date', 'clock_in', 'morning_clock_out',
            'evening_clock_in', 'clock_out', 'notes'
        ]
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'clock_in': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'morning_clock_out': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'evening_clock_in': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'clock_out': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SalaryRecordForm(forms.ModelForm):
    class Meta:
        model = SalaryRecord
        fields = ['staff', 'month', 'year', 'basic_salary', 'bonus', 'deduction', 'net_salary', 'paid_on', 'is_paid', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'month': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'basic_salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'bonus': forms.NumberInput(attrs={'class': 'form-control'}),
            'deduction': forms.NumberInput(attrs={'class': 'form-control'}),
            'net_salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'paid_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

