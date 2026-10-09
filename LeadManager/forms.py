from django import forms
from django.utils import timezone
from .models import Lead, LeadSource, Service, Activity, Task, FollowUpSchedule


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "name",
            "company",
            "designation",
            "industry",
            "email",
            "phone",
            "alternate_phone",
            "website",
            "linkedin",
            "facebook",
            "instagram",
            "country",
            "state",
            "city",
            "source",
            "service",
            "services",
            "stage",
            "temperature",
            "priority",
            "owner",
            "manager",
            "assigned_at",
            "estimated_value",
            "budget_tier",
            "billing_type",
            "probability",
            "expected_close_date",
            "next_follow_up",
            "tags",
            "notes",
            "lost_reason",
            "consent_to_contact",
        ]
        widgets = {
            "next_follow_up": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "assigned_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "expected_close_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "tags": forms.TextInput(attrs={"placeholder": "ecommerce, SEO, Kerala"}),
            "estimated_value": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "probability": forms.NumberInput(attrs={"min": "0", "max": "100"}),
            "services": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = LeadSource.objects.filter(is_active=True)
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["services"].queryset = Service.objects.filter(is_active=True)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxSelectMultiple):
                f.widget.attrs.setdefault("class", "form-control")
        for name in ["stage", "temperature", "priority", "source", "service",
                      "services", "owner", "manager", "budget_tier", "billing_type"]:
            if name in self.fields and not isinstance(self.fields[name].widget, forms.CheckboxSelectMultiple):
                self.fields[name].widget.attrs["class"] = "form-select"


class QuickLeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["name", "company", "email", "phone", "source", "services",
                  "estimated_value", "next_follow_up"]
        widgets = {
            "next_follow_up": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "services": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = LeadSource.objects.filter(is_active=True)
        self.fields["services"].queryset = Service.objects.filter(is_active=True)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxSelectMultiple):
                f.widget.attrs.setdefault("class", "form-control")
        for name in ["source", "services"]:
            if name in self.fields and not isinstance(self.fields[name].widget, forms.CheckboxSelectMultiple):
                self.fields[name].widget.attrs["class"] = "form-select"


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["activity_type", "outcome", "subject", "body", "due_at", "completed"]
        widgets = {
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "body": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")
        self.fields["activity_type"].widget.attrs["class"] = "form-select"
        self.fields["outcome"].widget.attrs["class"] = "form-select"


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "due_at", "status", "assigned_to", "lead"]
        widgets = {
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")
        for name in ["status", "assigned_to", "lead"]:
            if name in self.fields:
                self.fields[name].widget.attrs["class"] = "form-select"


class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUpSchedule
        fields = ["lead", "title", "description", "due_at", "status",
                  "snooze_until", "notification_sent", "assigned_to"]
        widgets = {
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "snooze_until": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")
        for name in ["status", "assigned_to", "lead"]:
            if name in self.fields:
                self.fields[name].widget.attrs["class"] = "form-select"
