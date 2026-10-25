from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Expense, Invoice, InvoiceLine, Payment


class Styled(forms.ModelForm):
    def _style(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class CustomerForm(Styled):
    class Meta:
        model = Customer
        fields = ["name", "company", "email", "phone", "tax_id", "address", "notes", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self._style()


class InvoiceForm(Styled):
    class Meta:
        model = Invoice
        fields = ["customer", "issue_date", "due_date", "currency", "tax_rate", "discount", "notes", "terms"]
        widgets = {"issue_date": forms.DateInput(attrs={"type": "date"}), "due_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2}), "terms": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self._style()


class PaymentForm(Styled):
    class Meta:
        model = Payment
        fields = ["amount", "payment_date", "method", "reference", "notes"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self._style()


class ExpenseForm(Styled):
    class Meta:
        model = Expense
        fields = ["title", "vendor", "category", "amount", "expense_date", "is_recurring", "notes"]
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self._style()


InvoiceLineFormSet = inlineformset_factory(Invoice, InvoiceLine, fields=["description", "quantity", "unit_price"], extra=3, can_delete=True)
