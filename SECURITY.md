# Security, Privacy & Access Control Architecture
**PhysioRehab Multi-Clinic SaaS Platform**

---

## 1. Security Philosophy in Healthcare SaaS

Operating a clinical physiotherapy application requires stringent confidentiality, integrity, and availability controls. The PhysioRehab platform implements defense-in-depth across the application layer, authentication pipeline, database tier, and notification channels.

---

## 2. Role-Based Access Control (RBAC) Matrix

The system enforces four distinct authorization tiers:

| Role | Verification Method | Scope of Authority | Boundary Enforcement |
| :--- | :--- | :--- | :--- |
| **Platform Super Admin** | `is_superuser=True` & `_is_platform_superadmin()` | Global SaaS platform, tenant clinics, platform settings | Isolated to `/super-admin/` routes; forbidden from clinical patient chart access without explicit audit trail. |
| **Clinic Admin** | `ClinicAdmin` relation (`clinic_admin_profile`) | Single clinic operational settings, staff, billing, appointments | Enforced by `_is_clinic_admin()` and `resolve_hospital(user)`. Zero access to other clinics or platform settings. |
| **Doctor / Staff** | `StaffProfile` relation (`staff_profile`) | Clinical tasks, assigned appointments, session notes | Limited to assigned clinical duties; cannot modify clinic billing or delete administrative accounts. |
| **Patient / Client** | `PatientProfile` relation (`patient_profile`) | Personal appointments, invoices, progress tracking | Strictly constrained to own records (`user=request.user`). |

---

## 3. Strict Multi-Tenant Data Isolation

### A. Non-Spoofable Server-Side Tenancy
Tenancy is resolved strictly on the server by inspecting authenticated user relations in `core/tenancy.py`:

```python
def resolve_hospital(user):
    """Resolve clinic strictly from verified server-side profile relations."""
    if not user or not user.is_authenticated:
        return None

    for relation in ("clinic_admin_profile", "staff_profile", "patient_profile"):
        profile = getattr(user, relation, None)
        if profile is not None and profile.hospital_id:
            return profile.hospital
    ...
```

### B. Tenancy Rules:
1. **No Client-Side Injections**: Views never trust `hospital_id` passed in query parameters, POST payloads, or cookies for authenticated operations.
2. **Cross-Tenant Prevention**:
   - `ClinicNotificationRecipient` operations (add, toggle, delete) verify `hospital=resolved_hospital`.
   - Accessing recipient ID 5 while authenticated as Clinic B returns HTTP 404 (or 403 Forbidden).
3. **Database-Level Isolation**:
   - All clinic-scoped models contain an explicit `hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)`.

---

## 4. Administrative Identity Decoupling

To prevent security misconfigurations and unauthorized privilege escalation:

1. **Super Admin Identity Immunity**:
   - The platform Super Admin email (`techcraft1215@gmail.com`) is stored in environment variables and protected in `PlatformSettings`.
   - Clinic Administrators cannot edit platform settings.
   - Clinic Administrators are actively blocked by backend validation from registering the Super Admin email as a clinic recipient:
     ```python
     if email == super_admin_email and not request.user.is_superuser:
         messages.error(request, "Platform Super Admin email cannot be registered as a clinic notification recipient.")
         return redirect("admin_settings")
     ```
2. **No Routine Clinic Exposure**:
   - The Super Admin email is never exposed to public visitors on clinic booking pages.
   - The Super Admin email is systematically excluded from clinic appointment notification routing loops.

---

## 5. Patient Privacy in Notifications & Logging

### A. Minimal Medical Data Disclosure
Transactional emails sent to clinic coordinators and patients contain only administrative booking metadata:
- Patient Name & Contact Phone
- Appointment Date & Preferred Time Window
- Chief Complaint / Service Category (high-level, e.g., "Knee Rehabilitation")
- **NEVER Disclosed via Email**: Detailed clinical examination notes, patient medical history, or payment card numbers.

### B. Log Masking
Email dispatch logging utilizes privacy masking to prevent exposure of Protected Health Information (PHI) or personal email addresses in production log aggregators:
- Email `doctor.rehab@example.com` appears in logs as `d**********b@example.com`.
- Email `techcraft1215@gmail.com` appears in logs as `t**********5@gmail.com`.

---

## 6. Protection Against Common Web Vulnerabilities

### A. Cross-Site Request Forgery (CSRF)
- Enforced on all mutating HTTP methods (POST, PUT, DELETE) via `django.middleware.csrf.CsrfViewMiddleware`.
- AJAX operations require the `X-CSRFToken` header.

### B. Cross-Site Scripting (XSS)
- Django auto-escaping is active across all HTML templates.
- HTML email templates escape dynamic variables using `{{ variable }}` without `|safe` on user-supplied strings.

### C. SQL Injection
- 100% of database interactions utilize Django's parameterized ORM.
- No raw string interpolation into SQL queries.

### D. Rate Limiting & Honeypot Spam Protection
- Public booking and contact forms enforce IP-based rate limiting via `django-ratelimit` / custom middleware.
- Hidden honeypot fields silently trap automated spam bots without interrupting real patients.

### E. Session Management & Back-Button Protection
- Idle session timeout middleware logs out inactive sessions after 30 minutes.
- `PreventBackAfterLogoutMiddleware` applies `Cache-Control: no-cache, no-store, must-revalidate` headers to authenticated views to prevent browser caching of patient records on shared computers.
