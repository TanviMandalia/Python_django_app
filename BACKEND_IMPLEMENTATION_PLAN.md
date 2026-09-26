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


# Hospital & Clinic Management SaaS — Backend Implementation Guide

**Stack:** Django (`core` app) · PostgreSQL · Django REST Framework · Celery + Redis · Razorpay
**Audience:** the developer(s), or AI coding assistant, implementing the backend
**Status:** Draft v2. This is a revised and expanded version of "Backend Implementation Plan".

> **Read this first.** The code samples use illustrative names (`Hospital`, `Appointment`, `staff`, `patient`, `status`, and so on). The guide was written without access to your `core/models.py`, so **adapt every sample to the real model and field names in your project**. Do not paste samples blindly. Where a sample conflicts with your existing migrations or business logic, your existing code wins and the sample must change.

---

## Table of Contents

0. How to use this guide and rules for every contributor
1. Objectives and non-negotiables
2. Decisions to confirm (with recommendations)
3. Target architecture
4. **Phase 0** — Safety net
5. **Phase 1** — Environment, settings, database
6. **Phase 2** — Tenant isolation and data integrity
7. **Phase 3** — Identity, roles, permissions
8. **Phase 4** — Backend organisation (refactor)
9. **Phase 5** — Domain rules
10. **Phase 6** — REST API
11. **Phase 7** — Payments
12. **Phase 8** — Background jobs and notifications
13. **Phase 9** — Security and privacy
14. **Phase 10** — Observability, backups, operations
15. **Phase 11** — Testing and CI
16. **Phase 12** — Performance
17. **Phase 13** — Deployment and go-live
18. Delivery roadmap
19. Out of scope until approved
20. Appendices (env vars, packages, commands, checklists)

---

## 0. How to use this guide

- Phases are written in **delivery order**. Each phase has a **Goal**, **Steps**, and **Acceptance criteria**. A phase is done only when every acceptance criterion is demonstrably true (test output, command output, or a written document).
- Checkboxes (`- [ ]`) are meant to be copied into your issue tracker.
- "MUST" means non-negotiable. "SHOULD" means do it unless you have a written reason not to. "MAY" is optional.

### 0.1 Rules for every contributor (human or AI)

1. **Never edit or delete a migration** that has been applied to any shared or production database. Add a new migration instead.
2. **One concern per migration and one concern per pull request.** Refactors and behaviour changes never share a PR.
3. **Write the failing test first** for anything touching tenant isolation, permissions, or money.
4. **Never trust the client** for `hospital`, `role`, `price`, `amount`, `status`, or `user_id`. Derive them on the server.
5. **Every query on a tenant-owned model is scoped to a hospital** (Phase 2). No exceptions except explicitly labelled platform-admin code.
6. **No secrets in code, logs, commits, screenshots, or error messages.**
7. **No new dependency** without a note in the PR: purpose, licence, last release date, and why the standard library or Django cannot do it.
8. **Preserve URL names, template context, and the `core` app label** unless the phase explicitly says otherwise.
9. If a decision in Section 2 is unconfirmed, **flag it and ask**. Do not assume.
10. Paste the output of `pytest`, `python manage.py check`, and `python manage.py makemigrations --check --dry-run` into every PR description.

---

## 1. Objectives and non-negotiables

**Objective:** a secure, maintainable, multi-tenant Django backend for clinics and hospitals (physiotherapy first) that can be operated by a small team and grown safely.

Non-negotiable qualities, in priority order:

| # | Quality | What it means in practice |
|---|---|---|
| 1 | **Tenant isolation** | A user from Clinic A can never read, change, or even confirm the existence of Clinic B's data. |
| 2 | **Patient-data privacy** | Medical data is minimised, access-controlled, audited, and never written to logs. |
| 3 | **Money correctness** | Payments are verified server-side, idempotent, reconciled, and never double-counted. |
| 4 | **Data integrity** | The database itself rejects invalid states (constraints), not only the application code. |
| 5 | **Reliability** | Backups are tested, deployments are repeatable, jobs are retry-safe. |
| 6 | **Evolvability** | Thin views, business rules in services, tests around everything that matters. |

The existing `core` app and its migration history stay intact. This guide **evolves** working code; it does not rewrite it.

---

## 2. Decisions to confirm

Confirm these before Phase 2. Recommendations are given so you can simply approve or override.

| # | Decision | Recommendation | Why | Revisit when |
|---|---|---|---|---|
| D1 | **Database** | **PostgreSQL everywhere except throwaway scratch work.** Run it locally through Docker so dev matches production. | Partial unique indexes, exclusion constraints, row locking (`SELECT … FOR UPDATE`), and concurrency behave differently on SQLite. Bugs that only appear in production are the expensive ones. | Never for production. SQLite is acceptable for a 10-minute experiment only. |
| D2 | **Tenancy model** | **Shared database, shared schema, `hospital_id` on every tenant-owned row.** | Simplest to migrate, back up, and operate. Schema-per-tenant or database-per-tenant multiplies migration effort. | A large enterprise customer contractually requires physical isolation. |
| D3 | **API scope** | Build the **services layer now** (needed either way). Add **DRF `/api/v1/`** in Phase 6 once the first non-browser client (patient mobile app, integration) is confirmed. | A physiotherapy product almost always ends up needing exercise reminders and a patient app. Services make that cheap later. | If no mobile or integration need exists within 12 months, defer Phase 6. |
| D4 | **Authentication** | **Session auth for the website. JWT only for mobile/third-party clients**, with short access tokens (≈10 min) and rotating, blacklisted refresh tokens. | Sessions are safest for browsers. JWT adds risk and code; add it only when needed. | Mobile app is approved. |
| D5 | **User model** | If **no real users exist yet**, decide now whether to move to a custom user model (email as login). If real users exist, **keep Django's default `User`** and use profile models. | Swapping the user model after data exists is painful and risky. This is a one-time decision. | Before first production user. |
| D6 | **Role model (v1)** | Four roles: `platform_admin`, `clinic_admin`, `staff`, `patient`. **One user belongs to exactly one hospital** in v1. | Simple and covers the current models. | A therapist must work at several clinics. |
| D7 | **Hosting region** | An **India region** (for example AWS Mumbai `ap-south-1`) with **managed PostgreSQL that supports point-in-time recovery**. | Latency, and health data is personal data (see Phase 9). | Compliance advice says otherwise. |
| D8 | **Async jobs** | **Celery + Redis** in production. The filesystem broker is acceptable for quick local runs only. | Reminders, expiry checks, and email must not run inside web requests. | Volume stays tiny (cron plus management commands may suffice). |
| D9 | **Payments model** | Server is the **source of truth**; Razorpay webhooks confirm payment. **Also decide: do patient payments go to the clinic or to the platform?** | Collecting money on behalf of other businesses has legal and gateway implications (for example Razorpay Route / linked accounts). Confirm with Razorpay and an accountant. | Before building patient-to-clinic payments. |
| D10 | **Time zones** | Store UTC (`USE_TZ = True`), display `Asia/Kolkata`. | Prevents reminder and expiry bugs. | Clinics outside India onboard. |
| D11 | **Deletion policy** | **Soft delete** for patients, appointments, notes, and payments. Hard delete only via an audited retention job. | Medical and financial records have retention needs. | Legal advice on retention periods. |

Record the final answers in `docs/DECISIONS.md` (one line each, with the date).

---

## 3. Target architecture

### 3.1 Project layout

```text
config/                         # project package: settings, urls, wsgi/asgi, celery
  settings/
    base.py
    dev.py
    prod.py
    test.py
core/                           # KEEP this app label: migrations depend on it
  models/                       # may become a package; __init__ re-exports every model
  tenancy/                      # TenantOwnedModel, querysets, resolve_hospital, mixins
  permissions/                  # roles, policy functions, DRF permission classes
  services/                     # business rules (no request/response objects)
  selectors/                    # read/query functions with optimised queries
  forms/                        # validation for HTML views
  views/                        # thin: public, auth, client, staff, admin, platform, payments
  api/v1/                       # serializers, viewsets, routers (Phase 6)
  tasks/                        # Celery tasks: thin wrappers around services
  integrations/                 # razorpay.py, email/SMS providers
  management/commands/          # seed_dev_data, one-off operations
  tests/
docs/
  DECISIONS.md
  RUNBOOK.md                    # restore, incident, deploy steps
```

### 3.2 Layer rules

```text
HTTP request
   │
   ▼
View / DRF ViewSet        → authenticates, authorises, validates input (form/serializer)
   │  calls
   ▼
Service function          → business rules, transactions, permission-sensitive logic
   │  uses
   ▼
Models + Selectors        → data shape, constraints, optimised reads

Celery task ──────────────→ calls the SAME service functions (never duplicates rules)
```

- Dependencies point **downward only**. Models never import services. Services never touch `request`.
- A rule that exists in two places will eventually disagree. Put it in one service and call it from views, API, and tasks.
- Services raise **domain exceptions** (`SlotUnavailable`, `PlanLimitReached`, `InvalidTransition`). Views translate them into messages; the API translates them into `409`/`400` responses.

---

## Phase 0 — Safety net (1–2 days)

**Goal:** be able to change code without fear of silently breaking working features.

- [ ] Commit or stash all work. Tag the current state: `git tag pre-hardening`.
- [ ] Back up the current database file and export a fixture: `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 2 > backup_pre_hardening.json`. Store it **outside** the repository.
- [ ] Record Python and Django versions and freeze dependencies (`pip freeze > requirements.lock.txt`).
- [ ] Run `python manage.py makemigrations --check --dry-run`. If it reports changes, the models and migrations have drifted. Generate and **review** that migration before continuing.
- [ ] Write **characterisation tests** before any refactor:
  - For every URL name, one smoke test per role: anonymous, patient, staff, clinic admin, platform admin. Assert the current status code (`200`, `302`, `403`). Record what happens today, even if it looks wrong. Fix later, deliberately.
  - One end-to-end test each for the flows that make money or affect patients: booking an appointment, marking attendance, creating and completing a payment, writing a session note.
- [ ] Install `pre-commit` with `ruff` (lint + format) so style stays consistent from now on.
- [ ] Protect the `main` branch: pull requests only, and CI must pass.

**Acceptance criteria:** the smoke and flow tests pass on a clean checkout; `makemigrations --check` reports no changes; the pre-hardening tag and backup exist.

---

## Phase 1 — Environment, settings, database

**Goal:** a reproducible local environment that mirrors production closely enough to trust tests.

### 1.1 Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then set DJANGO_SECRET_KEY (see below)
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
docker compose up -d db redis
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_dev_data
```

`docker-compose.yml` (development only):

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: clinic
      POSTGRES_USER: clinic
      POSTGRES_PASSWORD: clinic_dev_only
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7
    ports: ["6379:6379"]
volumes:
  pgdata:
```

### 1.2 Settings structure

Split settings if they are not already split: `base.py` (shared), `dev.py`, `prod.py`, `test.py`. Read everything environment-specific from environment variables (Appendix A). The application must **refuse to start in production without a secret key and allowed hosts**.

```python
# config/settings/base.py (excerpt)
import environ

env = environ.Env()

SECRET_KEY = env("DJANGO_SECRET_KEY")                      # no default: fail loudly
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["ATOMIC_REQUESTS"] = True             # each web request is one transaction

TIME_ZONE = "Asia/Kolkata"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

### 1.3 Moving existing SQLite data to PostgreSQL (only if the data matters)

1. Take the fixture created in Phase 0.
2. Create an empty PostgreSQL database and run `python manage.py migrate`.
3. Load the fixture: `python manage.py loaddata backup_pre_hardening.json`.
4. Compare row counts per table between the old and new database, and open the admin to spot-check records.
5. If the data is only test data, skip this and use the seed command instead.

### 1.4 Seed command

`python manage.py seed_dev_data` MUST:

- refuse to run unless `DEBUG` is true (`raise CommandError`);
- be **idempotent** (`get_or_create`), so it can run twice safely;
- create **at least two hospitals** (so tenant-isolation bugs are visible immediately), each with a subscription plan, a clinic admin, two staff, five patients, and a mix of appointments in different statuses;
- print the demo credentials it created.

**Acceptance criteria:** on a fresh machine, the steps in 1.1 produce a working site and admin; `python manage.py check` passes; seeding twice creates no duplicates.

---

## Phase 2 — Tenant isolation and data integrity

**Goal:** make cross-clinic data leaks structurally difficult, and make invalid data impossible to store.

### 2.1 Audit every model

`Hospital` is the tenant boundary. Classify **every** model and record the result in a table in `docs/DECISIONS.md`. Suggested starting classification (verify against your code):

| Model | Ownership | Tenant path | Action |
|---|---|---|---|
| Hospital | Is the tenant | — | Soft-delete only |
| SubscriptionPlan | Global (platform) | — | Not tenant-owned |
| Subscription | Tenant | `hospital` FK | Add constraints |
| ClinicAdmin | Tenant | `hospital` FK | Verify |
| Staff | Tenant | `hospital` FK | Verify |
| PatientProfile | Tenant | `hospital` FK | Verify |
| Appointment | Tenant | `hospital` direct | Add `hospital` if only reachable through patient/staff |
| Attendance | Tenant | via staff, **denormalise `hospital`** | Add FK |
| SessionNote | Tenant | via appointment, **denormalise `hospital`** | Add FK |
| Task | Tenant | **denormalise `hospital`** | Add FK |
| Payment | Tenant (and platform view) | `hospital` FK | Add constraints |
| SupportTicket | Tenant; visible to platform | `hospital` FK | Platform sees tickets only |
| Notification | Recipient user | via user, **denormalise `hospital`** | Add FK |
| Blog | Platform-wide or clinic-specific | nullable `hospital` | Nullable = platform-wide |

**Rule:** put `hospital` directly on every tenant-owned table, even when it is reachable through a relation. It makes filters fast, constraints simple, and Postgres row-level security possible later. Keep it consistent with the relations (see 2.2).

### 2.2 Base class and scoped queryset

```python
# core/tenancy/models.py
from django.core.exceptions import ValidationError
from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_hospital(self, hospital):
        """Every tenant-owned query MUST pass through this (or an equivalent filter)."""
        if hospital is None:
            return self.none()          # fail closed
        return self.filter(hospital=hospital)


class TenantOwnedModel(models.Model):
    hospital = models.ForeignKey(
        "core.Hospital",
        on_delete=models.PROTECT,       # deleting a clinic must never cascade silently
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True

    def assert_same_hospital(self, *related):
        """Related records must belong to the same clinic as this record."""
        for obj in related:
            if obj is not None and obj.hospital_id != self.hospital_id:
                raise ValidationError("Related record belongs to a different clinic.")
```

Services MUST call `full_clean()` (which calls each model's `clean()`) before saving, because Django does not do it automatically on `save()`.

> **Design note:** this guide uses **explicit** scoping (`.for_hospital(...)`) instead of automatic thread-local scoping. Automatic scoping is convenient, but it fails silently in Celery tasks, shells, and tests, which is exactly where leaks hide. Explicit is easier to review and to test.

### 2.3 Resolve the current hospital from the authenticated user only

Never take the hospital from a URL parameter, form field, header, or request body.

```python
# core/tenancy/context.py
def resolve_hospital(user):
    """Return the user's hospital, or None (platform admins and anonymous users have none)."""
    if not user.is_authenticated or user.is_superuser:
        return None
    for relation in ("clinicadmin", "staff", "patientprofile"):   # adapt to real related names
        profile = getattr(user, relation, None)
        if profile is not None:
            return profile.hospital
    return None
```

### 2.4 Use it in class-based views

```python
# core/tenancy/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class TenantViewMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        request.hospital = resolve_hospital(request.user)
        if request.hospital is None:
            raise PermissionDenied("No clinic is associated with this account.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().for_hospital(self.request.hospital)
```

For function-based views, always use:

```python
appointment = get_object_or_404(Appointment.objects.for_hospital(request.hospital), pk=pk)
```

**Cross-tenant access returns `404`, not `403`.** A `403` confirms the record exists.

### 2.5 Constraints and indexes (illustrative; adapt to your fields)

Define choice enums at **module level** (a nested `Meta` cannot see the enclosing class body).

```python
# core/models/appointments.py
from django.db import models
from django.db.models import Q


class AppointmentStatus(models.TextChoices):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(TenantOwnedModel):
    patient = models.ForeignKey("core.PatientProfile", on_delete=models.PROTECT)
    staff = models.ForeignKey("core.Staff", on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(
        max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.REQUESTED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # From the original plan: one slot per hospital, patient, date, and time.
            models.UniqueConstraint(
                fields=["hospital", "patient", "date", "time"],
                condition=~Q(status="cancelled"),
                name="uniq_appt_patient_slot",
            ),
            # Added: a practitioner cannot be double-booked in the same slot.
            models.UniqueConstraint(
                fields=["hospital", "staff", "date", "time"],
                condition=~Q(status="cancelled"),
                name="uniq_appt_staff_slot",
            ),
            # Status must be one of the allowed values even if someone bypasses forms.
            models.CheckConstraint(
                condition=Q(status__in=[s.value for s in AppointmentStatus]),  # Django < 5.1: use check=
                name="appt_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["hospital", "date", "status"], name="appt_hosp_date_status_idx"),
            models.Index(fields=["hospital", "staff", "date"], name="appt_hosp_staff_date_idx"),
            models.Index(fields=["hospital", "-created_at"], name="appt_hosp_created_idx"),
        ]
```

Other constraints to add:

| Rule | Constraint |
|---|---|
| One attendance record per staff member per day | `UniqueConstraint(fields=["staff", "date"], name="uniq_attendance_staff_date")` |
| One **active** subscription per hospital | `UniqueConstraint(fields=["hospital"], condition=Q(status="active"), name="uniq_active_subscription_per_hospital")` |
| Valid subscription and payment status values | `CheckConstraint` using a module-level `TextChoices` |
| Payment amount is positive | `CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive")` |
| Gateway payment ID unique when present | `UniqueConstraint(fields=["gateway_payment_id"], condition=~Q(gateway_payment_id=""), name="uniq_gateway_payment_id")` |

**Index rule of thumb:** put `hospital` first in composite indexes, because almost every query filters by it. Index what you filter and sort by; do not index everything.

**Optional, PostgreSQL only: overlapping-time protection.** If appointments have a duration, a unique constraint on the start time is not enough. Use an exclusion constraint on a time range (requires the `btree_gist` extension, added in a migration with `BtreeGistExtension()`):

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators

# field:  time_range = DateTimeRangeField()
ExclusionConstraint(
    name="no_overlapping_staff_appointments",
    expressions=[("staff", RangeOperators.EQUAL), ("time_range", RangeOperators.OVERLAPS)],
    condition=~Q(status="cancelled"),
)
```

### 2.6 Adding `hospital` to existing tables safely (three separate migrations)

Never add a non-null column to a populated table in one step.

1. **Add nullable:** `hospital = ForeignKey("core.Hospital", null=True, on_delete=PROTECT)`.
2. **Backfill** from an existing guaranteed relation, then fail loudly if anything is left:

```python
from django.db.models import OuterRef, Subquery


def backfill_appointment_hospital(apps, schema_editor):
    Appointment = apps.get_model("core", "Appointment")
    Staff = apps.get_model("core", "Staff")
    Appointment.objects.filter(hospital__isnull=True).update(
        hospital_id=Subquery(Staff.objects.filter(pk=OuterRef("staff_id")).values("hospital_id")[:1])
    )
    orphans = Appointment.objects.filter(hospital__isnull=True).count()
    if orphans:
        raise RuntimeError(f"{orphans} appointments have no derivable hospital; resolve manually.")

# operations = [migrations.RunPython(backfill_appointment_hospital, migrations.RunPython.noop)]
```

3. **Make non-null** (`null=False`) in a follow-up migration, then add constraints and indexes.

Rehearse all three on a **copy of production data** before running them for real.

### 2.7 Optional defence in depth: PostgreSQL row-level security

Later, once the application layer is solid, you MAY add RLS policies (`hospital_id = current_setting('app.hospital_id')::bigint`) and set the value with `SET LOCAL` inside each request's transaction. This protects against a forgotten filter. It adds operational complexity (connection pooling, migrations, superuser bypass), so treat it as a hardening step, not a starting point.

### 2.8 Tests that prove isolation

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_clinic_admin_cannot_open_another_clinics_appointment(client, clinic_a_admin, clinic_b_appointment):
    client.force_login(clinic_a_admin)
    response = client.get(reverse("appointment_detail", args=[clinic_b_appointment.pk]))  # adapt URL name
    assert response.status_code == 404


@pytest.mark.django_db
def test_clinic_admin_cannot_modify_another_clinics_appointment(client, clinic_a_admin, clinic_b_appointment):
    client.force_login(clinic_a_admin)
    response = client.post(reverse("appointment_update", args=[clinic_b_appointment.pk]), {"status": "cancelled"})
    assert response.status_code == 404
    clinic_b_appointment.refresh_from_db()
    assert clinic_b_appointment.status != "cancelled"
```

Add a **meta-test** so nobody forgets the base class:

```python
from django.apps import apps
from core.tenancy.models import TenantOwnedModel

EXEMPT = {"Hospital", "Blog"}          # Blog has a nullable hospital (platform-wide posts)

def test_every_model_with_a_hospital_field_is_tenant_owned():
    offenders = [
        m.__name__
        for m in apps.get_app_config("core").get_models()
        if any(f.name == "hospital" for f in m._meta.get_fields())
        and not issubclass(m, TenantOwnedModel)
        and m.__name__ not in EXEMPT
    ]
    assert offenders == []
```

Also add: a test per tenant-owned list/detail/update/delete endpoint that Clinic A gets `404` for Clinic B's record ID, and a test that created records get the **server-derived** hospital even if the request body contains a different `hospital` value.

**Acceptance criteria:** tenant-isolation tests pass for every tenant-owned model and view; constraints reject duplicates and invalid statuses at the database level (tested with `pytest.raises(IntegrityError)`); all new columns are non-null and backfilled; migrations apply cleanly to a copy of real data.

---

## Phase 3 — Identity, roles, permissions

**Goal:** one clear definition of "who may do what", used identically by HTML views, API, and tasks.

### 3.1 Single source of truth

```python
# core/permissions/roles.py
from enum import StrEnum


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    CLINIC_ADMIN = "clinic_admin"
    STAFF = "staff"
    PATIENT = "patient"


def get_role(user) -> Role | None:
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Role.PLATFORM_ADMIN
    if hasattr(user, "clinicadmin"):     # adapt related names
        return Role.CLINIC_ADMIN
    if hasattr(user, "staff"):
        return Role.STAFF
    if hasattr(user, "patientprofile"):
        return Role.PATIENT
    return None
```

Write **policy functions** in `core/permissions/policies.py` (`can_view_patient(user, patient)`, `can_edit_session_note(user, note)`, and so on). HTML views, DRF permission classes, and services call the same functions, so behaviour can never diverge.

### 3.2 Permission matrix (v1 target)

`C` create · `R` read · `U` update · `D` delete or cancel · `—` no access

| Resource | Platform admin | Clinic admin | Staff (therapist) | Patient |
|---|---|---|---|---|
| Hospitals and plans | CRUD | R own hospital | — | — |
| Subscriptions | CRUD (billing operations) | R own; start renewal | — | — |
| Staff accounts | R (support, audited) | CRUD own clinic | R and U self | — |
| Patient profiles | — (break-glass only) | CRUD own clinic | R/U **assigned** patients | R/U self (limited fields) |
| Appointments | — | CRUD own clinic | R/U own; create for assigned patients | R own; C (request); D (cancel own before cutoff) |
| Session notes | — | R own clinic | C/R/U own (locked after N hours) | R notes marked patient-visible |
| Attendance | — | R own clinic; correct with audit | C/R own (one per day) | — |
| Tasks / exercises | — | CRUD | R/U assigned | R own; mark complete |
| Payments | R aggregate and reconcile | R own clinic; refund | — | R own; C (pay) |
| Support tickets | CRUD all | CRU own clinic | C/R own | C/R own |
| Notifications | R delivery logs | R/U own | R/U own | R/U own |
| Blogs | CRUD platform-wide | CRUD clinic-specific | — | R published |
| Audit log | R all | R own clinic | — | — |

Principles:

- **Platform admins do not see patient medical data by default.** Support access uses a time-limited, reason-recorded **break-glass grant**, and every use is written to the audit log.
- **Least privilege for staff:** decide whether therapists see all clinic patients or only assigned ones. The recommendation is *assigned only* for clinical notes.
- **Default deny:** anything not explicitly allowed is refused.

### 3.3 Tests

For every endpoint and view, a parametrised test across roles asserting the expected status (`200`/`302`/`403`/`404`). The matrix above is the specification; if the matrix changes, the tests change in the same PR.

**Acceptance criteria:** the role × resource matrix is covered by automated tests; no view relies on template-level hiding as its only protection; break-glass access is implemented (or explicitly documented as not available) and audited.

---