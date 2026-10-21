# Database & Frontend-Backend Integration Audit Report

**Repository**: [https://github.com/TanviMandalia/Python_django_app](https://github.com/TanviMandalia/Python_django_app)  
**Database**: PostgreSQL 18.6 (`physio_db` on port 5433)  
**Deployment**: Render  
**Django Version**: 5.2.x | **Python**: 3.12.9 (Virtualenv: `.venv`)  
**Audit Status**: Verified & Validated (All 452 automated tests passed)

---

## 1. Executive Summary

A comprehensive read-only audit of the PostgreSQL database and end-to-end integration mapping across all Django frontend pages, forms, and backend endpoints was performed:
* **PostgreSQL Schema**: 62 public tables, 109 foreign keys, 33 unique constraints, 281 indexes, and 615 columns.
* **Model Synchronization**: 52 `core` Django models mapped to database tables with 100% column-to-field alignment (571 fields verified).
* **Referential Integrity**: 0 orphaned records found across all 109 foreign key constraints.
* **Frontend Routing**: 602 `{% url %}` references across all HTML templates were checked; 100% resolve to active Django view endpoints.
* **Form & CSRF Security**: All 87 POST forms contain active `{% csrf_token %}` tags.
* **Automated Tests**: 452 tests executed; 452 passed (0 failures, 0 errors, 0 silenced issues).

---

## 2. PostgreSQL Database Audit

### 2.1 Connection & Environment
* **Engine**: `django.db.backends.postgresql`
* **Version**: PostgreSQL 18.6 on x86_64-windows, 64-bit
* **Migration Status**: 68 total applied migrations (50 in `core`). `python manage.py makemigrations --check --dry-run` reports 0 pending changes.

### 2.2 Table-to-Model Mapping Inventory

| Database Table | Django Model | Row Count | Purpose & Domain |
| :--- | :--- | :--- | :--- |
| `core_hospital` | `core.Hospital` | 2 | Multi-tenant clinic instances (SaaS tenants) |
| `core_hospitalsubscription` | `core.HospitalSubscription` | 2 | Clinic subscription status, tier & validity |
| `core_subscriptionplan` | `core.SubscriptionPlan` | 5 | SaaS pricing tiers & plan configurations |
| `core_subscriptionhistory` | `core.SubscriptionHistory` | 0 | Audit trail of plan changes and renewals |
| `core_featurecategory` | `core.FeatureCategory` | 7 | SaaS feature catalog categories |
| `core_feature` | `core.Feature` | 16 | Granular platform features and modules |
| `core_planfeature` | `core.PlanFeature` | 80 | Entitlement matrix linking plans to features |
| `core_clinicfeatureoverride`| `core.ClinicFeatureOverride` | 0 | Tenant-specific feature flag overrides |
| `core_clinicsubscriptionpayment` | `core.ClinicSubscriptionPayment` | 0 | Subscription transaction ledger |
| `auth_user` | `django.contrib.auth.models.User` | 13 | Global authentication credentials |
| `core_profile` | `core.Profile` | 13 | User profile (role, phone, hospital link) |
| `core_clinicadmin` | `core.ClinicAdmin` | 2 | Clinic administrator credentials & association |
| `core_staffprofile` | `core.StaffProfile` | 3 | Physical therapists & clinical staff profiles |
| `core_patientprofile` | `core.PatientProfile` | 2 | Patient medical records & contact details |
| `core_role` | `core.Role` | 4 | RBAC role definitions (Admin, Staff, Client, etc.) |
| `core_userrole` | `core.UserRole` | 4 | User-to-role assignment junction |
| `core_appointment` | `core.Appointment` | 5 | Scheduled consultations and clinical visits |
| `core_publicappointmentrequest` | `core.PublicAppointmentRequest` | 0 | Unauthenticated public booking intake |
| `core_staffavailability` | `core.StaffAvailability` | 0 | Therapist work shift and slot availability |
| `core_clinicsettings` | `core.ClinicSettings` | 2 | Clinic operating hours, slot intervals & policies |
| `core_clinicservice` | `core.ClinicService` | 0 | Clinic-specific treatment offerings |
| `core_treatmentcategory` | `core.TreatmentCategory` | 10 | Clinical categories (e.g. Sports, Neuro) |
| `core_treatment` | `core.Treatment` | 10 | Published treatment protocols and service pages |
| `core_sessionnote` | `core.SessionNote` | 3 | Clinical SOAP notes & treatment progress |
| `core_exercise` | `core.Exercise` | 0 | Rehabilitation exercise library |
| `core_exerciselog` | `core.ExerciseLog` | 0 | Patient exercise completion logs |
| `core_patientexerciseassignment` | `core.PatientExerciseAssignment` | 0 | Prescribed rehabilitation programs |
| `core_treatmentplan` | `core.TreatmentPlan` | 0 | Longitudinal patient rehabilitation plans |
| `core_paymentrecord` | `core.PaymentRecord` | 3 | Consultation fees, invoices, cash/UPI receipts |
| `core_paymentevent` | `core.PaymentEvent` | 0 | Payment webhook & transactional events |
| `core_attendance` | `core.Attendance` | 1 | Staff biometric/manual clock-in & hours |
| `core_leaveapplication` | `core.LeaveApplication` | 1 | Staff time-off requests and approvals |
| `core_salaryrecord` | `core.SalaryRecord` | 2 | Monthly staff payroll slips and disbursement |
| `core_dailytask` | `core.DailyTask` | 1 | Clinic operational tasks and task status |
| `core_message` | `core.Message` | 7 | Real-time internal & clinical chat messaging |
| `core_mediaasset` | `core.MediaAsset` | 0 | Secure chat attachments & clinical files |
| `core_notification` | `core.Notification` | 15 | In-app alerts, reminders and system updates |
| `core_clinicpromo` | `core.ClinicPromo` | 1 | Clinic announcement banners & promos |
| `core_review` | `core.Review` | 0 | Google/direct patient testimonials & ratings |
| `core_blog` | `core.Blog` | 1 | Published educational blog articles |
| `core_supportticket` | `core.SupportTicket` | 1 | Clinic admin to platform helpdesk tickets |
| `core_supportreply` | `core.SupportReply` | 2 | Helpdesk correspondence threads |
| `core_emailaccount` | `core.EmailAccount` | 1 | Multi-account SMTP governance & credentials |
| `core_emaillog` | `core.EmailLog` | 20 | Outbound email audit trail & delivery status |
| `core_inboundemail` | `core.InboundEmail` | 3 | Inbound doctor reply webhook & parsing |
| `core_passwordresetotp` | `core.PasswordResetOTP` | 0 | Time-sensitive 6-digit password reset tokens |
| `core_visitorsession` | `core.VisitorSession` | 15 | First-party visitor sessions (zero-cookie/GDPR) |
| `core_pageviewevent` | `core.PageViewEvent` | 62 | Anonymized page view telemetry |
| `core_visitorconsentrecord`| `core.VisitorConsentRecord`| 0 | Explicit visitor cookie & tracking consents |
| `core_visitorlead` | `core.VisitorLead` | 0 | Inbound leads captured from public forms |
| `core_analyticssetting` | `core.AnalyticsSetting` | 1 | Platform telemetry retention & privacy rules |
| `core_analyticsauditlog`| `core.AnalyticsAuditLog` | 0 | Compliance log for data purge actions |
| `core_auditevent` | `core.AuditEvent` | 1 | System-wide administrative action audit trail |
| `django_session` | `django.contrib.sessions.models.Session` | 94 | Active user web sessions |
| `django_admin_log` | `django.contrib.admin.models.LogEntry` | 0 | Django built-in admin action log |
| `django_content_type` | `django.contrib.contenttypes.models.ContentType` | 58 | Django content types registry |
| `django_migrations` | None (Internal) | 68 | Applied database migration history |
| `auth_permission` | `django.contrib.auth.models.Permission` | 232 | Granular Django model permissions |
| `auth_group` | `django.contrib.auth.models.Group` | 0 | Django auth permission groups |
| `auth_group_permissions`| None (ManyToMany Junction) | 0 | Django auth group permissions |
| `auth_user_groups` | None (ManyToMany Junction) | 0 | Django user group assignments |
| `auth_user_user_permissions`| None (ManyToMany Junction) | 0 | Django user direct permission overrides |

---

## 3. Frontend-to-Backend Connectivity

### 3.1 Super Admin Dashboard
* **Metrics & Analytics**: Database-backed queries for tenant subscriptions, revenue, and active clinics (`super_admin_dashboard`, `super_admin_analytics`).
* **Multi-Tenant Operations**: Clinic provisioning, suspension, activation, subscription tier upgrades, and feature overrides.
* **Email Governance**: Multi-account SMTP configuration, credential testing, and audit logging (`super_admin_email_accounts`).
* **Telemetry & Privacy**: First-party visitor analytics, lead management, and GDPR retention/purge actions (`super_admin_visitor_analytics`, `super_admin_analytics_purge`).

### 3.2 Clinic Admin Dashboard
* **Appointments Intake**: Full support for authenticated client bookings (`Appointment`) and public booking requests (`PublicAppointmentRequest`).
* **Clinical Records**: Longitudinal patient records, SOAP session notes, and treatment plans.
* **Staff & Payroll**: Clock-in/clock-out tracking, leave approvals, and monthly salary disbursement.
* **Payments & Billing**: Cash and UPI receipt recording, PDF/Excel ledger exports, and refund/cancellation tracking.

### 3.3 Staff Dashboard
* **Personalized Schedule**: Shift schedule and assigned patient appointments scoped to `request.user`.
* **Clinical Input**: Session notes and recovery progress tracking for assigned visits.
* **Attendance & Time-Off**: Shift clock-in/out and leave application submission.
* **Strict Tenant Isolation**: Server-side enforcement prevents staff from inspecting other staff salaries, appointments, or clinic-wide totals.

### 3.4 Client / Patient Dashboard
* **Patient Portal**: Upcoming appointments, prescription notes, and payment receipts isolated strictly to `request.user`.
* **Interactive Booking**: Conflict-prevented appointment slot booking.
* **Doctor Chat**: Real-time communication with clinic doctors with attachment downloads.

### 3.5 Public Clinic Website
* **Public Appointment Request**: Dedicated route at `/book-appointment/` with CSRF protection, honeypot anti-bot trap, IP rate limiting, server-side validation, and instant email dispatch to `physio.rehab.guj@gmail.com`.
* **SEO & Compliance**: Dynamic `sitemap.xml`, `robots.txt`, Google verification handling, and cookie-free analytics consent.

---

## 4. Test Suite Execution Results

All automated test suites were executed against the PostgreSQL environment:
```bash
python manage.py test
```
* **Ran**: 452 tests in 302.371s
* **Passed**: 452
* **Failures**: 0
* **Errors**: 0
* **System Checks**: 0 issues identified
