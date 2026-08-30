# 🤖 PhysioRehab AI Architectural Guide & Blueprint

Welcome to the **PhysioRehab Clinic & Multi-Tenant Hospital Management System** AI documentation. This document is designed to give any AI agent, LLM, or software engineer an immediate, comprehensive understanding of the project's requirements, domain logic, data models, permission rules, and codebase structure.

---

## 1. Executive Overview & Domain

**PhysioRehab** is a full-featured medical practice management platform specifically tailored for physiotherapy and orthopedic clinics (founded for *Dr. Dhvani Patalia (PT)*, Jamnagar).

The system supports:
1. **Multi-Tenancy & Platform Administration**: Host multiple clinic branches / hospitals under a unified SaaS platform with subscription billing.
2. **Four Distinct Role Dashboards**:
   - 🛡️ **Clinic Admin Dashboard**: Full clinic administration (appointments, patient directory, staff roster, leaves, salaries, daily tasks, clinic settings, promo banners, reviews, blogs, and support tickets).
   - 🩺 **Doctor / Physiotherapist Dashboard**: Clinical progress tracking, patient assessments, session notes (diagnosis, therapy modalities, exercises), and reports.
   - 👥 **Staff / Employee Dashboard**: Shift attendance clock-in/clock-out, leave applications, task checklists, monthly salary slips, and session assistance.
   - 👤 **Client / Patient Portal**: Online appointment booking, treatment progress history, prescription notes, live chat with clinic, Razorpay / UPI bill payment, and feedback reviews.
   - 🌐 **Super Admin (Platform Owner)**: Clinic SaaS tenant onboarding, subscription plans, platform-wide payment approvals, and support ticket management.

---

## 2. Tech Stack & Key Libraries

- **Framework**: Django 6.0+ (Python 3.12+)
- **Database**: SQLite (Development/Test) / PostgreSQL (Production ready via `dj-database-url`)
- **Frontend**: Bootstrap 5, FontAwesome 6, Chart.js, responsive custom CSS design system
- **Payment Gateway**: Razorpay API (`razorpay` SDK) + Direct UPI reference capture + Cash recording
- **Document Generation**:
  - `openpyxl`: Structured Microsoft Excel spreadsheet exports
  - `reportlab`: Formal PDF clinical & financial report generation
- **Communications**: Email notifications via Django standard SMTP/Console backend + Live message chat

---

## 3. Directory Structure Blueprint

```
e:/my_django_app/
├── .env.example                     # Reference environment variables
├── .env                             # Active environment credentials (gitignored)
├── manage.py                        # Django CLI entrypoint
├── myproject/                       # Project configuration package
│   ├── __init__.py
│   ├── settings.py                  # Production-hardened settings with fallback resilience
│   ├── urls.py                      # Root URL router
│   ├── asgi.py
│   └── wsgi.py
├── core/                            # Core application package
│   ├── __init__.py
│   ├── apps.py
│   ├── admin.py                     # Django Admin registration with rich search & filters
│   ├── models.py                    # 20+ Data Models (Hospital, User, Profile, Attendance, etc.)
│   ├── urls.py                      # Application endpoint routes
│   ├── decorators.py                # Role-Based Access Control (@admin_required, @doctor_required, etc.)
│   ├── context_processors.py        # Dynamic user role & unread badge counters
│   ├── email_utils.py               # Transactional email dispatchers
│   ├── notifications.py             # In-app notification creation triggers
│   ├── forms/                       # Modular Django Forms Package
│   │   ├── __init__.py
│   │   ├── auth_forms.py            # User registration, login, profile edit
│   │   ├── appointment_forms.py     # Public & admin appointment booking
│   │   ├── clinic_forms.py          # Clinic settings, promos, reviews, blogs
│   │   ├── medical_forms.py         # Clinical session notes
│   │   └── staff_forms.py           # Leaves, attendance, salaries, tasks
│   ├── services/                    # Encapsulated Business Services Package
│   │   ├── __init__.py
│   │   ├── appointment_service.py   # Slot availability, booking logic, status triggers
│   │   ├── attendance_service.py    # Multi-shift calculation, hours, late detection
│   │   ├── payment_service.py       # Razorpay order generation & HMAC-SHA256 verification
│   │   └── export_service.py        # OpenPyXL & ReportLab document generation
│   ├── views/                       # Modular Views Package (Decomposed from 4,081 lines)
│   │   ├── __init__.py              # Re-exports all views
│   │   ├── public_views.py          # Home, About, Services, Contact, Blog
│   │   ├── auth_views.py            # Login, Register, Logout, Profile, OTP Reset
│   │   ├── client_views.py          # Client dashboard, booking, appointments, reviews
│   │   ├── doctor_views.py          # Clinical progress, session notes, exercises
│   │   ├── staff_views.py           # Staff dashboard, attendance clocking, leaves, tasks
│   │   ├── admin_views.py           # Admin dashboard, patient/staff/salary/promo CRUD
│   │   ├── super_admin_views.py     # SaaS multi-tenancy, hospitals, subscription billing
│   │   ├── payment_views.py         # Razorpay checkout, UPI, cash reconciliation
│   │   ├── chat_views.py            # Live real-time patient-clinic chat & typing status
│   │   ├── notification_views.py    # Notification center, mark read
│   │   └── export_views.py          # Excel & PDF downloadable data exports
│   ├── management/                  # Management commands
│   │   └── commands/
│   │       ├── check_missed_shifts.py
│   │       ├── send_appointment_reminders.py
│   │       └── seed_demo_data.py    # Auto-populates all 4 role accounts + demo data
│   └── tests/                       # Automated Unit & Integration Test Suite
│       ├── __init__.py
│       ├── test_auth.py             # Auth & OTP flows
│       ├── test_rbac.py             # Role access boundaries
│       ├── test_appointments.py     # Slot availability & booking
│       ├── test_attendance.py       # Shift math & late detection
│       ├── test_payments.py         # Razorpay signature & order simulation
│       └── test_exports.py          # Excel/PDF report generation
├── static/                          # Static assets
│   ├── css/
│   │   ├── variables.css            # Gold (#F5C518) & Dark Slate theme system
│   │   ├── dashboard.css            # Unified responsive dashboard layout
│   │   ├── responsive.css           # Mobile breakpoints & touch enhancements
│   │   └── chat.css                 # Real-time chat bubbles & layout
│   └── js/
│       ├── dashboard.js             # Sidebar toggle, table search, auto-dismiss toasts
│       ├── chat.js                  # Chat auto-scroll & typing indicators
│       └── payments.js              # Razorpay popup launcher
└── templates/                       # Jinja2 / Django HTML Templates
    ├── layouts/
    │   ├── base.html                # Root HTML wrapper
    │   ├── base_dashboard.html      # Responsive Sidebar + Topbar + Content layout
    │   └── base_public.html         # Public navigation header + footer
    ├── components/
    │   ├── topbar.html              # Universal topbar with user dropdown & alerts
    │   ├── footer.html              # Universal dashboard footer
    │   ├── toasts.html              # Django messages toaster
    │   ├── sidebar_admin.html       # Clinic Admin menu
    │   ├── sidebar_doctor.html      # Doctor / Physiotherapist menu
    │   ├── sidebar_staff.html       # Employee / Staff menu
    │   ├── sidebar_client.html      # Patient / Client menu
    │   └── sidebar_super_admin.html # SaaS Super Admin menu
    └── *.html                       # View templates
```

---

## 4. Permission & Role-Based Access Control (RBAC) Matrix

| Endpoint / Area | Super Admin | Clinic Admin | Doctor (PT) | Staff / Assistant | Client / Patient | Anonymous |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Public Landing / Services / Blog | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Online Appointment Booking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Client Dashboard (`/dashboard/`) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Client Chat (`/chat/`) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Razorpay / Bill Pay (`/payments/`) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Doctor Clinical Notes (`/progress-tracking/`) | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Staff Dashboard (`/staff-dashboard/`) | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Staff Attendance Clocking | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Clinic Admin Dashboard (`/admin-dashboard/`) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Staff & Salary Management | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Clinic Settings & Promos | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| SaaS Platform Dashboard (`/super-admin/`) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 5. Core Business Workflows

### 5.1 Multi-Shift Attendance Tracking
- **Morning Shift**: 10:00 AM – 01:00 PM (3 hours scheduled)
- **Evening Shift**: 04:00 PM – 08:00 PM (4 hours scheduled)
- **Total Workday**: 7.00 hours
- **Grace Period**: 15 minutes grace on clock-in before marked `late`
- **Calculation Service**: `AttendanceService.process_shift_record(attendance)` computes exact decimal hours across both shifts automatically.

### 5.2 Appointments & Conflict Prevention
- Available slots are defined by `Appointment.TIME_CHOICES` (30-min intervals from 10:00 to 19:30).
- `AppointmentService.is_slot_available(date, time, hospital)` ensures no duplicate bookings occur for active (`pending` or `confirmed`) appointments.
- Status updates trigger automated email confirmations and in-app notifications.

### 5.3 Payment Flow & Webhooks
1. **Online**: Patient initiates checkout -> `PaymentService.create_razorpay_order` creates order -> Razorpay SDK displays modal -> Callback verifies HMAC-SHA256 signature -> `PaymentRecord` marked `paid` -> Appointment confirmed.
2. **UPI QR**: Patient scans clinic UPI QR -> Submits 12-digit UTR -> Admin verifies & approves in `/admin-dashboard/payments/`.
3. **Cash**: Clinic receptionist records cash receipt directly from reception desk.

---

## 6. Seed Demo Data & Credentials

Run `python manage.py seed_demo_data` to reset or populate default accounts:

| Role | Username | Password | Email | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Super Admin** | `superadmin` | `superadmin123` | `superadmin@physiorehab.com` | SaaS multi-tenancy & subscriptions |
| **Clinic Admin** | `admin` | `admin123` | `admin@physiorehab.com` | Clinic operations, staff, settings |
| **Doctor (PT)** | `doctor_dhvani` | `doctor123` | `doctor@physiorehab.com` | Clinical diagnoses, treatment notes |
| **Staff Member** | `staff_rahul` | `staff123` | `staff@physiorehab.com` | Attendance clocking, task list |
| **Patient** | `patient_priya` | `client123` | `patient@physiorehab.com` | Bookings, bill payment, live chat |

---

## 7. Running Automated Tests

Run the test suite with:
```bash
python manage.py test core
```
Expected output: **22 tests, 0 failures, 0 errors (OK)**.

