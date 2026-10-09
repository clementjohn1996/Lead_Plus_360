from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length"), ("Control", "0005_role_capabilities")]
    operations = [
        migrations.CreateModel(name="Customer", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=160)), ("company", models.CharField(blank=True, max_length=180)),
            ("email", models.EmailField(blank=True, max_length=254)), ("phone", models.CharField(blank=True, max_length=40)),
            ("tax_id", models.CharField(blank=True, max_length=80)), ("address", models.TextField(blank=True)),
            ("notes", models.TextField(blank=True)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="Invoice", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("number", models.CharField(blank=True, max_length=40, unique=True)), ("issue_date", models.DateField(default=django.utils.timezone.localdate)),
            ("due_date", models.DateField(blank=True, null=True)), ("status", models.CharField(choices=[("draft", "Draft"), ("sent", "Sent"), ("partial", "Partially paid"), ("paid", "Paid"), ("overdue", "Overdue"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=15)),
            ("currency", models.CharField(default="INR", max_length=3)), ("tax_rate", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
            ("discount", models.DecimalField(decimal_places=2, default=0, max_digits=12)), ("notes", models.TextField(blank=True)), ("terms", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="Accounts.customer")),
        ], options={"ordering": ["-issue_date", "-id"]}),
        migrations.CreateModel(name="InvoiceLine", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("description", models.CharField(max_length=240)),
            ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=10)), ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
            ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="Accounts.invoice")),
        ]),
        migrations.CreateModel(name="Payment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
            ("payment_date", models.DateField(default=django.utils.timezone.localdate)), ("method", models.CharField(choices=[("bank", "Bank transfer"), ("cash", "Cash"), ("card", "Card"), ("upi", "UPI"), ("other", "Other")], default="bank", max_length=15)),
            ("reference", models.CharField(blank=True, max_length=120)), ("notes", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="Accounts.invoice")),
            ("received_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="Expense", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("title", models.CharField(max_length=180)),
            ("vendor", models.CharField(blank=True, max_length=160)), ("category", models.CharField(choices=[("software", "Software"), ("people", "People"), ("office", "Office"), ("marketing", "Marketing"), ("travel", "Travel"), ("other", "Other")], default="other", max_length=20)),
            ("amount", models.DecimalField(decimal_places=2, max_digits=14)), ("expense_date", models.DateField(default=django.utils.timezone.localdate)), ("notes", models.TextField(blank=True)), ("is_recurring", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-expense_date", "-id"]}),
        migrations.AddIndex(model_name="invoice", index=models.Index(fields=["status", "due_date"], name="Accounts_in_status_7499c2_idx")),
    ]
