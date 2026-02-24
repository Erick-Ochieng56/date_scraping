"""Dashboard forms for Target edit, Lead add, Prospect add."""

from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError

from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeTarget, ScrapeTargetType


class TargetEditForm(forms.ModelForm):
    """Edit scrape target (name, URL, type, interval, enabled, config as JSON)."""

    config_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 12, "class": "form-control font-monospace"}),
        label="Configuration (JSON)",
        help_text="Scraper configuration as JSON. Edit with care.",
    )

    class Meta:
        model = ScrapeTarget
        fields = ("name", "start_url", "target_type", "enabled", "run_every_minutes")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_url": forms.URLInput(attrs={"class": "form-control"}),
            "target_type": forms.Select(attrs={"class": "form-select"}, choices=ScrapeTargetType.choices),
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "run_every_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["config_json"].initial = json.dumps(self.instance.config, indent=2)
        else:
            self.fields["config_json"].initial = "{}"

    def clean_config_json(self):
        data = self.cleaned_data.get("config_json") or "{}"
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}") from e

    def save(self, commit=True):
        target = super().save(commit=False)
        target.config = self.cleaned_data["config_json"]
        if commit:
            target.save()
        return target


class ProspectCreateForm(forms.ModelForm):
    """Create a new prospect from the dashboard."""

    class Meta:
        model = Prospect
        fields = (
            "event_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "notes",
            "status",
        )
        widgets = {
            "event_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Event or meeting name"}),
            "company": forms.TextInput(attrs={"class": "form-control", "placeholder": "Company / organisation"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "email@example.com"}),
            "phone_raw": forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional notes"}),
            "status": forms.Select(attrs={"class": "form-select"}, choices=ProspectStatus.choices),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["website"].required = False
        self.fields["status"].initial = ProspectStatus.NEW


class LeadCreateForm(forms.ModelForm):
    """Create a new lead from the dashboard."""

    class Meta:
        model = Lead
        fields = (
            "full_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "position",
            "event_name",
            "address",
            "city",
            "state",
            "country_code",
            "notes",
            "status",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name"}),
            "company": forms.TextInput(attrs={"class": "form-control", "placeholder": "Company"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "email@example.com"}),
            "phone_raw": forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "position": forms.TextInput(attrs={"class": "form-control", "placeholder": "Job title"}),
            "event_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Event name"}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Street address"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "City"}),
            "state": forms.TextInput(attrs={"class": "form-control", "placeholder": "State / region"}),
            "country_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. US", "maxlength": 2}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional notes"}),
            "status": forms.Select(attrs={"class": "form-select"}, choices=LeadStatus.choices),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("email", "website", "position", "event_name", "address", "city", "state", "country_code", "notes"):
            self.fields[f].required = False
        self.fields["status"].initial = LeadStatus.CONTACTED
