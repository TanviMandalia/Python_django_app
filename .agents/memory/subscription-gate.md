---
name: Subscription gate
description: Middleware blocks expired clinic-admin access; email warning sent 5 days before expiry.
---
**Rule:** SubscriptionGateMiddleware redirects to /subscription/ when clinic admin's HospitalSubscription is expired. Platform superadmins (is_platform_admin=True) are always exempt.

**Why:** Without subscription, clinic features should be locked behind a paywall/renewal page.

**How to apply:**
- Both middleware classes in core/middleware.py.
- Added at end of MIDDLEWARE list in settings.py.
- Exempt paths: /login/, /logout/, /register/, /forgot-password/, /verify-otp/, /reset-password/, /resend-otp/, /subscription/, /super-admin/, /support/submit/.
- Email warning uses send_subscription_expiry_warning_email() from core/email_utils.py.
- Cron command: `python manage.py check_subscription_expiry` — marks expired, sends 5-day warnings.
