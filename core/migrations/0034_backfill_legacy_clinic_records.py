# Generated for safe legacy clinic data backfill

from django.db import migrations


def backfill_legacy_records(apps, schema_editor):
    Hospital = apps.get_model("core", "Hospital")
    default_hospital = Hospital.objects.order_by("id").first()
    if not default_hospital:
        return

    models_to_backfill = [
        "DailyTask",
        "StaffProfile",
        "Attendance",
        "LeaveApplication",
        "SalaryRecord",
        "SessionNote",
        "Appointment",
        "PaymentRecord",
        "ClinicPromo",
        "UserRole",
        "Blog",
        "Review",
        "Message",
        "Notification",
    ]
    for model_name in models_to_backfill:
        try:
            Model = apps.get_model("core", model_name)
            Model.objects.filter(hospital_id__isnull=True).update(hospital_id=default_hospital.id)
        except Exception:
            pass

    try:
        ClinicSettings = apps.get_model("core", "ClinicSettings")
        if ClinicSettings.objects.filter(hospital_id=default_hospital.id).exists():
            ClinicSettings.objects.filter(hospital_id__isnull=True).delete()
        else:
            ClinicSettings.objects.filter(hospital_id__isnull=True).update(hospital_id=default_hospital.id)
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_emaillog_inboundemail'),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_records, reverse_code=migrations.RunPython.noop),
    ]
