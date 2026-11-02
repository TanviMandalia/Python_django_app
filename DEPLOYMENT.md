# Production Deployment & Operations Guide
**PhysioRehab Multi-Clinic SaaS Platform**

---

## 1. Supported Deployment Targets

The application is built to run on standard modern cloud container and PaaS environments:
1. **Render.com** (Recommended for Web Service + Worker architecture)
2. **Vercel** (Serverless WSGI deployment with external Supabase PostgreSQL)
3. **AWS / Railway / Self-Hosted VPS** (Docker / Gunicorn)

---

## 2. Production Environment Variables Checklist

Before initiating deployment, configure these environment variables in your hosting provider's dashboard (e.g., Render Environment settings):

### A. Core Django & Security
```bash
DJANGO_SETTINGS_MODULE=myproject.settings.production
SECRET_KEY=generate-a-strong-random-50-character-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,*.onrender.com,*.vercel.app
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://*.onrender.com
```

### B. Supabase PostgreSQL Database
```bash
# Transaction pooled connection string (port 6543)
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
```

### C. Administrative & Email Identity Separation
```bash
# Platform Super Admin Identity (Platform Owner)
PLATFORM_SUPERADMIN_EMAIL=techcraft1215@gmail.com

# Clinic Operational Identity (Dr. Dhvani Patalia Physio Rehab)
CLINIC_NAME=Dr. Dhvani Patalia Physio Rehab
CLINIC_EMAIL=physio.rehab.guj@gmail.com
CLINIC_NOTIFICATION_EMAIL=physio.rehab.guj@gmail.com
CLINIC_PHONE=+91 94095 10501
CLINIC_CITY=Jamnagar
```

### D. Transactional Email Delivery (SMTP / Provider)
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=physio.rehab.guj@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=Dr. Dhvani Patalia Physio Rehab <physio.rehab.guj@gmail.com>
```

---

## 3. Build & Release Pipeline (`build.sh`)

Ensure your deployment build script runs the standard asset pipeline and safe schema migrations:

```bash
#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "==> Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static assets..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Deployment build completed successfully."
```

---

## 4. Web Process Startup (`Procfile`)

For Render, Railway, or Heroku, use Gunicorn with the optimized `gunicorn.conf.py`:

```procfile
web: gunicorn myproject.wsgi:application -c gunicorn.conf.py
```

### Server Configuration (`gunicorn.conf.py`):
- **Workers**: `2` (suitable for memory-efficient concurrency)
- **Threads**: `4` per worker
- **Worker Class**: `gthread`
- **Timeout**: `60` seconds

---

## 5. Post-Deployment Verification Checklist

Once deployed, perform these verification checks:

1. **Public Booking Verification**:
   - Visit `/book-appointment/`.
   - Submit a test appointment request.
   - Confirm status is set to `pending`.
   - Verify notification arrives at `physio.rehab.guj@gmail.com` and configured clinic recipients.
   - Verify that `techcraft1215@gmail.com` did NOT receive the clinic booking email.
2. **Clinic Admin Access**:
   - Log in to `/admin-settings/`.
   - Verify clinic details show `physio.rehab.guj@gmail.com`.
   - Verify notification recipient management (add test recipient, test mute toggle).
3. **Platform Super Admin Access**:
   - Log in with `techcraft1215`.
   - Access `/super-admin/platform-settings/`.
   - Verify platform settings and clinics overview load correctly.
4. **Log Inspection**:
   - Check application logs to confirm email masking (`p**************j@gmail.com`).
   - Confirm no database passwords or secret keys appear in stdout.
