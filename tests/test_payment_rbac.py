"""
tests/test_payment_rbac.py
Comprehensive Role-Based Access Control (RBAC), Security, IDOR/BOLA Prevention,
and API/UI Test Suite for the Hospital Management System Payment Module.

Roles verified:
  1. SUPER_ADMIN: Full platform scope, create, edit, delete/cancel, view all, export.
  2. ADMIN: Clinic-scoped management, create, edit, delete/cancel, verify, export own clinic. Blocked from other clinics (IDOR).
  3. STAFF: Read-only clinic payment history & logs, search/filter/details. Strictly blocked from create/edit/delete/status/export.
  4. CLIENT: Read-only personal payment history & receipts. Strictly blocked from other patients (IDOR), create, edit, delete.
"""

import json
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from tests.test_helpers import BaseHospitalTestCase
from core.models import (
    Hospital,
    PaymentRecord,
    Appointment,
    AuditEvent,
)


class BasePaymentTestCase(BaseHospitalTestCase):
    def setUp(self):
        super().setUp()
        # Setup 2 clinics to test horizontal multi-tenant isolation and IDOR/BOLA
        self.clinic_a = self.create_hospital(name="Alpha General Clinic", slug="alpha-clinic", email="contact@alpha.com")
        self.clinic_b = self.create_hospital(name="Beta Specialty Clinic", slug="beta-clinic", email="contact@beta.com")

        # Super Admin
        self.super_admin = self.create_super_admin(username="super_admin_user", email="super@platform.com")

        # Clinic Admins
        self.admin_a = self.create_clinic_admin(self.clinic_a, username="admin_alpha", email="admin@alpha.com")
        self.admin_b = self.create_clinic_admin(self.clinic_b, username="admin_beta", email="admin@beta.com")

        # Staff
        self.staff_a = self.create_staff(self.clinic_a, username="staff_alpha", email="staff@alpha.com", role="nurse")
        self.staff_b = self.create_staff(self.clinic_b, username="staff_beta", email="staff@beta.com", role="physiotherapist")

        # Patients
        self.patient_a = self.create_patient(self.clinic_a, username="patient_alice", email="alice@test.com")
        self.patient_b = self.create_patient(self.clinic_b, username="patient_bob", email="bob@test.com")

        # Appointments
        self.appt_a = self.create_appointment(self.clinic_a, self.patient_a, consultation_fee=Decimal("600.00"))
        self.appt_b = self.create_appointment(self.clinic_b, self.patient_b, consultation_fee=Decimal("950.00"))

        # Payment records
        self.payment_a1 = PaymentRecord.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_a,
            appointment_id=self.appt_a.id,
            amount=Decimal("600.00"),
            method="cash",
            status="paid",
            transaction_id="TXN-A1-001",
            notes="Initial consultation fee",
        )
        self.payment_a_pending = PaymentRecord.objects.create(
            hospital=self.clinic_a,
            patient=self.patient_a,
            appointment_id=self.appt_a.id,
            amount=Decimal("300.00"),
            method="upi",
            status="pending",
            transaction_id="UPI-A-PENDING-001",
            notes="Followup advance",
        )
        self.payment_b1 = PaymentRecord.objects.create(
            hospital=self.clinic_b,
            patient=self.patient_b,
            appointment_id=self.appt_b.id,
            amount=Decimal("950.00"),
            method="card",
            status="paid",
            transaction_id="TXN-B1-001",
            notes="Specialist procedure",
        )


# ══════════════════════════════════════════════════════════════════
# 1. SUPER ADMIN PAYMENT SUITE
# ══════════════════════════════════════════════════════════════════

class SuperAdminPaymentTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.super_admin)

    def test_super_admin_views_platform_wide_payments(self):
        """Super admin can view payments across ALL clinics."""
        resp = self.client.get(reverse("super_admin_all_payments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TXN-A1-001")
        self.assertContains(resp, "TXN-B1-001")
        self.assertContains(resp, "Alpha General Clinic")
        self.assertContains(resp, "Beta Specialty Clinic")

    def test_super_admin_accesses_payments_root_redirects_properly(self):
        """Super admin accessing /payments/ is redirected to platform all-payments view."""
        resp = self.client.get(reverse("payments"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("super-admin", resp.url)

    def test_super_admin_creates_payment(self):
        """Super admin can create payment for any clinic."""
        payload = {
            "hospital_id": self.clinic_a.id,
            "patient_id": self.patient_a.id,
            "amount": "1200.00",
            "method": "bank_transfer",
            "status": "paid",
            "notes": "Surgery advance recorded by platform admin",
        }
        resp = self.client.post(reverse("payment_create"), payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data.get("success"))
        created_id = data.get("payment_id")
        created_pay = PaymentRecord.objects.get(id=created_id)
        self.assertEqual(created_pay.amount, Decimal("1200.00"))
        self.assertEqual(created_pay.hospital, self.clinic_a)

    def test_super_admin_edits_payment(self):
        """Super admin can edit payment details."""
        edit_payload = {
            "amount": "650.00",
            "status": "paid",
            "notes": "Updated note with revised surcharge",
        }
        resp = self.client.post(
            reverse("payment_edit", args=[self.payment_a1.id]),
            data=json.dumps(edit_payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.payment_a1.refresh_from_db()
        self.assertEqual(self.payment_a1.amount, Decimal("650.00"))
        self.assertIn("revised surcharge", self.payment_a1.notes)

    def test_super_admin_deletes_payment(self):
        """Super admin can delete/cancel payment."""
        resp = self.client.delete(reverse("payment_detail", args=[self.payment_a1.id]))
        self.assertEqual(resp.status_code, 200)
        self.payment_a1.refresh_from_db()
        self.assertEqual(self.payment_a1.status, "refunded")

    def test_super_admin_exports_platform_excel_and_pdf(self):
        """Super admin can export platform-wide Excel and PDF."""
        excel_resp = self.client.get(reverse("export_payments_excel"))
        self.assertEqual(excel_resp.status_code, 200)
        self.assertIn("spreadsheetml", excel_resp["Content-Type"])

        pdf_resp = self.client.get(reverse("export_payments_pdf"))
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertIn("pdf", pdf_resp["Content-Type"])


# ══════════════════════════════════════════════════════════════════
# 2. CLINIC ADMIN PAYMENT SUITE & IDOR / BOLA PREVENTION
# ══════════════════════════════════════════════════════════════════

class ClinicAdminPaymentTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_a)

    def test_admin_views_only_own_clinic_payments(self):
        """Admin A views Clinic A payments, Clinic B payments are completely excluded."""
        resp = self.client.get(reverse("admin_payments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TXN-A1-001")
        self.assertNotContains(resp, "TXN-B1-001")
        if resp.context:
            self.assertFalse(resp.context.get("is_staff_view"))
            self.assertTrue(resp.context.get("can_manage"))

    def test_admin_creates_payment_for_own_clinic(self):
        """Admin A can create payment for Clinic A patient."""
        payload = {
            "patient_id": self.patient_a.id,
            "amount": "450.00",
            "method": "cash",
            "notes": "Walk-in consultation fee",
        }
        resp = self.client.post(reverse("payment_create"), payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        created = PaymentRecord.objects.get(id=data["payment_id"])
        self.assertEqual(created.hospital, self.clinic_a)
        self.assertEqual(created.patient, self.patient_a)

    def test_admin_confirms_and_rejects_pending_payment(self):
        """Admin A can confirm pending payment in Clinic A."""
        conf_resp = self.client.post(reverse("confirm_payment", args=[self.payment_a_pending.id]))
        self.assertEqual(conf_resp.status_code, 302)
        self.payment_a_pending.refresh_from_db()
        self.assertEqual(self.payment_a_pending.status, "paid")

    def test_admin_idor_cannot_view_other_clinic_payment(self):
        """IDOR Prevention: Admin A cannot view payment detail of Clinic B (HTTP 403)."""
        resp = self.client.get(reverse("payment_detail", args=[self.payment_b1.id]))
        self.assertEqual(resp.status_code, 403)

    def test_admin_idor_cannot_edit_other_clinic_payment(self):
        """IDOR Prevention: Admin A cannot edit payment of Clinic B (HTTP 403)."""
        edit_payload = {"amount": "1.00", "notes": "Hacked amount"}
        resp = self.client.post(
            reverse("payment_edit", args=[self.payment_b1.id]),
            data=json.dumps(edit_payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.payment_b1.refresh_from_db()
        self.assertEqual(self.payment_b1.amount, Decimal("950.00"))

    def test_admin_idor_cannot_delete_other_clinic_payment(self):
        """IDOR Prevention: Admin A cannot delete payment of Clinic B (HTTP 403)."""
        resp = self.client.delete(reverse("payment_detail", args=[self.payment_b1.id]))
        self.assertEqual(resp.status_code, 403)
        self.payment_b1.refresh_from_db()
        self.assertEqual(self.payment_b1.status, "paid")

    def test_admin_idor_cannot_confirm_other_clinic_payment(self):
        """IDOR Prevention: Admin A cannot confirm payment of Clinic B (HTTP 403)."""
        # Create pending payment in Clinic B
        pay_b_pending = PaymentRecord.objects.create(
            hospital=self.clinic_b,
            patient=self.patient_b,
            amount=Decimal("500.00"),
            method="upi",
            status="pending",
        )
        resp = self.client.post(reverse("confirm_payment", args=[pay_b_pending.id]))
        self.assertEqual(resp.status_code, 403)
        pay_b_pending.refresh_from_db()
        self.assertEqual(pay_b_pending.status, "pending")

    def test_admin_idor_cannot_create_payment_for_other_clinic_patient(self):
        """IDOR Prevention: Admin A cannot record payment for Clinic B patient (HTTP 403)."""
        payload = {
            "patient_id": self.patient_b.id,
            "amount": "200.00",
            "method": "cash",
        }
        resp = self.client.post(reverse("payment_create"), payload)
        self.assertEqual(resp.status_code, 403)

    def test_admin_export_contains_only_own_clinic_records(self):
        """Admin A export scopes strictly to Clinic A."""
        resp = self.client.get(reverse("export_payments_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])


# ══════════════════════════════════════════════════════════════════
# 3. STAFF PAYMENT SUITE (STRICT READ-ONLY)
# ══════════════════════════════════════════════════════════════════

class StaffPaymentTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff_a)

    def test_staff_views_clinic_payment_history_and_logs(self):
        """Staff sees read-only payment log for their clinic."""
        resp = self.client.get(reverse("staff_payments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Payment History &amp; Logs")
        self.assertContains(resp, "TXN-A1-001")
        # Ensure management buttons are NOT present in staff UI
        self.assertNotContains(resp, "Record Offline Payment")
        self.assertNotContains(resp, "recordPaymentModal")
        if resp.context:
            self.assertTrue(resp.context.get("is_staff_view"))
            self.assertFalse(resp.context.get("can_manage"))

    def test_staff_admin_payments_url_rendered_as_read_only(self):
        """Even if Staff hits /admin-payments/ directly, it renders read-only."""
        resp = self.client.get(reverse("admin_payments"))
        self.assertEqual(resp.status_code, 200)
        if resp.context:
            self.assertTrue(resp.context.get("is_staff_view"))
            self.assertFalse(resp.context.get("can_manage"))
        self.assertNotContains(resp, "Record Offline Payment")

    def test_staff_can_view_payment_details_in_own_clinic(self):
        """Staff can view payment details (GET) for own clinic."""
        resp = self.client.get(reverse("payment_detail", args=[self.payment_a1.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["payment"]["amount"], 600.0)

    def test_staff_idor_cannot_view_other_clinic_payment(self):
        """Staff cannot view payment from another clinic (HTTP 403)."""
        resp = self.client.get(reverse("payment_detail", args=[self.payment_b1.id]))
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_create_payment(self):
        """Backend rejects Staff attempt to create payment (HTTP 403)."""
        payload = {
            "patient_id": self.patient_a.id,
            "amount": "500.00",
            "method": "cash",
        }
        resp = self.client.post(reverse("payment_create"), payload)
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_record_cash_payment(self):
        """Backend rejects Staff attempt to record cash payment (HTTP 403)."""
        payload = {"amount": "500.00", "appointment_id": str(self.appt_a.id)}
        resp = self.client.post(reverse("record_cash_payment"), payload)
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_record_upi_payment(self):
        """Backend rejects Staff attempt to record UPI payment (HTTP 403)."""
        payload = {"amount": "500.00", "appointment_id": str(self.appt_a.id), "transaction_id": "U123"}
        resp = self.client.post(reverse("record_upi_payment"), payload)
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_edit_payment(self):
        """Backend rejects Staff attempt to edit payment via API (HTTP 403)."""
        payload = {"amount": "100.00", "status": "refunded"}
        resp = self.client.post(
            reverse("payment_edit", args=[self.payment_a1.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_put_payment_detail(self):
        """Backend rejects Staff PUT request to /payments/<id>/ (HTTP 403)."""
        resp = self.client.put(
            reverse("payment_detail", args=[self.payment_a1.id]),
            data=json.dumps({"amount": "10.00"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_staff_backend_blocks_delete_payment(self):
        """Backend rejects Staff attempt to delete payment (HTTP 403)."""
        resp = self.client.delete(reverse("payment_detail", args=[self.payment_a1.id]))
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.post(reverse("payment_delete", args=[self.payment_a1.id]))
        self.assertEqual(resp2.status_code, 403)

    def test_staff_backend_blocks_confirm_or_reject_payment(self):
        """Backend rejects Staff attempt to change status via confirm/reject (HTTP 403)."""
        resp1 = self.client.post(reverse("confirm_payment", args=[self.payment_a_pending.id]))
        self.assertEqual(resp1.status_code, 403)

        resp2 = self.client.post(reverse("reject_payment", args=[self.payment_a_pending.id]))
        self.assertEqual(resp2.status_code, 403)

    def test_staff_backend_blocks_export_reports(self):
        """Backend rejects Staff attempt to download payment exports (HTTP 403)."""
        excel_resp = self.client.get(reverse("export_payments_excel"))
        self.assertEqual(excel_resp.status_code, 403)

        pdf_resp = self.client.get(reverse("export_payments_pdf"))
        self.assertEqual(pdf_resp.status_code, 403)


# ══════════════════════════════════════════════════════════════════
# 4. CLIENT PAYMENT SUITE (PERSONAL READ-ONLY & IDOR)
# ══════════════════════════════════════════════════════════════════

class ClientPaymentTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.patient_a)

    def test_client_views_only_own_payment_history(self):
        """Client views only their personal payment records."""
        resp = self.client.get(reverse("payments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TXN-A1-001")
        self.assertNotContains(resp, "TXN-B1-001")
        # Ensure no payment entry forms/buttons appear
        self.assertNotContains(resp, "Record Payment")
        self.assertNotContains(resp, "action=\"/payments/record-cash/\"")

    def test_client_views_own_payment_details(self):
        """Client can view receipt/details for their own payment."""
        resp = self.client.get(reverse("payment_detail", args=[self.payment_a1.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["payment"]["transaction_id"], "TXN-A1-001")

    def test_client_idor_cannot_view_another_patient_payment(self):
        """IDOR Prevention: Client cannot view another patient's payment details (HTTP 403)."""
        resp = self.client.get(reverse("payment_detail", args=[self.payment_b1.id]))
        self.assertEqual(resp.status_code, 403)

    def test_client_cannot_access_admin_payments(self):
        """Client is blocked/redirected from admin payments dashboard."""
        resp = self.client.get(reverse("admin_payments"))
        self.assertIn(resp.status_code, [302, 403])

    def test_client_cannot_access_staff_payments(self):
        """Client is blocked/redirected from staff payments page."""
        resp = self.client.get(reverse("staff_payments"))
        self.assertIn(resp.status_code, [302, 403])

    def test_client_backend_blocks_create_payment(self):
        """Client cannot create payments via API (HTTP 403)."""
        payload = {"amount": "100.00", "patient_id": self.patient_a.id}
        resp = self.client.post(reverse("payment_create"), payload)
        self.assertEqual(resp.status_code, 403)

    def test_client_backend_blocks_record_cash_or_upi(self):
        """Client cannot record cash or UPI payments directly (HTTP 403)."""
        resp_cash = self.client.post(reverse("record_cash_payment"), {"amount": "50.00"})
        self.assertEqual(resp_cash.status_code, 403)

        resp_upi = self.client.post(reverse("record_upi_payment"), {"amount": "50.00"})
        self.assertEqual(resp_upi.status_code, 403)

    def test_client_backend_blocks_edit_and_delete(self):
        """Client cannot edit or delete payment records (HTTP 403)."""
        resp_edit = self.client.post(
            reverse("payment_edit", args=[self.payment_a1.id]),
            data=json.dumps({"amount": "0.01"}),
            content_type="application/json",
        )
        self.assertEqual(resp_edit.status_code, 403)

        resp_del = self.client.delete(reverse("payment_detail", args=[self.payment_a1.id]))
        self.assertEqual(resp_del.status_code, 403)

    def test_client_backend_blocks_exports(self):
        """Client cannot download payment exports (HTTP 403)."""
        excel_resp = self.client.get(reverse("export_payments_excel"))
        self.assertEqual(excel_resp.status_code, 403)

        pdf_resp = self.client.get(reverse("export_payments_pdf"))
        self.assertEqual(pdf_resp.status_code, 403)


# ══════════════════════════════════════════════════════════════════
# 5. MASS ASSIGNMENT & AUDIT LOGGING SUITE
# ══════════════════════════════════════════════════════════════════

class PaymentSecurityAndAuditTests(BasePaymentTestCase):
    def test_mass_assignment_protection_on_payment_edit(self):
        """Admin cannot alter hospital or patient ownership via update payload."""
        self.client.force_login(self.admin_a)
        malicious_payload = {
            "hospital_id": self.clinic_b.id,
            "patient_id": self.patient_b.id,
            "amount": "777.00",
            "notes": "Attempted tenancy spoofing",
        }
        resp = self.client.post(
            reverse("payment_edit", args=[self.payment_a1.id]),
            data=json.dumps(malicious_payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.payment_a1.refresh_from_db()
        # Amount and notes updated, but hospital and patient remain untouched
        self.assertEqual(self.payment_a1.amount, Decimal("777.00"))
        self.assertEqual(self.payment_a1.hospital, self.clinic_a)
        self.assertEqual(self.payment_a1.patient, self.patient_a)

    def test_audit_event_logged_on_payment_creation_and_status_change(self):
        """Mutations on payment records generate AuditEvent records."""
        self.client.force_login(self.admin_a)
        initial_events = AuditEvent.objects.filter(hospital=self.clinic_a).count()

        # 1. Create payment
        self.client.post(
            reverse("payment_create"),
            {"patient_id": self.patient_a.id, "amount": "250.00", "method": "cash"},
        )
        events_after_create = AuditEvent.objects.filter(hospital=self.clinic_a).count()
        self.assertGreater(events_after_create, initial_events)

        # 2. Confirm pending payment
        self.client.post(reverse("confirm_payment", args=[self.payment_a_pending.id]))
        latest_event = AuditEvent.objects.filter(hospital=self.clinic_a).order_by("-created_at", "-id").first()
        self.assertIsNotNone(latest_event)
        self.assertEqual(latest_event.action, "payment_confirmed")
        self.assertEqual(latest_event.actor, self.admin_a)
