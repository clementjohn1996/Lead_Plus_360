import csv
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CustomerForm, ExpenseForm, InvoiceForm, InvoiceLineFormSet, PaymentForm
from .models import Customer, Expense, Invoice, Payment
from .permissions import accounts_required


@accounts_required
def dashboard(request):
    today = timezone.localdate()
    invoices = Invoice.objects.prefetch_related("payments", "lines")
    for invoice in invoices.filter(status__in=["sent", "partial"]):
        if invoice.due_date and invoice.due_date < today:
            invoice.refresh_status()
    month_start = today.replace(day=1)
    month_invoiced = sum((invoice.total for invoice in invoices.filter(issue_date__gte=month_start)), Decimal("0"))
    month_paid = Payment.objects.filter(payment_date__gte=month_start).aggregate(value=Sum("amount"))["value"] or Decimal("0")
    month_expenses = Expense.objects.filter(expense_date__gte=month_start).aggregate(value=Sum("amount"))["value"] or Decimal("0")
    outstanding = sum((invoice.balance_due for invoice in invoices.filter(status__in=["sent", "partial", "overdue"])), Decimal("0"))
    return render(request, "Accounts/dashboard.html", {
        "invoice_count": Invoice.objects.exclude(status="cancelled").count(),
        "customer_count": Customer.objects.filter(is_active=True).count(),
        "month_invoiced": month_invoiced, "month_paid": month_paid,
        "month_expenses": month_expenses, "outstanding": outstanding,
        "recent_invoices": invoices[:8], "recent_expenses": Expense.objects.all()[:6],
    })


@accounts_required
def customers(request):
    query = request.GET.get("q", "").strip()
    rows = Customer.objects.all()
    if query:
        rows = rows.filter(name__icontains=query) | rows.filter(company__icontains=query) | rows.filter(email__icontains=query)
    return render(request, "Accounts/customers.html", {"customers": rows, "query": query})


@accounts_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "Customer added."); return redirect("account_customers")
    return render(request, "Accounts/form.html", {"form": form, "heading": "Add customer", "back": "account_customers"})


@accounts_required
def invoices(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    rows = Invoice.objects.select_related("customer").prefetch_related("lines", "payments")
    if query:
        rows = rows.filter(number__icontains=query) | rows.filter(customer__name__icontains=query) | rows.filter(customer__company__icontains=query)
    if status:
        rows = rows.filter(status=status)
    return render(request, "Accounts/invoices.html", {"invoices": rows, "query": query, "status": status, "statuses": Invoice.STATUSES})


@accounts_required
@transaction.atomic
def invoice_create(request):
    form = InvoiceForm(request.POST or None)
    formset = InvoiceLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        invoice = form.save(commit=False); invoice.created_by = request.user; invoice.save()
        formset.instance = invoice; formset.save()
        messages.success(request, f"Invoice {invoice.number} created."); return redirect("account_invoice_detail", pk=invoice.pk)
    return render(request, "Accounts/invoice_form.html", {"form": form, "formset": formset})


@accounts_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer").prefetch_related("lines", "payments"), pk=pk)
    payment_form = PaymentForm(request.POST or None)
    if request.method == "POST" and payment_form.is_valid():
        amount = payment_form.cleaned_data["amount"]
        if amount <= 0 or amount > invoice.balance_due:
            payment_form.add_error("amount", "Payment must be greater than zero and no more than the balance due.")
        else:
            payment = payment_form.save(commit=False); payment.invoice = invoice; payment.received_by = request.user; payment.save()
            messages.success(request, "Payment recorded."); return redirect("account_invoice_detail", pk=pk)
    return render(request, "Accounts/invoice_detail.html", {"invoice": invoice, "payment_form": payment_form})


@accounts_required
@require_POST
def invoice_action(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    action = request.POST.get("action")
    if action == "send" and invoice.status == "draft": invoice.status = "sent"
    elif action == "cancel" and invoice.status not in {"paid", "cancelled"}: invoice.status = "cancelled"
    invoice.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Invoice {invoice.number} marked {invoice.get_status_display().lower()}.")
    return redirect("account_invoice_detail", pk=pk)


@accounts_required
def expense_list(request):
    return render(request, "Accounts/expenses.html", {"expenses": Expense.objects.all()})


@accounts_required
def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False); expense.created_by = request.user; expense.save()
        messages.success(request, "Expense recorded."); return redirect("account_expenses")
    return render(request, "Accounts/form.html", {"form": form, "heading": "Record expense", "back": "account_expenses"})


@accounts_required
def export_invoices(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="invoices.csv"'
    writer = csv.writer(response); writer.writerow(["Invoice", "Customer", "Issue date", "Due date", "Status", "Total", "Paid", "Balance"])
    for invoice in Invoice.objects.select_related("customer").prefetch_related("lines", "payments"):
        writer.writerow([invoice.number, invoice.customer, invoice.issue_date, invoice.due_date, invoice.get_status_display(), invoice.total, invoice.paid_amount, invoice.balance_due])
    return response
