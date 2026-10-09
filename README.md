# PhysioRehab SaaS — Multi-Clinic Management Platform

[![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.6-336791?logo=postgresql)](https://www.postgresql.org/)
[![Test Suite](https://img.shields.io/badge/Tests-320%20Passed-brightgreen)](tests/)

A multi-tenant, enterprise-grade Clinic & Hospital Management SaaS platform tailored for physiotherapy and specialty healthcare centers. The system provides complete clinic operations including multi-role portals, doctor scheduling, patient clinical records, single-conversation clinical messaging with secure attachments, staff attendance and payroll, internal payment logs, multi-account SMTP email governance with strict platform (TechCraft) vs clinic identity separation, an automated 24-hour OTP retention & cleanup policy, a centralized Super Admin SaaS subscription & feature entitlement engine, and a complete technical & local SEO framework for public healthcare clinic discoverability.

---

## 1. Project Overview & Architecture

### 1.1 Core Modules
- **Multi-Tenant Clinic Isolation:** Strict data partition per clinic tenant enforced server-side via `core.tenancy`.
- **4 Distinct Role Portals:** Dedicated web portals for Platform Administrators (`super_admin`), Clinic Administrators (`admin`), Clinical Staff/Physiotherapists (`staff`), and Patients (`client`).
- **Single-Conversation Clinical Messaging & File Sharing:** Instagram-inspired, uncluttered single-conversation view with attachment preview pills, multiline text entry, duplicate submission prevention, and tenant-isolated authenticated downloads (`/chat/attachment/<id>/`).
- **Secure File, Document & Image Uploads:** Defense-in-depth file validation (`.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png`, `.webp`), 10MB clinical limit, magic-byte inspection, Pillow image verification, `X-Content-Type-Options: nosniff`, and `Content-Disposition: attachment`.
- **Email Delivery Audit & 24-Hour OTP Retention:** Granular logging of outgoing and incoming emails with `direction`, `status`, `is_otp`, `expires_at`, and an automated CLI cleanup command (`cleanup_expired_otp_logs`) that purges expired OTP logs while retaining general clinical audit history. Zero plaintext OTP storage.
- **Accessible Sidebar Navigation System:** Unified layout controller (`static/js/layout.js`) supporting smooth desktop collapse (76px/260px), mobile off-canvas drawer with overlay, `aria-expanded` and accessible label synchronization, and Escape key dismissal.
- **Scheduling & Working Weekday Engine:** Automated 30-minute slot generation, doctor availability filters, and double-booking prevention operating Monday through Friday.
- **SaaS Subscription & Entitlement Architecture:** Tiered plans, plan-to-feature matrix, global kill switches, clinic-specific complimentary grants/overrides, and real-time usage meters.
- **Staff Attendance & Payroll:** Morning and evening shift clock-ins, leave requests, monthly salary processing, and payslip generation.
- **Multi-Account Email Governance & Identity Separation:** Strict separation between SaaS platform identity (TechCraft / `techcraft1215@gmail.com`) and clinic identity (Dr. Dhvani Patalia Physio Rehab / `physio.rehab.guj@gmail.com`), per-clinic and platform default SMTP accounts, encrypted credential storage (AES-256), HMAC webhook verification, and idempotency tracking.
- **Technical & Local SEO Architecture:** Dynamic `robots.txt`, valid XML sitemap (`/sitemap.xml`), canonical URLs with query-param stripping, Open Graph & Twitter Cards, Schema.org JSON-LD structured data (`MedicalClinic`, `Physician`, `OfferCatalog`, `MedicalWebPage`), local Jamnagar NAP citations, and `X-Robots-Tag: noindex, nofollow, noarchive` on all private and administrative endpoints.
- **Internal Payment & Billing Logs:** Audit-logged cash, direct UPI QR code, and bank transfer logs with clinic approval/rejection workflows (third-party payment gateways removed).
- **Deployment Hardening & Health Monitoring:** Lightweight `/healthz` probe, WhiteNoise compressed static delivery, `DATABASE_URL` pooling via `dj-database-url`, and safe CLI password rotation command.

### 1.2 Technology Stack
- **Backend Framework:** Python 3.12+ / Django 6.0
- **Database Engine (Production):** PostgreSQL 17 or 18 (with `psycopg` v3 / `dj-database-url`)
- **Database Engine (Development / CI):** SQLite 3 (in `myproject.settings.dev`) or local PostgreSQL
- **Database Management Tool:** pgAdmin 4 compatible
- **Static Asset Pipeline:** WhiteNoise 6.12 with `CompressedManifestStaticFilesStorage`
- **Background Tasks & Workers:** Celery 5.4 with Redis broker (with graceful local filesystem queue fallback)
- **Frontend / UI:** Django Server-Rendered Templates (113 templates), Vanilla CSS, responsive layout architecture, Font Awesome 6
- **Static Assets:** 143 static assets collected via `collectstatic`

### 1.3 Repository Directory Structure

```text
Python_django_app/
├── core/                           # Primary Django application
│   ├── management/commands/        # CLI commands (password rotation, reminders, seeds)
│   ├── migrations/                 # Migrations 0001 through 0041
│   ├── templatetags/               # Custom template filters
│   ├── appointment_slots.py        # Weekday slot generation & doctor scheduling
│   ├── checks.py                   # System checks & readiness verification
│   ├── crypto.py                   # AES-256 (Fernet) credential encryption
│   ├── email_service.py            # Email dispatch & template assembly
│   ├── email_utils.py              # Inbound email parsing, HMAC webhooks & routing
│   ├── entitlements.py             # SaaS feature entitlement & usage engine
│   ├── file_security.py            # File MIME type & extension sanitization
│   ├── middleware.py               # Session timeout, lockout, WhiteNoise & tenant middleware
│   ├── models.py                   # Relational domain & SaaS models (53 tables)
│   ├── tenancy.py                  # Multi-tenant isolation engine
│   ├── urls.py                     # App routing (100+ endpoints + /healthz)
│   └── views.py                    # Role-partitioned view controllers & healthz probe
├── myproject/                      # Project configuration root
│   ├── settings/
│   │   ├── base.py                 # Shared settings & security policies
│   │   ├── dev.py                  # Local development settings (SQLite/PostgreSQL)
│   │   └── production.py           # Production settings (DATABASE_URL, SSL & WhiteNoise)
│   ├── asgi.py                     # ASGI configuration
│   ├── celery.py                   # Celery broker & task configuration
│   ├── urls.py                     # Root URL routing
│   └── wsgi.py                     # WSGI entrypoint for Gunicorn
├── md/                             # Internal engineering reports & plans (git-ignored)
├── static/                         # Source stylesheets, scripts, icons, brand assets
├── staticfiles/                    # Compiled production assets from collectstatic
├── templates/                      # Modular template hierarchy
├── tests/                          # 24 test suites (320+ automated test cases)
├── build.sh                        # Production build script (PaaS / Render / Container)
├── render.yaml                     # Render Blueprint specification
├── .env.example                    # Production environment configuration template
├── manage.py                       # Django administrative CLI
├── requirements.txt                # Production dependencies manifest
└── README.md                       # Public project documentation
```

### 1.4 Modern Direct Messaging (DM) & Decoupled Interaction Architecture
- **Instagram-Inspired Two-Panel Desktop Experience:**
  - **Left Panel (`.chat-inbox-panel`):** Fixed 360px conversation list with instant search filtering, patient/doctor avatars with real-time online status indicators, last message snippets with sender attribution ("You: ..."), formatted timestamps, and unread count badges. Active conversations feature prominent highlight states.
  - **Right Panel (`.chat-conversation-panel`):** Full-height conversation workspace. Features a contact header with status and quick actions, a scrollable chronological message timeline with differentiated sent/received bubbles (`#F5C518` brand gold / neutral white), and a fixed bottom composer with attachment picker, selected file preview pill, and send button.
  - **Zero-Selection Desktop State:** Root `/admin-chat/` and `/admin-doctor-chat/` display a clean, centered welcome state prompting the user to select an inbox conversation.
- **Mobile-First Responsive Transitions (< 992px):**
  - **Strict Single-Panel Mode:** On mobile screens, only ONE panel renders at a time. The conversation list is shown at 100% width on `/admin-chat/`. Tapping any thread transitions to the active conversation at 100% width on `/admin-chat/<id>/`.
  - **Dedicated Mobile Navigation:** A prominent header back arrow (`.chat-back-btn`) returns the user to the conversation list. Overlapping chat windows and dual-pane mobile squishing are strictly eliminated.
- **Independent Controls & Conflict Elimination:**
  - **Decoupled Sidebar Toggle:** `static/js/layout.js` strictly targets dedicated sidebar triggers (`#menuToggle`, `#mobileMenuBtn`, `.sidebar-toggle-btn`, `[data-action="toggle-sidebar"]`). Generic styling classes (such as `.topbar-toggle-btn`) were completely excised from sidebar event listeners.
  - **Dedicated Navigation Back Button:** Back controls use `.chat-back-btn` with explicit `href` targets and fallback URLs, preventing accidental event bubbling or sidebar toggling.
  - **Isolated Attachment Controls:** Attachment pickers use dedicated `.chat-attach-btn` buttons with `type="button"`, completely decoupled from form submission and navigation.
- **Database Query Batching (N+1 Elimination):**
  - Conversation inbox lists (`_get_admin_patient_chats` and `_get_admin_doctor_chats`) batch unread message counts in 1 aggregated query (`Count('id')`) and fetch recent conversation messages in 1 query, replacing 2*N queries with 2 queries total (98% query reduction).
- **Private Attachment Security:**
  - All uploaded clinical records, reports, and images are protected behind authenticated endpoint `/chat/attachment/<id>/`.
  - Server-side multi-tenant authorization verifies clinic ownership, sender/receiver identity, and staff roles. Unauthenticated requests redirect to login, cross-tenant requests yield `403 Forbidden`, and responses enforce `X-Content-Type-Options: nosniff` and `Content-Disposition: attachment`.

---

## 2. Prerequisites & Environment Setup

### 2.1 Software Prerequisites
- **Python:** Version 3.12.0 or higher
- **PostgreSQL:** Version 17.x or 18.x
- **pgAdmin:** pgAdmin 4 (v8.x or higher)
- **Redis (Optional):** Required for production Celery broker (`redis://localhost:6379/0`)

### 2.2 Local Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Python_django_app
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   # Windows PowerShell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Environment Variables:**
   ```powershell
   # Windows PowerShell
   Copy-Item .env.example .env
   ```
   ```bash
   # Linux / macOS
   cp .env.example .env
   ```

---

## 3. PostgreSQL & pgAdmin 4 Configuration

### 3.1 Create PostgreSQL Database
Connect to your local PostgreSQL server via SQL Shell (`psql`) or pgAdmin 4:
```sql
CREATE DATABASE physio_db;
CREATE USER postgres WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE physio_db TO postgres;
```

### 3.2 Configure `.env` for PostgreSQL
Set the following connection parameters in your `.env` file:
```dotenv
DB_ENGINE=django.db.backends.postgresql
DB_NAME=physio_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5433
```
*(Note: If your PostgreSQL service runs on the default port, set `DB_PORT=5432`).*

### 3.3 Connect Through pgAdmin 4
pgAdmin 4 can be launched from the start menu or executable at:
`C:\Program Files\PostgreSQL\18\pgAdmin 4\runtime\pgAdmin4.exe`

To register the application database in pgAdmin 4:
1. Open pgAdmin 4 and right-click **Servers** > **Register** > **Server...**
2. In the **General** tab:
   - Name: `PhysioRehab Production DB`
3. In the **Connection** tab:
   - Host name/address: `localhost` (or `127.0.0.1`)
   - Port: `5433` (or `5432`)
   - Maintenance database: `postgres`
   - Username: `postgres`
   - Password: `<your_secure_password>`
4. Save the server definition, expand **Databases** > `physio_db` > **Schemas** > **public** > **Tables** to view all 53 tables.

### 3.4 Apply Migrations & Initialize Seed Data
Apply all 40 database migrations (which automatically seeds the SaaS catalog and tier plans via migration `0040`):
```bash
python manage.py migrate --settings=myproject.settings.production
```

Create a platform superuser:
```bash
python manage.py createsuperuser --settings=myproject.settings.production
```

### 3.5 Database Backup and Restore
- **Backup (Schema and Data):**
  ```powershell
  & "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h localhost -p 5433 -U postgres -d physio_db -F c -b -v -f "backup_physio_db.dump"
  ```
- **Restore:**
  ```powershell
  & "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -h localhost -p 5433 -U postgres -d physio_db -v "backup_physio_db.dump"
  ```

---

## 4. Running the Application

### 4.1 Local Development Server (SQLite)
```bash
python manage.py runserver --settings=myproject.settings.dev
```
Open `http://127.0.0.1:8000/` in your browser.

### 4.2 Production Server (PostgreSQL)
Collect static assets:
```bash
python manage.py collectstatic --noinput --settings=myproject.settings.production
```

Run WSGI server via Gunicorn (Linux) or Waitress/Uvicorn (Windows):
```bash
gunicorn myproject.wsgi:application --bind 0.0.0.0:8000 --settings=myproject.settings.production
```

### 4.3 Celery Asynchronous Workers
Start the background task worker for automated appointment reminders and email dispatch:
```bash
celery -A myproject worker -l info
```

---

## 5. Roles & Permissions Architecture

The system provides four strict, non-overlapping user roles:

| Role | Target URL | Primary Capabilities | Boundary & Constraints |
|---|---|---|---|
| **Super Admin** | `/super-admin/` | Clinic provisioning, plans & pricing, feature catalog, global kill switches, clinic overrides, usage monitoring, audit logs, platform payment exports. | Platform-wide administration. Cannot view patient clinical notes unless explicitly authorized. |
| **Clinic Admin** | `/admin-dashboard/` | Full clinic management: patient CRUD, doctor scheduling, staff attendance & payroll, clinic payments, email settings, clinic profile. | Strictly bounded to own clinic. Accessing another clinic's data returns HTTP 403/404. |
| **Staff** | `/staff-dashboard/` | Assigned appointments, morning/evening attendance clock-in, leave requests, session notes, daily tasks, read-only clinic payment logs. | Denied access to clinic settings, payroll processing, plan changes, or other clinics. |
| **Client / Patient** | `/client-dashboard/` | Appointment booking, appointment history, receipts & invoice download, clinic chat, profile management. | Strictly bounded to own user record (`patient=request.user`). All other patient records forbidden. |

---

## 6. SaaS Subscription & Feature Entitlement System

Feature access is resolved via a 6-stage evaluation hierarchy in `core/entitlements.py`:

$$\text{Final Access} = \text{Role Permission} + \text{Clinic Context} + \text{Subscription Plan} + \text{Clinic Override} + \text{Usage Cap}$$

### 6.1 Evaluation Order
1. **Global Kill Switch:** If a feature's global status is `disabled`, all clinics are denied access platform-wide.
2. **Maintenance Mode:** Returns a scheduled maintenance notice.
3. **Clinic Suspension:** If a clinic is suspended or archived, access to all features is immediately blocked.
4. **Clinic-Specific Override:** Platform administrators can grant complimentary access, explicitly disable features, or customize limits with an expiration date.
5. **Subscription Plan Mapping:** Evaluates whether the clinic's plan includes the feature (`full`, `limited`, `read_only`).
6. **Usage Limit Checks:** Evaluates real-time counts against plan caps (e.g. `max_patients`, `max_staff`, monthly appointments).

---

## 7. Testing & Quality Assurance

The repository contains comprehensive test suites covering **320 automated tests** across 24 test modules.

### 7.1 Running All Tests via Django Test Runner
```bash
python manage.py test tests
```
*Result: 320 passed in ~141s (100% pass rate, 0 failures, 0 errors).*

### 7.2 Running Focused Feature Test Suites
```bash
# Sidebar navigation and role menu access across all 4 portals
python manage.py test tests.test_sidebar_navigation

# Clinical messaging, secure attachments, and download permissions
python manage.py test tests.test_messaging_and_attachments

# Email delivery audit trail & 24h OTP retention cleanup
python manage.py test tests.test_email_audit_and_otp_retention

# Dedicated SEO validation suite
python manage.py test tests.test_seo_implementation
```

### 7.3 Running All Tests via Pytest
```bash
pytest -q
```
*Result: 320 passed (100% pass rate, 0 failures, 0 errors).*

### 7.4 Running All Tests (PostgreSQL Production Settings)
When running tests against production settings, set `SECURE_SSL_REDIRECT=False` so the local test client is not redirected from HTTP to HTTPS:
```powershell
# Windows PowerShell
$env:SECURE_SSL_REDIRECT="False"; pytest -q --ds=myproject.settings.production
```
```bash
# Linux / macOS
SECURE_SSL_REDIRECT=False pytest -q --ds=myproject.settings.production
```

### 7.5 OTP Retention Cleanup Management Command
Run the scheduled audit cleanup command to delete expired OTP records (24-hour retention):
```bash
# Dry run preview
python manage.py cleanup_expired_otp_logs --dry-run

# Purge expired OTP logs
python manage.py cleanup_expired_otp_logs
```

### 7.6 Code Quality & AST Compilation
Verify that all Python source files parse without syntax errors:
```bash
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('.').rglob('*.py') if '.venv' not in p.parts]"
```
```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```
*Result: 0 syntax or critical lint errors across the entire codebase.*

---

## 8. Environment Variables Reference

| Variable | Description | Required | Example / Default |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic signing key | **Yes** | `django-insecure-prod-key...` |
| `DEBUG` | Enable debug mode | **Yes** | `False` (in production) |
| `ALLOWED_HOSTS` | Comma-delimited list of hostnames | **Yes** | `yourdomain.com,www.yourdomain.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF validation | **Yes** | `https://yourdomain.com` |
| `CANONICAL_BASE_URL` | Production HTTPS URL for canonical SEO tags & sitemap | **Yes** | `https://yourdomain.com` |
| `DB_ENGINE` | Database backend | **Yes** | `django.db.backends.postgresql` |
| `DB_NAME` | PostgreSQL database name | **Yes** | `physio_db` |
| `DB_USER` | PostgreSQL username | **Yes** | `postgres` |
| `DB_PASSWORD` | PostgreSQL user password | **Yes** | Secret |
| `DB_HOST` | Database host | **Yes** | `localhost` |
| `DB_PORT` | Database port | **Yes** | `5433` (or `5432`) |
| `EMAIL_BACKEND` | Django email backend | No | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP server address | No | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | No | `587` |
| `EMAIL_USE_TLS` | Enable TLS encryption | No | `True` |
| `EMAIL_HOST_USER` | System sender email address | No | `alerts@yourdomain.com` |
| `EMAIL_HOST_PASSWORD` | SMTP password / app password | No | Secret |
| `DEFAULT_FROM_EMAIL` | Display sender header | No | `PhysioRehab Clinic <alerts@yourdomain.com>` |
| `CELERY_BROKER_URL` | Redis broker URL | No | `redis://localhost:6379/0` |
| `CLINIC_UPI_ID` | Clinic UPI address for direct payments | No | `physiorehab@upi` |
| `SECURE_SSL_REDIRECT` | Enforce HTTPS redirect | No | `True` |
| `SECURE_HSTS_SECONDS` | HTTP Strict Transport Security duration | No | `31536000` (1 year) |

---

## 9. Troubleshooting & Operational Guidance

### 9.1 PostgreSQL Connection Refused
- **Symptom:** `psycopg.OperationalError: connection to server at "localhost", port 5432 failed: Connection refused`.
- **Solution:** Verify the actual port PostgreSQL is listening on. If PostgreSQL 18 is running alongside another instance, it often listens on port `5433`. Update `DB_PORT=5433` in `.env`.

### 9.2 SSL Redirect in Local Production Testing
- **Symptom:** Tests or local HTTP requests fail with `301 Moved Permanently`.
- **Solution:** Production settings enable `SECURE_SSL_REDIRECT = True` by default. When running local tests, export `SECURE_SSL_REDIRECT=False`.

### 9.3 Celery Broker Fallback
- **Symptom:** Redis server is not running locally.
- **Solution:** Celery automatically falls back to the filesystem broker queue stored in `celery_queue/messages/`. For production deployments, ensure Redis is running and `CELERY_BROKER_URL` is configured.

### 9.4 Internal Documentation Location
All detailed internal technical audits, migration manifesto, QA validation plans, and subscription guides are securely cataloged inside the `md/` directory:
- `md/DATABASE_ARCHITECTURE.md` — Authoritative PostgreSQL 18.6 architecture, pgAdmin 4 connection guide, backup/restore runbook, and migration procedures
- `md/DATABASE_AUDIT_REPORT.md` — Complete PostgreSQL 18.6 & pgAdmin 4 connection, schema, and integrity audit
- `md/CRUD_AUDIT_REPORT.md` — 26-entity CRUD matrix, multi-tenant RBAC verification, and defect remediation report
- `md/FINAL_PRODUCTION_AUDIT_REPORT.md` — Final deployment verification and evidence report
- `md/FINAL_PROJECT_AUDIT_CHECKLIST.md` — Complete master audit checklist
- `md/SUBSCRIPTION_ARCHITECTURE.md` — SaaS subscription model and entitlement logic
- `md/FEATURE_ENTITLEMENT_SYSTEM.md` — Feature catalog and matrix specification

*(Note: The `md/` directory is private and excluded from public version control via `.gitignore`).*

---

## 10. License & Maintenance

© 2026 PhysioRehab Management System. All rights reserved. Built for production deployment.
