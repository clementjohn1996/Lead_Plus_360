from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User

from django.utils.text import slugify

from Control.models import Role, UserProfile


class StyledFormMixin:
    def _style(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class UserProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["profile_picture", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class RoleForm(StyledFormMixin, forms.ModelForm):
    key = forms.SlugField(max_length=40, required=False, label="Key", help_text="Internal key. Set once; generated from the label if blank.")

    class Meta:
        model = Role
        fields = ["label", "description", "level", "is_active", "can_use_crm", "sees_all_leads",
                  "sees_team_leads", "can_manage_team", "can_manage_hr", "is_privileged", "is_super_admin"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.pop("class", None)
        if self.instance.pk:
            del self.fields["key"]
            if self.instance.is_system and self.instance.is_super_admin:
                for name in ("is_active", "is_privileged", "is_super_admin"):
                    self.fields[name].disabled = True
        self._style()

    def clean_key(self):
        key = self.cleaned_data.get("key") or slugify(self.cleaned_data.get("label", ""))[:40]
        key = key.replace("-", "_")
        if Role.objects.filter(name=key).exists():
            raise forms.ValidationError("A role with this key already exists.")
        return key

    def save(self, commit=True):
        role = super().save(commit=False)
        if not role.pk:
            role.name = self.cleaned_data["key"]
        if commit:
            role.save()
        return role
