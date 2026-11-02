# Email Configuration & Multi-Recipient Architecture Guide
**PhysioRehab Multi-Clinic SaaS Platform**

---

## 1. Executive Summary & Identity Separation Philosophy

In a healthcare SaaS application, administrative identities and email roles must remain strictly decoupled. Conflating platform administration with clinic-level clinical operations creates operational hazards, privacy leaks, and confusion.

The PhysioRehab platform enforces a strict separation across four distinct email identities:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        EMAIL IDENTITY ARCHITECTURE                     │
├────────────────────────────┬───────────────────────────────────────────┤
│ Role                       │ Identity / Purpose                        │
├────────────────────────────┼───────────────────────────────────────────┤
│ 1. Platform Super Admin    │ Platform Owner (techcraft1215@gmail.com)  │
│                            │ Platform-wide alerts, security notices,   │
│                            │ infrastructure lifecycle. NEVER receives  │
│                            │ routine clinic patient bookings.          │
├────────────────────────────┼───────────────────────────────────────────┤
│ 2. Clinic Doctor / Admin   │ Clinical Team (physio.rehab.guj@gmail.com)│
│                            │ Receives appointment booking alerts,      │
│                            │ patient inquiries, and clinical handovers │
│                            │ for Dr. Dhvani Patalia Physio Rehab.      │
├────────────────────────────┼───────────────────────────────────────────┤
│ 3. Authenticated Sender    │ Transactional SMTP / Resend / SES         │
│                            │ Configured in ClinicEmailAccount or       │
│                            │ DEFAULT_FROM_EMAIL. Sender identity used  │
│                            │ to dispatch emails with proper SPF/DKIM.  │
├────────────────────────────┼───────────────────────────────────────────┤
│ 4. Patient / Visitor       │ External Public / Recipient               │
│                            │ Patient receiving booking acknowledgments │
│                            │ and appointment confirmation notices.     │
└────────────────────────────┴───────────────────────────────────────────┘
```

> [!IMPORTANT]
> The **Platform Super Admin** email (`techcraft1215@gmail.com`) is never hardcoded as a clinic notification recipient. Clinic administrators cannot view, modify, or register the Super Admin email within their clinic settings.

---

## 2. Architecture & Data Models

### A. `PlatformSettings` (Singleton)
- **Table**: `core_platformsettings`
- **Purpose**: Stores platform-wide configuration and platform owner contact details.
- **Access**: Strictly restricted to the Platform Super Admin (`techcraft1215` / `is_superuser`). Clinic Admins have zero read/write access.
- **Fields**:
  - `platform_name`: SaaS platform display brand (e.g., "PhysioRehab SaaS Cloud").
  - `super_admin_email`: Platform owner primary email (`techcraft1215@gmail.com`).
  - `super_admin_username`: Designated Super Admin username (`techcraft1215`).
  - `system_alert_email`: Destination for critical security and platform error alerts.
  - `support_email`: Public support contact address.
  - `maintenance_mode`: Global maintenance toggle with custom visitor notice.

### B. `ClinicSettings` (Per-Clinic Configuration)
- **Table**: `core_clinicsettings`
- **Purpose**: Clinic-specific branding, operational contact details, and notification preferences.
- **Key Fields**:
  - `hospital`: OneToOne relationship to `Hospital`.
  - `clinic_name`: Clinic display name.
  - `email`: General clinic contact email (`physio.rehab.guj@gmail.com`).
  - `primary_doctor_email`: Dedicated email for doctor appointment alerts.
  - `appointment_notification_enabled`: Master boolean toggle to mute/unmute clinic appointment alerts.
  - `lead_notification_enabled`: Master boolean toggle to mute/unmute visitor inquiry alerts.

### C. `ClinicNotificationRecipient` (Multi-Email Routing Registry)
- **Table**: `core_clinicnotificationrecipient`
- **Purpose**: Allows a clinic to configure multiple notification recipients (Doctor, Clinic Admin, Appointment Coordinator, Receptionist, Billing).
- **Key Fields**:
  - `hospital`: ForeignKey to `Hospital`.
  - `name`: Recipient full name or desk title (e.g., "Dr. Dhvani Patalia", "Front Desk Coordinator").
  - `email`: Validated email address.
  - `recipient_type`: Role classification (`doctor`, `admin`, `coordinator`, `billing`, `general`).
  - `notify_on_appointment`: Boolean toggle for appointment booking alerts.
  - `notify_on_contact_inquiry`: Boolean toggle for general website leads.
  - `is_active`: Operational toggle to mute notifications without deleting recipient history.
  - **Constraint**: `unique_together = ("hospital", "email")` ensures no duplicate emails within the same clinic.

---

## 3. Appointment Booking Notification Workflow

When a visitor books an appointment via the public booking portal:

```
[ Visitor Submits Booking Form ]
               │
               ▼
   [ Form Validation & CSRF Check ]
               │
               ▼
[ PublicAppointmentRequest Saved (Status: 'pending') ]
               │
               ▼
[ Retrieve Active Clinic Notification Recipients ]
  ├── Resolves ClinicSettings.primary_doctor_email
  ├── Queries ClinicNotificationRecipient (is_active=True, notify_on_appointment=True)
  └── Excludes Platform Super Admin Email (techcraft1215@gmail.com)
               │
               ▼
[ Are Appointment Notifications Enabled for Clinic? ]
  ├── NO  ──> Log skip notice & proceed to patient confirmation
  └── YES ──> Dispatch branded alert to all resolved recipients
               │
               ▼
[ Dispatch Patient Acknowledgment Email ]
  └── Visitor is explicitly told: "Request received – awaiting clinic confirmation"
               │
               ▼
[ Fault-Tolerant Delivery Safeguard ]
  └── SMTP network drops or delivery failures NEVER delete or roll back the booking.
```

### Key Safety Guarantees:
1. **Pending State**: The visitor is never told their appointment is confirmed until a clinic administrator approves it in the dashboard.
2. **Resilience**: If the SMTP server experiences a timeout or authentication failure, the exception is caught, logged to `django.production`, and the booking remains safely saved in the database.
3. **No Cross-Clinic Leakage**: Recipient resolution queries filter exclusively by `hospital=appointment.hospital`.

---

## 4. Clinic Admin Configuration Instructions

Clinic administrators manage their notification routing directly from the Clinic Admin Portal without developer assistance or source code edits.

### A. Accessing Clinic Settings
1. Log in to the Clinic Admin Portal: `https://yourdomain.com/login/`
2. In the left navigation menu, click **Settings** (`/admin-settings/`).

### B. Updating Primary Doctor & Toggles
1. Under **Clinic Information & General Settings**:
   - Verify **Clinic Contact Email** (`physio.rehab.guj@gmail.com`).
2. Under **Notification Preferences**:
   - Set **Primary Doctor / Appointment Alert Email** (e.g., `physio.rehab.guj@gmail.com`).
   - Check or uncheck **Receive email alerts when new appointments are booked**.
   - Check or uncheck **Receive email alerts for general contact inquiries**.
3. Click **Save Settings**.

### C. Adding Multiple Notification Recipients
1. Scroll down to the **Clinic Appointment Notification Recipients** section.
2. Click **+ Add Recipient** to open the modal dialog.
3. Fill in the recipient details:
   - **Full Name**: e.g., `Front Desk Receptionist` or `Dr. Associate`
   - **Email Address**: e.g., `reception@physiorehab.com`
   - **Recipient Role**: Choose from Doctor, Clinic Administrator, Appointment Coordinator, Billing, or General.
   - **Notification Types**: Check *Appointment Booking Requests* and/or *Contact Form Inquiries*.
   - **Active Status**: Checked by default.
4. Click **Add Recipient**. The email address is validated, checked for duplicates, and added immediately.

### D. Managing Existing Recipients
- **Mute / Unmute**: Click the toggle switch icon next to any recipient to temporarily pause notifications without deleting their profile.
- **Remove**: Click the red trash icon to delete a recipient.

---

## 5. Platform Super Admin Configuration Instructions

The Platform Super Admin controls platform-wide parameters and tenant isolation.

### A. Accessing Platform Settings
1. Log in with the platform owner account (`techcraft1215`).
2. Navigate to **Super Admin Portal** -> **Platform Settings** (`/super-admin/platform-settings/`).
3. Only authenticated Super Admins can access this view; any clinic admin attempting access is redirected to their own dashboard with an access error.

### B. Available Platform Controls
- **Platform Display Name**: Global branding.
- **Super Admin Email**: `techcraft1215@gmail.com`
- **System Alert Email**: Target inbox for security logs and server alerts.
- **Platform Support Email**: Public contact point for SaaS tenant support.
- **Maintenance Mode**: Toggle to temporarily show a branded maintenance notice to public visitors while allowing staff login.

---

## 6. Email Provider Setup & Environment Variables

### Recommended Production Providers:
1. **Google Workspace / Gmail SMTP**: Suitable for current clinic volume. Requires a 2-Step Verification App Password (16 characters).
2. **Resend / SendGrid / Amazon SES**: Recommended for high-volume multi-clinic scaling with dedicated DKIM/SPF domain verification.

### Required Environment Variables:

| Variable | Description | Example / Recommended Value |
| :--- | :--- | :--- |
| `PLATFORM_SUPERADMIN_EMAIL` | Platform owner email | `techcraft1215@gmail.com` |
| `CLINIC_EMAIL` | Primary clinic public email | `physio.rehab.guj@gmail.com` |
| `CLINIC_NOTIFICATION_EMAIL`| Default clinic alert recipient | `physio.rehab.guj@gmail.com` |
| `CLINIC_NAME` | Primary clinic organization name | `Dr. Dhvani Patalia Physio Rehab` |
| `CLINIC_PHONE` | Primary clinic contact phone | `+91 94095 10501` |
| `EMAIL_BACKEND` | Django email backend | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Transport Layer Security | `True` |
| `EMAIL_HOST_USER` | Authenticated SMTP username | `physio.rehab.guj@gmail.com` |
| `EMAIL_HOST_PASSWORD` | App Password (never personal pwd) | *(16-character Google App Password)* |
| `DEFAULT_FROM_EMAIL` | Default From header | `Dr. Dhvani Patalia Physio Rehab <physio.rehab.guj@gmail.com>` |

> [!CAUTION]
> Never commit real SMTP passwords or Google App Passwords to version control. Store all credentials in the production platform environment variables (Render, Vercel, Supabase, or AWS Secrets Manager).

---

## 7. Verification & Automated Testing

The multi-email configuration architecture is covered by automated unit and integration tests:

```bash
# Run multi-email test suite
python manage.py test tests.test_multi_email_notifications

# Run appointment and admin regression suites
python manage.py test tests.test_public_appointment tests.test_clinic_admin
```

All automated tests use Django's memory backend (`locmem.EmailBackend`) to guarantee that zero external network emails are dispatched during testing.
