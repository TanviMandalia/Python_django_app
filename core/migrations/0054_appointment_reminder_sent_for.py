from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0053_alter_emailaccount_provider_gmailoauthcredential"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="reminder_sent_for",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
