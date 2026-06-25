---
name: Stripe integration
description: Stripe payment setup for PhysioRehab — keys, model, views, and webhook.
---
**Rule:** Stripe secret key read from env `STRIPE_SECRET_KEY`. Publishable key from `STRIPE_PUBLISHABLE_KEY`. Webhook secret from `STRIPE_WEBHOOK_SECRET`. UPI ID from `CLINIC_UPI_ID`.

**Why:** Keys must never be hardcoded. Settings.py reads from os.environ with empty fallback.

**How to apply:** 
- PaymentRecord model in core/models.py handles cash/upi/netbanking/stripe.
- Views: stripe_checkout, stripe_success, stripe_cancel, stripe_webhook, record_cash_payment, record_upi_payment, admin_payments.
- URLs at /payments/stripe-checkout/, /payments/record-cash/, /payments/record-upi/, /payments/admin/.
- Stripe uses INR currency with `stripe.checkout.Session.create`.
- To activate: set STRIPE_PUBLISHABLE_KEY and STRIPE_SECRET_KEY env secrets in Replit.
