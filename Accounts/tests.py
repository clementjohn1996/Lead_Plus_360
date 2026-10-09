from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from Control.models import Role, UserProfile

from .models import Customer, Expense, Invoice, InvoiceLine, Payment


class AccountsWorkflowTests(TestCase):
    def setUp(self):
        role = Role.objects.create(name="accounts_admin", label="Accounts Admin", can_manage_accounts=True)
        self.user = User.objects.create_user("accounts", password="test-password-123")
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        self.user.profile.role = role
        self.user.profile.save(update_fields=["role"])
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(name="Test Client", company="Test Co")

    def test_accounts_dashboard_requires_accounts_access(self):
        self.assertEqual(self.client.get(reverse("accounts_dashboard")).status_code, 200)

    def test_invoice_balance_and_payment_status(self):
        invoice = Invoice.objects.create(customer=self.customer, status="sent")
        InvoiceLine.objects.create(invoice=invoice, description="Monthly retainer", quantity=1, unit_price=Decimal("1000"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("1000"))
        Payment.objects.create(invoice=invoice, amount=Decimal("1000"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.balance_due, Decimal("0"))

    def test_payment_cannot_exceed_balance(self):
        invoice = Invoice.objects.create(customer=self.customer, status="sent")
        InvoiceLine.objects.create(invoice=invoice, description="Setup", quantity=1, unit_price=Decimal("100"))
        response = self.client.post(reverse("account_invoice_detail", args=[invoice.pk]), {"amount": "101", "payment_date": "2026-10-09", "method": "cash"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.payments.count(), 0)

    def test_expense_can_be_recorded(self):
        response = self.client.post(reverse("account_expense_create"), {"title": "Hosting", "vendor": "Cloud", "category": "software", "amount": "50", "expense_date": "2026-10-09"})
        self.assertRedirects(response, reverse("account_expenses"))
        self.assertTrue(Expense.objects.filter(title="Hosting").exists())
