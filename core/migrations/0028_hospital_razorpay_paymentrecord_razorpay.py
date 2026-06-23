from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_clinic_subscription_payment'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='razorpay_key_id',
            field=models.CharField(
                blank=True,
                help_text="Doctor/Clinic Razorpay Key ID — patient payments go to this account",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='hospital',
            name='razorpay_key_secret',
            field=models.CharField(
                blank=True,
                help_text="Doctor/Clinic Razorpay Key Secret",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='razorpay_order_id',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='razorpay_signature',
            field=models.CharField(blank=True, max_length=400),
        ),
        migrations.RemoveField(
            model_name='paymentrecord',
            name='stripe_payment_intent',
        ),
        migrations.RemoveField(
            model_name='paymentrecord',
            name='stripe_session_id',
        ),
        migrations.AlterField(
            model_name='paymentrecord',
            name='method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('upi', 'UPI / QR Code'),
                    ('netbanking', 'Net Banking'),
                    ('razorpay', 'Online (Razorpay)'),
                    ('wallet', 'Wallet'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='clinicsubscriptionpayment',
            name='method',
            field=models.CharField(
                choices=[
                    ('upi', 'UPI / QR Code'),
                    ('cash', 'Cash'),
                    ('netbanking', 'Net Banking / NEFT'),
                    ('razorpay', 'Online (Razorpay)'),
                ],
                default='upi',
                max_length=20,
            ),
        ),
    ]
