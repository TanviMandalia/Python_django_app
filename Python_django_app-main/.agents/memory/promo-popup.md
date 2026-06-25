---
name: Promo popup system
description: Doctor sees festival/scheme announcements as dismissable popups on admin dashboard.
---
**Rule:** ClinicPromo model (migration 0026) stores promos. admin_dashboard view passes active_promos (filtered by is_live property and session dismissed_promos list). JS popup dismisses via POST to /api/promos/dismiss/.

**Why:** Doctor needs to see clinic-wide announcements (festivals, schemes) without missing them.

**How to apply:**
- Create promos at /admin-promos/add/ (admin only).
- Promos show on admin_dashboard.html as overlay modal on login.
- Dismiss stores promo_id in session['dismissed_promos'].
- is_live property checks is_active + start_date <= today <= end_date.
