from django import forms

from LeadManager.models import Service

from .models import Campaign, OutreachSettings, PitchTemplate, Prospect
from .profiler import domain_of, normalize_url


class Styled:
    def _style(self):
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                field.widget.attrs.setdefault("class", "form-control")


class ProspectForm(Styled, forms.ModelForm):
    class Meta:
        model = Prospect
        fields = ["company", "contact_name", "contact_title", "email", "phone", "website", "city", "country",
                  "industry", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()
        return normalize_url(value) if value else ""

    def clean(self):
        data = super().clean()
        email = (data.get("email") or "").lower()
        domain = domain_of(data.get("website") or "")
        qs = Prospect.objects.exclude(pk=self.instance.pk)
        if email and qs.filter(email__iexact=email).exists():
            self.add_error("email", "A prospect with this email already exists.")
        if domain and qs.filter(domain=domain).exists():
            self.add_error("website", "A prospect with this website already exists.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.email = (obj.email or "").lower()
        obj.domain = domain_of(obj.website)
        if commit:
            obj.save()
        return obj


class ImportForm(Styled, forms.Form):
    file = forms.FileField(label="Excel (.xlsx) or CSV file", widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.csv"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class CampaignForm(Styled, forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "service", "offer", "call_to_action", "framework", "followup_days_2", "followup_days_3"]
        labels = {
            "offer": "What you do for companies like this", "call_to_action": "Closing question",
            "followup_days_2": "Follow-up after (days)", "followup_days_3": "Last note after (days)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.all()
        self.fields["service"].required = False
        self._style()


class PitchTemplateForm(Styled, forms.ModelForm):
    class Meta:
        model = PitchTemplate
        fields = ["name", "business_type", "subject", "body", "is_active"]
        widgets = {"body": forms.Textarea(attrs={"rows": 9})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class SettingsForm(Styled, forms.ModelForm):
    class Meta:
        model = OutreachSettings
        fields = ["daily_cap", "sending_paused", "sender_name", "signature", "company_address"]
        widgets = {"signature": forms.Textarea(attrs={"rows": 3}), "company_address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_daily_cap(self):
        value = self.cleaned_data["daily_cap"]
        if value > 200:
            raise forms.ValidationError("For deliverability keep the daily cap at 200 or below.")
        return value
