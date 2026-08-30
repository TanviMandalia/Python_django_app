# 🏥 PhysioRehab — Advanced Physiotherapy Practice & Hospital Management

A modern, production-ready Django web application designed for physiotherapy clinics and multi-tenant healthcare practices. Built for **Dr. Dhvani Patalia (PT)** with responsive dashboards across 4 key roles plus platform SaaS administration.

---

## 🚀 Key Features

- **4 Dedicated Responsive Dashboards**:
  - 🛡️ **Clinic Admin**: Patient management, staff rosters, attendance logs, salary slips, tasks, clinic branding, reviews, blogs, and promos.
  - 🩺 **Doctor / Physiotherapist**: Clinical assessment, diagnosis records, therapy modalities, session notes, and treatment progress tracking.
  - 👥 **Staff / Assistant**: Multi-shift attendance (Morning 10 AM-1 PM & Evening 4 PM-8 PM), leave applications, daily task checklists, and salary history.
  - 👤 **Client / Patient**: Seamless appointment booking, session history, live chat with clinic, Razorpay online payments & UPI receipts, review submissions.
  - 🌐 **Super Admin**: SaaS hospital tenant management, subscription packages, and payment reconciliation.
- **Enterprise Security & RBAC**: Custom decorators prevent cross-role privilege escalation.
- **Automated Document Exports**: Download Patient Directory, Appointments, Analytics, and Payments in formatted **Excel (`.xlsx`)** or **PDF (`.pdf`)**.
- **Automated Background Reminders**: Management commands to dispatch daily shift reminders and upcoming appointment alerts.

---

## 🛠️ Quickstart Installation

### 1. Clone & Activate Virtual Environment
```bash
git clone https://github.com/TanviMandalia/Python_django_app.git
cd Python_django_app

# Create and activate virtual environment
python -m venv venv
# On Windows PowerShell:
venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Seed Demo Test Data (All 4 Dashboards)
```bash
python manage.py seed_demo_data
```

### 6. Run the Development Server
```bash
python manage.py runserver
```
Visit **http://127.0.0.1:8000** in your browser.

---

## 🔑 Default Test Accounts

| Role | Username | Password | Dashboard URL |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `superadmin` | `superadmin123` | `/super-admin/` |
| **Clinic Admin** | `admin` | `admin123` | `/admin-dashboard/` |
| **Doctor (PT)** | `doctor_dhvani` | `doctor123` | `/progress-tracking/` |
| **Staff Member** | `staff_rahul` | `staff123` | `/staff-dashboard/` |
| **Patient** | `patient_priya` | `client123` | `/dashboard/` |

---

## 🧪 Running Automated Tests

Run the full test suite with Django's test runner:
```bash
python manage.py test core
```
*All 22 unit and integration tests covering Authentication, RBAC, Appointments, Attendance Shifts, Payments, and Exports will execute.*

---

## 📖 Additional Documentation
- [AI Architectural Guide (`AI_GUIDE.md`)](AI_GUIDE.md): Complete blueprint for AI agents and engineers explaining models, services, and routing.
- [Release Notes (`RELEASE_NOTES.md`)](RELEASE_NOTES.md): Comprehensive changelog of all improvements.

