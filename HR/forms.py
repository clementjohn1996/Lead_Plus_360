from django import forms
from django.contrib.auth.models import User

from Control.models import Role, UserProfile
from Control.org_defaults import ensure_standard_roles
from Control.permissions import assignable_roles, is_admin

from .models import Employee, EmployeeDocument, OnboardingTask, OnboardingTemplate, OnboardingTemplateTask


class Styled:
    def _style(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            widget.attrs.setdefault("class", "form-control")


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        super().__init__(format="%H:%M", **kwargs)


def _designation_choices(roles, current=""):
    choices = [(role.label, role.label) for role in roles]
    values = {value for value, _ in choices}
    if current and current not in values:
        choices.insert(0, (current, current))
    return [("", "---------"), *choices]


class NewEmployeeForm(Styled, forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(label="Work email")
    username = forms.CharField(max_length=150, help_text="Login name")
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=True)
    designation = forms.ChoiceField(required=False, label="Designation")
    photo = forms.ImageField(
        required=False, label="Photo", help_text="Shown as the employee icon in lists, the profile and the onboarding board.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = Employee
        fields = [
            "department", "designation", "manager", "employment_type", "work_mode",
            "date_of_joining", "is_fresher", "personal_email", "emergency_contact",
            "shift_start", "shift_end", "grace_minutes", "show_on_tv",
        ]
        widgets = {"date_of_joining": DateInput(), "shift_start": TimeInput(), "shift_end": TimeInput()}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not Role.objects.filter(is_active=True).exists():
            ensure_standard_roles()
        roles = assignable_roles(actor)
        self.fields["role"].queryset = roles
        self.fields["designation"].choices = _designation_choices(roles)
        self._style()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username


class EmployeeForm(Styled, forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(label="Work email")
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=True)
    designation = forms.ChoiceField(required=False, label="Designation")
    photo = forms.ImageField(
        required=False, label="Photo", help_text="Shown as the employee icon in lists, the profile and the onboarding board.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = Employee
        fields = [
            "department", "designation", "manager", "employment_type", "work_mode", "status",
            "date_of_joining", "is_fresher", "date_of_birth", "date_of_exit", "personal_email", "emergency_contact",
            "shift_start", "shift_end", "grace_minutes", "show_on_tv",
        ]
        widgets = {
            "date_of_joining": DateInput(), "date_of_birth": DateInput(), "date_of_exit": DateInput(),
            "shift_start": TimeInput(), "shift_end": TimeInput(),
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        roles = assignable_roles(actor)
        self.fields["role"].queryset = roles
        current = profile.role
        if current and (current.is_privileged or current.is_super_admin) and not is_admin(actor):
            roles = Role.objects.filter(pk=current.pk)
            self.fields["role"].queryset = roles
            self.fields["role"].disabled = True
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email
        self.fields["role"].initial = profile.role
        self.fields["designation"].choices = _designation_choices(roles, self.instance.designation)
        self.fields["manager"].queryset = Employee.objects.exclude(pk=self.instance.pk).exclude(status="exited")
        self._style()

    def save(self, commit=True):
        employee = super().save(commit)
        user = employee.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = self.cleaned_data["role"]
        profile.save(update_fields=["role"])
        user.is_active = employee.status != "exited"
        user.save(update_fields=["is_active"])
        from . import services

        services.save_photo(user, self.cleaned_data.get("photo"))
        services.apply_fresher_flag(employee)
        return employee


class DocumentForm(Styled, forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ["doc_type", "title", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class TaskUploadForm(Styled, forms.ModelForm):
    class Meta:
        model = OnboardingTask
        fields = ["attachment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class CustomTaskForm(Styled, forms.ModelForm):
    class Meta:
        model = OnboardingTask
        fields = ["title", "description", "category", "responsible", "due_date", "required"]
        widgets = {"due_date": DateInput(), "description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class WorkflowForm(Styled, forms.ModelForm):
    class Meta:
        model = OnboardingTemplate
        fields = ["name", "role", "department", "is_default", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        data = super().clean()
        if data.get("is_default") and (data.get("role") or data.get("department")):
            raise forms.ValidationError("The company default cannot be limited to a role or department.")
        return data

    def save(self, commit=True):
        template = super().save(commit)
        if commit and template.is_default:
            OnboardingTemplate.objects.exclude(pk=template.pk).update(is_default=False)
        return template


class WorkflowTaskForm(Styled, forms.ModelForm):
    class Meta:
        model = OnboardingTemplateTask
        fields = ["title", "category", "responsible", "due_after_days", "required", "requires_upload",
                  "verifier", "requires_approval", "approver", "skippable", "skip_label", "skip_if_fresher",
                  "auto_key", "description", "order"]
        widgets = {"description": forms.TextInput(attrs={"placeholder": "Instructions (optional)"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


WorkflowTaskFormSet = forms.inlineformset_factory(
    OnboardingTemplate, OnboardingTemplateTask, form=WorkflowTaskForm, extra=3, can_delete=True,
)


class DepartmentForm(Styled, forms.ModelForm):
    """Create / edit a department. Lives on Administration -> Departments."""

    class Meta:
        from LeadManager.models import Department as _Department

        model = _Department
        fields = ["name", "description", "head"]
        labels = {
            "name": "Department name",
            "description": "What does this department handle?",
            "head": "Department head",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head"].queryset = User.objects.filter(is_active=True).order_by("first_name", "username")
        self.fields["head"].required = False
        self.fields["head"].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields["name"].widget.attrs["placeholder"] = "e.g. Customer Success"
        self._style()


class PhotoForm(forms.Form):
    photo = forms.ImageField()
