# Project Structure & Architecture Overview
**PhysioRehab Multi-Clinic SaaS Platform**

---

## 1. High-Level Architectural Pattern

The application is structured as a **Multi-Tenant Django SaaS Architecture** adhering to clean separation of concerns, robust security boundaries, and healthcare-grade data isolation.

```
                           ┌────────────────────────────┐
                           │   Cloudflare / Edge CDN    │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │    Gunicorn WSGI Server    │
                           └─────────────┬──────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
    ┌──────────────────────────┐                    ┌──────────────────────────┐
    │     Django Middleware    │                    │     Django Middleware    │
    │  - SecurityHeaders       │                    │  - SessionTimeout        │
    │  - PublicVisitorTracking │                    │  - SubscriptionGate      │
    └────────────┬─────────────┘                    └────────────┬─────────────┘
                 │                                               │
                 ▼                                               ▼
    ┌──────────────────────────┐                    ┌──────────────────────────┐
    │      Public Surfaces     │                    │  Authenticated Portals   │
    │  - Home, Treatments      │                    │  - Super Admin Portal    │
    │  - Unified Booking & Lead│                    │  - Clinic Admin Portal   │
    │  - SEO Landing Pages     │                    │  - Patient Client Portal │
    └────────────┬─────────────┘                    └────────────┬─────────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                           ┌────────────────────────────┐
                           │      Core Service Layer    │
                           │  - Tenancy Isolation       │
                           │  - Multi-Email Dispatcher  │
                           │  - Feature Entitlements    │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │   Supabase PostgreSQL DB   │
                           │  - 52 Normalized Models    │
                           │  - Strict Tenant FKs       │
                           └────────────────────────────┘
```

---

## 2. Directory Tree Layout

```
Python_django_app/
│
├── core/                              # Primary Django application domain
│   ├── migrations/                    # 52 production-tested migrations
│   │   ├── 0051_hospital_razorpay_account_id...
│   │   └── 0052_platformsettings_and_more.py  # Platform & Multi-Email routing models
│   ├── admin.py                       # Django standard admin registrations
│   ├── apps.py                        # Core application registry configuration
│   ├── context_processors.py          # Dynamic clinic NAP & unread badge counters
│   ├── email_service.py               # Outbox management & transactional records
│   ├── email_utils.py                 # Multi-recipient dispatch & clinic templates
│   ├── entitlements.py                # SaaS tiered feature flags & usage quotas
│   ├── forms.py                       # Hardened forms with CSRF and anti-tampering
│   ├── google_reviews.py              # Google Places API caching and reviews sync
│   ├── middleware.py                  # Rate-limiting, tracking, session protection
│   ├── models.py                      # PostgreSQL data definitions & business logic
│   ├── tenancy.py                     # Non-spoofable hospital/clinic resolution
│   ├── urls.py                        # Endpoint definitions and view mappings
│   └── views.py                       # Route controllers (Public, Client, Admin, Super Admin)
│
├── myproject/                         # Django project orchestration
│   ├── settings/                      # Split environment settings
│   │   ├── __init__.py
│   │   ├── base.py                    # Base configuration, middleware, apps, auth
│   │   ├── dev.py                     # Local developer runtime (PostgreSQL / SQLite)
│   │   └── production.py              # Hardened production (Render / Supabase)
│   ├── asgi.py                        # ASGI entrypoint
│   ├── wsgi.py                        # WSGI entrypoint (Gunicorn / PaaS)
│   └── urls.py                        # Root URL routing
│
├── templates/                         # Django HTML5 presentation templates
│   ├── admin/                         # Clinic Administrator portal templates
│   │   ├── base_admin.html            # Admin master shell with branded responsive layout
│   │   ├── admin_dashboard.html       # Clinic metrics, revenue cards, appointments
│   │   ├── admin_settings.html        # Multi-email recipients & clinic configuration
│   │   └── ...                        # Patient, Staff, Task, Leave management views
│   ├── super_admin/                   # Platform Owner portal templates
│   │   ├── base_super_admin.html      # Super Admin layout
│   │   ├── super_admin_dashboard.html # Multi-tenant overview & metrics
│   │   ├── super_admin_clinics.html   # Clinic provisioning & lifecycle
│   │   ├── super_admin_clinic_detail.html # Deep-dive into clinic routing & accounts
│   │   └── super_admin_platform_settings.html # Platform Super Admin identity settings
│   ├── emails/                        # Branded HTML email templates
│   │   ├── public_appointment_clinic_notification.html  # Clinic team alert
│   │   ├── public_appointment_patient_acknowledgment.html # Patient receipt
│   │   ├── contact_inquiry_clinic_notification.html    # Lead alert
│   │   └── appointment_confirmed.html                  # Official confirmation
│   ├── client/                        # Patient portal templates
│   ├── public/                        # Public SEO & booking templates
│   └── partials/                      # Reusable components (preloader, navbar, footer)
│
├── static/                            # Static asset pipeline
│   ├── css/                           # Vanilla CSS design system
│   ├── js/                            # Modular scripts (preloader, admin layout)
│   └── images/                        # Branded clinic media & favicons
│
├── tests/                             # Comprehensive automated test suite
│   ├── test_helpers.py                # Standardized factories & test fixtures
│   ├── test_multi_email_notifications.py # Platform Admin & multi-email test suite
│   ├── test_public_appointment.py     # Public booking workflow verification
│   ├── test_clinic_admin.py           # Clinic Admin CRUD & security verification
│   └── ...                            # RBAC, Payment, deployment tests
│
├── docs/                              # Architecture & operational guides
├── scripts/                           # Maintenance & migration shell scripts
├── requirements.txt                   # Production pinned dependencies
├── Procfile                           # Gunicorn web dyno process declaration
├── render.yaml                        # Render cloud orchestration specification
└── manage.py                          # Django management CLI utility
```

---

## 3. Core Component Responsibilities

### `core/models.py`
Contains 52 PostgreSQL-compatible models. Key models for multi-clinic administration:
- **`Hospital`**: The root tenant model. All clinical entities (`Appointment`, `PatientProfile`, `StaffProfile`, `ClinicSettings`) cascade from here.
- **`PlatformSettings`**: Singleton storing platform-wide identity (`techcraft1215@gmail.com`), platform branding, and maintenance switches.
- **`ClinicSettings`**: Clinic operational configuration (`physio.rehab.guj@gmail.com`), phone, address, and notification toggles.
- **`ClinicNotificationRecipient`**: Multi-email routing table allowing unlimited categorized recipients per clinic with duplicate email prevention.
- **`PublicAppointmentRequest`**: Captures visitor booking submissions in initial `pending` state with reference IDs (e.g., `PAR-20261102-XXXX`).

### `core/tenancy.py`
- Provides `resolve_hospital(user)` and `require_hospital(user)`.
- Inspects verified server-side user relations (`clinic_admin_profile`, `staff_profile`, `patient_profile`) to determine clinic tenancy.
- **Security Rule**: The active clinic can NEVER be forged or spoofed via client-side request headers, query parameters, or hidden form inputs.

### `core/email_utils.py`
- Encapsulates transactional email dispatch.
- Dynamically resolves multiple active clinic notification recipients.
- Explicitly enforces that platform Super Admin credentials and emails are excluded from routine clinic notifications.
- Catches network timeouts and SMTP transport exceptions to prevent patient booking loss.

### `core/entitlements.py`
- Manages feature tiering (Starter, Pro, Enterprise).
- Controls feature gates such as automated reminders, multi-doctor scheduling, and analytics exports.
