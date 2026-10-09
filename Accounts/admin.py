from django.contrib import admin

from .models import Customer, Expense, Invoice, InvoiceLine, Payment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "email", "is_active"]
    search_fields = ["name", "company", "email"]


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "issue_date", "due_date", "status"]
    list_filter = ["status", "currency"]
    search_fields = ["number", "customer__name", "customer__company"]
    inlines = [InvoiceLineInline]


admin.site.register(Payment)
admin.site.register(Expense)
