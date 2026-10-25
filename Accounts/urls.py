from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="accounts_dashboard"),
    path("customers/", views.customers, name="account_customers"),
    path("customers/new/", views.customer_create, name="account_customer_create"),
    path("invoices/", views.invoices, name="account_invoices"),
    path("invoices/new/", views.invoice_create, name="account_invoice_create"),
    path("invoices/export/", views.export_invoices, name="account_invoice_export"),
    path("invoices/<int:pk>/", views.invoice_detail, name="account_invoice_detail"),
    path("invoices/<int:pk>/action/", views.invoice_action, name="account_invoice_action"),
    path("expenses/", views.expense_list, name="account_expenses"),
    path("expenses/new/", views.expense_create, name="account_expense_create"),
]
