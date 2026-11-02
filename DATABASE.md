# Database Architecture & PostgreSQL Schema Documentation
**PhysioRehab Multi-Clinic SaaS Platform**

---

## 1. Engine & Environment

The PhysioRehab application uses **PostgreSQL 15+** (specifically configured and optimized for **Supabase PostgreSQL** in cloud environments and local PostgreSQL 18.6 in development).

### Key Configuration Directives:
- **Encoding**: `UTF-8`
- **Time Zone**: `Asia/Kolkata` (`USE_TZ = True`)
- **Connection Handling**:
  - Direct connection on port `5432` for administrative migrations.
  - Connection pooling on port `6543` (Supabase PgBouncer / Transaction pooler) for serverless web dynos to avoid connection exhaustion.

---

## 2. Core Schema & Data Dictionary

### A. `core_platformsettings` (Platform Super Admin Settings)
Singleton table storing platform-level configuration and Super Admin identity.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY` | Record ID (always 1) |
| `platform_name` | `VARCHAR(120)` | `NOT NULL` | Brand name of SaaS platform |
| `super_admin_email` | `VARCHAR(254)` | `NOT NULL` | Platform owner email (`techcraft1215@gmail.com`) |
| `super_admin_username` | `VARCHAR(150)` | `NOT NULL` | Super Admin username (`techcraft1215`) |
| `system_alert_email` | `VARCHAR(254)` | `NOT NULL` | Target for security and system logs |
| `support_email` | `VARCHAR(254)` | `NOT NULL` | Public support email for clinic tenants |
| `maintenance_mode` | `BOOLEAN` | `DEFAULT FALSE` | Global maintenance gate |
| `maintenance_message`| `TEXT` | `BLANK` | Custom banner for visitors during upgrades |
| `updated_at` | `TIMESTAMP WITH TZ` | `AUTO_NOW` | Last modification timestamp |

### B. `core_hospital` (Clinic Tenant Model)
The root tenant record. Every clinical entity belongs to a hospital.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY` | Clinic unique ID |
| `name` | `VARCHAR(200)` | `NOT NULL` | Clinic legal name |
| `slug` | `SLUG` | `UNIQUE, NOT NULL` | URL-safe identifier (e.g., `dr-dhvani-patalia-physio-rehab`) |
| `email` | `VARCHAR(254)` | `NOT NULL` | Primary public contact email |
| `phone` | `VARCHAR(30)` | `NOT NULL` | Clinic telephone number |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Active tenant status |
| `created_at` | `TIMESTAMP WITH TZ` | `AUTO_NOW_ADD` | Registration timestamp |

### C. `core_clinicsettings` (Clinic Operational Configuration)
Operational settings specific to each clinic.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY` | Settings ID |
| `hospital_id` | `BIGINT` | `UNIQUE, FK -> core_hospital` | Associated clinic |
| `clinic_name` | `VARCHAR(200)` | `NOT NULL` | Branded display name |
| `email` | `VARCHAR(254)` | `NOT NULL` | Clinic operational email |
| `primary_doctor_email` | `VARCHAR(254)` | `BLANK` | Primary doctor appointment alert target |
| `appointment_notification_enabled` | `BOOLEAN` | `DEFAULT TRUE` | Master toggle for appointment alerts |
| `lead_notification_enabled` | `BOOLEAN` | `DEFAULT TRUE` | Master toggle for website lead alerts |

### D. `core_clinicnotificationrecipient` (Multi-Email Routing Registry)
Enables multiple categorized notification recipients per clinic.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY` | Recipient ID |
| `hospital_id` | `BIGINT` | `FK -> core_hospital` | Associated clinic |
| `name` | `VARCHAR(150)` | `NOT NULL` | Full name / desk title (e.g., "Dr. Dhvani Patalia") |
| `email` | `VARCHAR(254)` | `NOT NULL` | Validated email address |
| `recipient_type` | `VARCHAR(20)` | `NOT NULL` | Role: `doctor`, `admin`, `coordinator`, `billing`, `general` |
| `notify_on_appointment` | `BOOLEAN` | `DEFAULT TRUE` | Receives appointment booking alerts |
| `notify_on_contact_inquiry` | `BOOLEAN` | `DEFAULT TRUE` | Receives website contact lead alerts |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Active routing status (mute/unmute) |
| `created_at` | `TIMESTAMP WITH TZ` | `AUTO_NOW_ADD` | Created date |

**Unique Constraint**:
```sql
ALTER TABLE "core_clinicnotificationrecipient" 
ADD CONSTRAINT "unique_hospital_email" 
UNIQUE ("hospital_id", "email");
```

---

## 3. Migration History & Migration `0052`

The database schema evolution is tracked linearly across 52 migrations in `core/migrations/`:

- **`0001_initial.py` to `0050_...`**: Foundational clinic management, EHR, billing, and patient records.
- **`0051_hospital_razorpay_account_id...`**: Payment gateway integration.
- **`0052_platformsettings_and_more.py`**:
  - Adds `PlatformSettings` singleton model.
  - Adds `ClinicNotificationRecipient` multi-email registry model.
  - Adds `appointment_notification_enabled`, `lead_notification_enabled`, and `primary_doctor_email` to `ClinicSettings`.
  - Enforces `unique_together = ("hospital", "email")`.

### Safe Migration Execution Command:
```bash
# Verify pending migrations without modifying schema
python manage.py showmigrations

# Apply pending migrations
python manage.py migrate core
```

---

## 4. Query Performance & Indexing Strategy

1. **Foreign Key Indices**: All foreign keys to `core_hospital` are indexed by default in PostgreSQL, ensuring $O(\log N)$ joins for tenant filtering.
2. **Deterministic Lookup Indexing**:
   - `Hospital.objects.filter(is_active=True).order_by('id')` ensures high-speed resolution during public booking requests.
   - Lookups on `slug` utilize the unique B-tree index on `core_hospital.slug`.
3. **Recipient Resolution Query**:
   ```python
   # Optimized single-query recipient fetch
   recipients = hospital.notification_recipients.filter(
       is_active=True, 
       notify_on_appointment=True
   ).values_list("email", flat=True)
   ```

---

## 5. Supabase Backup & Disaster Recovery

1. **Point-In-Time Recovery (PITR)**: Supabase PostgreSQL provides automated continuous backups with point-in-time restore capability.
2. **Logical Dumps**:
   ```bash
   # Create a compressed logical dump before executing production maintenance
   pg_dump "postgres://user:password@host:5432/postgres" -Fc > backup_pre_migration.dump
   ```
3. **Rollback Strategy**:
   - Migration `0052` is backward-compatible and additive. Rolling back can be achieved safely with:
     ```bash
     python manage.py migrate core 0051
     ```
   - No existing patient records, user profiles, or appointment bookings are modified or dropped.
