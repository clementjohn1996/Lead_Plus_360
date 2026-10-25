from django import forms
from django.contrib.auth import get_user_model
from .calendar_models import DeliveryPackage, DeliveryPlan, DeliveryCalendarTask

User = get_user_model()

class DeliveryPlanForm(forms.ModelForm):
    class Meta:
        model = DeliveryPlan
        fields = ["package", "package_name", "start_date", "target_completion_date", "bdm_notes"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "target_completion_date": forms.DateInput(attrs={"type": "date"}),
            "bdm_notes": forms.Textarea(attrs={"rows": 3}),
        }

class PackageForm(forms.ModelForm):
    class Meta:
        model = DeliveryPackage
        fields = ["name", "description", "is_preset", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

class PackageTaskTemplateForm(forms.ModelForm):
    class Meta:
        model = __import__("Delivery.calendar_models", fromlist=["PackageTaskTemplate"]).PackageTaskTemplate
        fields = ["task_type", "title", "icon", "gif_url", "default_duration_days", "sequence", "active"]

class CalendarTaskForm(forms.ModelForm):
    class Meta:
        model = DeliveryCalendarTask
        fields = ["task_type", "title", "description", "icon", "gif_url", "assignment_role", "assigned_to", "start_date", "shoot_date", "draft_date", "launch_date", "final_date", "due_date", "status", "progress", "notes", "reminder_enabled", "reminder_days_before"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            **{f: forms.DateInput(attrs={"type": "date"}) for f in ["start_date", "shoot_date", "draft_date", "launch_date", "final_date", "due_date"]},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reminder_days_before"].help_text = "Minimum 1 day. Notification fires at least 1 day before start."
        self.fields["reminder_days_before"].min = 1

class QuickTaskForm(CalendarTaskForm):
    plan = forms.ModelChoiceField(queryset=DeliveryPlan.objects.none(), required=True, label="Delivery plan")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["plan"].queryset = visible_plans(user)

class BDMReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approved", "Approve plan"), ("changes_requested", "Request changes")])
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Approval notes or required changes..."}))
