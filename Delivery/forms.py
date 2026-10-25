from django import forms
from django.contrib.auth import get_user_model
from HR.models import Employee
from .models import WorkAssignment

User = get_user_model()

TEAM_ROLES = {"developer","digital_marketing","graphic_designer","videographer","video_editor"}

def users_for_role(role_names):
    return User.objects.filter(is_active=True, profile__role__name__in=role_names).select_related("profile").order_by("first_name","last_name","username")

class BDMForm(forms.Form):
    bdm = forms.ModelChoiceField(queryset=users_for_role({"bd_manager"}), label="Business Development Manager")

class PMForm(forms.Form):
    project_manager = forms.ModelChoiceField(queryset=users_for_role({"project_manager"}), label="Project Manager")

class TeamAssignmentForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=users_for_role(TEAM_ROLES),
        label="Team member"
    )
    class Meta:
        model = WorkAssignment
        fields = ["employee","role","title","instructions","due_date"]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows":4}),
            "due_date": forms.DateInput(attrs={"type":"date"}),
        }

class AssignmentUpdateForm(forms.ModelForm):
    class Meta:
        model = WorkAssignment
        fields = ["status","progress","reviewer_notes"]
        widgets = {"reviewer_notes": forms.Textarea(attrs={"rows":3})}
