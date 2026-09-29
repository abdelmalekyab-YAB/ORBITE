from django import forms

from .models import Milestone


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ["name", "kind", "status", "start_date", "due_date", "is_client_visible", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
