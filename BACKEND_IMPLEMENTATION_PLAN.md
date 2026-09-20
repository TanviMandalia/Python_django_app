# Backend Implementation Plan

## Objective

Build a secure, maintainable Django backend for a multi-clinic physiotherapy SaaS platform. The current `core` application and its migration history remain intact; this plan evolves them safely instead of replacing working business logic.

## Current Foundation

The project already includes Django models and migrations for hospitals, subscriptions, clinic administrators, staff, appointments, patient profiles, attendance, session notes, tasks, payments, support tickets, notifications, and blogs. Development is configured for SQLite and production is configured for PostgreSQL.

## Decisions Required Before Implementation

1. **Database:** SQLite for local-only use, or PostgreSQL for the production SaaS environment.
2. **Tenancy:** Confirm that each hospital must only access its own staff, patients, appointments, payments, and content.
3. **API scope:** Browser-rendered Django pages only, or a REST API for mobile apps and external integrations as well.
4. **Authentication:** Keep Django session authentication only, or add JWT tokens for API/mobile clients.
5. **Deployment:** Choose the production host and managed PostgreSQL provider.

## Phase 1 — Local Environment and Database

1. Install Python 3.12+ and recreate the local virtual environment.
2. Install the pinned Python dependencies from `requirements.txt`.
3. Create `.env` from `.env.example` and provide a local `DJANGO_SECRET_KEY`.
4. Run the existing migrations against SQLite for local development.
5. Create a Django superuser and seed an initial subscription plan and hospital.
6. Add a repeatable management command for development seed data.

**Acceptance criteria:** `python manage.py check`, `python manage.py migrate`, and the Django admin all work with a new local database.

## Phase 2 — Tenant Isolation and Data Integrity

1. Define `Hospital` as the tenant boundary.
2. Review every clinic-owned model and ensure it can be associated with a hospital directly or through a guaranteed relation.
3. Apply tenant-scoped query helpers or custom managers so views never return records from another hospital.
4. Add database constraints for duplicate or invalid data, including:
   - one appointment slot per hospital, patient, date, and time;
   - one attendance record per staff member and date;
   - one active subscription per hospital;
   - valid payment and subscription status values.
5. Add indexes for common queries: hospital, patient, staff, appointment date/status, payment status, and created timestamps.
6. Create data migrations only where existing records need a safe hospital assignment.

**Acceptance criteria:** tenant-isolation tests prove that a clinic administrator cannot read or modify another clinic's data.

## Phase 3 — Backend Organization

1. Keep `core` as the Django app label so existing migrations and database tables remain stable.
2. Split the large view module incrementally into feature modules without changing URLs:
   - `core/views/public.py`
   - `core/views/auth.py`
   - `core/views/client.py`
   - `core/views/staff.py`
   - `core/views/admin.py`
   - `core/views/platform.py`
   - `core/views/payments.py`
3. Move reusable business rules from views into `core/services/` modules.
4. Move validation into Django forms and model validation methods.
5. Preserve current URL names and page behaviour throughout the refactor.

**Acceptance criteria:** URLs, templates, and management commands work exactly as before while backend code is grouped by responsibility.

## Phase 4 — APIs and Authentication

1. Add Django REST Framework when an API or mobile app is required.
2. Version endpoints under `/api/v1/`.
3. Start with endpoints for authentication, profile, appointments, session notes, notifications, payments, and clinic administration.
4. Use serializers to validate input and avoid exposing internal fields.
5. Add permission classes for platform admin, clinic admin, staff, and patient roles.
6. Use session authentication for the existing website; add JWT only if mobile or third-party API access is approved.
7. Document the API with OpenAPI/Swagger.

**Acceptance criteria:** authenticated API tests cover valid access, forbidden cross-clinic access, validation failures, and pagination.

## Phase 5 — Payments, Notifications, and Background Jobs

1. Keep payment gateway secrets only in environment variables or a dedicated secret manager.
2. Verify Razorpay webhook signatures before updating payment records.
3. Make webhook processing idempotent so repeated gateway events do not duplicate payments.
4. Use Celery for appointment reminders, exercise reminders, subscription expiry checks, and email delivery.
5. Use Redis or a managed message broker in production; keep the filesystem broker for local development only.
6. Record notification and payment audit events for support and debugging.

**Acceptance criteria:** webhook and scheduled-task tests demonstrate reliable, duplicate-safe processing.

## Phase 6 — Security and Operations

1. Use PostgreSQL, `DEBUG=False`, HTTPS-only cookies, HSTS, secure CSRF origins, and restricted allowed hosts in production.
2. Enforce password policy, login rate limiting, session expiry, and role-based permissions.
3. Add structured logs without passwords, tokens, payment secrets, or sensitive medical data.
4. Configure daily encrypted PostgreSQL backups and regularly test a restore.
5. Add health-check endpoints and error monitoring.
6. Run migrations as a separate deployment step before application instances start.

**Acceptance criteria:** the Django deployment checklist passes and a backup restoration test is documented.

## Phase 7 — Testing and CI

1. Add model tests for constraints, status transitions, and tenant ownership.
2. Add service tests for appointments, subscriptions, reminders, and payments.
3. Add view/API permission tests for every user role.
4. Run tests against PostgreSQL in CI once the production schema is adopted.
5. Add formatting, linting, migration consistency, and security checks to GitHub Actions.

**Acceptance criteria:** CI blocks merges when tests, migrations, linting, or security checks fail.

## Delivery Order

1. Confirm database and tenancy decisions.
2. Repair the local Python environment and create the development database.
3. Implement tenant constraints and tests.
4. Refactor backend modules feature by feature.
5. Add API support if required.
6. Harden payments, Celery, production deployment, backups, and monitoring.

## Out of Scope Until Approved

- Replacing Django authentication with a custom user model.
- Changing historical migration labels or deleting production data.
- Introducing a mobile app, public API, or JWT authentication.
- Migrating to PostgreSQL before a backup and rollback plan is ready.
