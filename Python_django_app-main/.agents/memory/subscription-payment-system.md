---
name: Clinic Subscription Payment System
description: How clinic admins pay for plans and how super admin verifies/activates subscriptions.
---
**Rule:** ClinicSubscriptionPayment model (migration 0027) tracks every plan payment per hospital — separate from PatientPaymentRecord.

**Flow:**
1. Doctor (clinic admin) visits /subscription/ → selects Basic/Standard/Premium plan → picks UPI/Cash/Net Banking → submits txn ID → creates ClinicSubscriptionPayment(status='pending')
2. Super admin visits /super-admin/subscriptions/ → sees "Pending Verification" tab with alert count → clicks Confirm → activates HospitalSubscription with expiry = today + duration_months using python-dateutil relativedelta
3. Per-hospital full payment history at /super-admin/hospitals/<id>/payments/

**Key URLs:**
- /subscription/ — doctor's plan page (POST creates pending payment)
- /super-admin/subscriptions/ — tabbed: Pending | Clinic Status | All Subs | Manage Plans
- /super-admin/subscriptions/confirm/<id>/ — confirm payment → activate sub
- /super-admin/subscriptions/reject/<id>/ — reject payment
- /super-admin/hospitals/<id>/payments/ — full clinic payment history

**Plans seeded:** basic ₹500, standard ₹1200, premium ₹2500 — seeded via shell after migration 0027.

**Template filter:** `get_item` added to core/templatetags/custom_filters.py for dict lookup in templates. Use {% load custom_filters %} in templates needing it.

**Why:** Previously subscription page only showed an alert popup — no real payment flow. No tracking of which clinic paid. Premium plan didn't exist in DB.

**How to apply:** python-dateutil must be installed (pip install python-dateutil). Already installed in this environment.
