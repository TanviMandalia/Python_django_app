import hmac
import hashlib
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.conf import settings
from core.services.payment_service import PaymentService


class PaymentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            username="patient_pay", email="pay@test.com", password="pass"
        )
        self.admin = User.objects.create_user(
            username="admin_pay", email="adminpay@test.com", password="pass", is_superuser=True, is_staff=True
        )

    def test_create_razorpay_order_simulation(self):
        order = PaymentService.create_razorpay_order(amount_inr=500, receipt_id="test_receipt_1")
        self.assertIn("id", order)
        self.assertEqual(order["amount"], 50000)

    def test_verify_signature_mock(self):
        order_id = "order_999"
        payment_id = "pay_999"
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'SampleKeySecret12345')

        # Generate correct HMAC SHA256 signature
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg,
            hashlib.sha256
        ).hexdigest()

        # Valid signature verification test
        result = PaymentService.verify_payment_signature(order_id, payment_id, valid_signature)
        self.assertTrue(result)

        # Invalid signature test
        invalid_result = PaymentService.verify_payment_signature(order_id, payment_id, "invalid_sig_abc")
        self.assertFalse(invalid_result)

