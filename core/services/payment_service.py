import hmac
import hashlib
import logging
from decimal import Decimal
from django.conf import settings
from core.models import PaymentRecord, ClinicSubscriptionPayment, Hospital, Appointment

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def get_razorpay_client(hospital=None):
        try:
            import razorpay
            key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
            key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

            if hospital and hospital.razorpay_key_id and hospital.razorpay_key_secret:
                key_id = hospital.razorpay_key_id
                key_secret = hospital.razorpay_key_secret

            if not key_id or not key_secret:
                return None

            return razorpay.Client(auth=(key_id, key_secret))
        except ImportError:
            logger.warning("razorpay package not installed or failed to import.")
            return None

    @classmethod
    def create_razorpay_order(cls, amount_inr, receipt_id, currency="INR", hospital=None):
        client = cls.get_razorpay_client(hospital)
        amount_paise = int(Decimal(str(amount_inr)) * 100)
        data = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": str(receipt_id),
            "payment_capture": 1
        }
        if client:
            try:
                order = client.order.create(data=data)
                return order
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}")
        return {
            "id": f"order_sim_{receipt_id}_{amount_paise}",
            "amount": amount_paise,
            "currency": currency,
            "status": "created"
        }

    @classmethod
    def verify_payment_signature(cls, order_id, payment_id, signature, hospital=None):
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        if hospital and hospital.razorpay_key_secret:
            key_secret = hospital.razorpay_key_secret

        if not key_secret:
            return True

        msg = f"{order_id}|{payment_id}".encode('utf-8')
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(generated_signature, signature)

