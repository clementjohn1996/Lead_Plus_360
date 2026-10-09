from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField(max_length=160)
    company = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.company or self.name


class Invoice(models.Model):
    STATUSES = [("draft", "Draft"), ("sent", "Sent"), ("partial", "Partially paid"),
                ("paid", "Paid"), ("overdue", "Overdue"), ("cancelled", "Cancelled")]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField(max_length=40, unique=True, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUSES, default="draft", db_index=True)
    currency = models.CharField(max_length=3, default="INR")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [models.Index(fields=["status", "due_date"])]

    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = "INR"
        if not self.number:
            from Control.models import OrganizationSettings
            prefix = OrganizationSettings.get_solo().invoice_prefix or "INV"
            year = timezone.localdate().year
            last = Invoice.objects.filter(number__startswith=f"{prefix}-{year}-").order_by("-id").first()
            sequence = int(last.number.rsplit("-", 1)[-1]) + 1 if last else 1
            self.number = f"{prefix}-{year}-{sequence:04d}"
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum((line.total for line in self.lines.all()), Decimal("0"))

    @property
    def tax_amount(self):
        return max(self.subtotal - self.discount, Decimal("0")) * self.tax_rate / Decimal("100")

    @property
    def total(self):
        return max(self.subtotal - self.discount, Decimal("0")) + self.tax_amount

    @property
    def paid_amount(self):
        return sum((payment.amount for payment in self.payments.all()), Decimal("0"))

    @property
    def balance_due(self):
        return max(self.total - self.paid_amount, Decimal("0"))

    def refresh_status(self):
        if self.status == "cancelled":
            return
        paid = self.paid_amount
        if paid >= self.total and self.total > 0:
            self.status = "paid"
        elif paid > 0:
            self.status = "partial"
        elif self.due_date and self.due_date < timezone.localdate() and self.status in {"sent", "overdue"}:
            self.status = "overdue"
        self.save(update_fields=["status", "updated_at"])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    @property
    def total(self):
        return self.quantity * self.unit_price


class Payment(models.Model):
    METHODS = [("bank", "Bank transfer"), ("cash", "Cash"), ("card", "Card"),
               ("upi", "UPI"), ("other", "Other")]
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=15, choices=METHODS, default="bank")
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_status()


class Expense(models.Model):
    CATEGORIES = [("software", "Software"), ("people", "People"), ("office", "Office"),
                  ("marketing", "Marketing"), ("travel", "Travel"), ("other", "Other")]
    title = models.CharField(max_length=180)
    vendor = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="other")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    expense_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]
