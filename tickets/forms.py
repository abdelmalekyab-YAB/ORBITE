from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from core.models import Company, Milestone, Project

from .models import Comment, Ticket


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = [super(MultipleFileField, self).clean(f, initial) for f in files]
        for f in cleaned:
            if f.size > settings.ORBIT_MAX_ATTACHMENT_SIZE:
                raise forms.ValidationError(
                    _("%(name)s is too large (max %(max)s).")
                    % {"name": f.name, "max": filesizeformat(settings.ORBIT_MAX_ATTACHMENT_SIZE)}
                )
        return cleaned


def staff_users():
    return get_user_model().objects.filter(Q(role="staff") | Q(is_superuser=True), is_active=True)


class ClientTicketForm(forms.ModelForm):
    """Simple request form used by clients."""

    files = MultipleFileField(label=_("Files or screenshots"), required=False)

    class Meta:
        model = Ticket
        fields = ["type", "title", "description", "priority"]
        widgets = {"description": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = [c for c in Ticket.Type.choices if c[0] in Ticket.CLIENT_TYPES]
        self.fields["description"].required = True


class StaffTicketForm(forms.ModelForm):
    files = MultipleFileField(label=_("Files or screenshots"), required=False)

    class Meta:
        model = Ticket
        fields = [
            "type", "title", "description", "status", "priority", "visibility",
            "assignee", "milestone", "parent", "due_date",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields["assignee"].queryset = staff_users()
        self.fields["milestone"].queryset = project.milestones.all()
        parents = project.tickets.filter(parent__isnull=True)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
            if self.instance.subtasks.exists():
                parents = parents.none()
        self.fields["parent"].queryset = parents
        self.fields["parent"].label_from_instance = lambda t: f"{t.reference} {t.title}"
        if self.instance.pk and self.instance.origin == Ticket.Origin.CLIENT:
            self.fields["visibility"].disabled = True
            self.fields["visibility"].help_text = _("Client requests always stay visible to the client.")


class CommentForm(forms.ModelForm):
    files = MultipleFileField(label=_("Files or screenshots"), required=False)

    class Meta:
        model = Comment
        fields = ["body", "is_internal"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": _("Write a reply…")})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False
        if not user.is_digitalia:
            del self.fields["is_internal"]

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("body") and not cleaned.get("files"):
            raise forms.ValidationError(_("Write a comment or add a file."))
        return cleaned


class TicketFilterForm(forms.Form):
    q = forms.CharField(label=_("Search"), required=False)
    company = forms.ModelChoiceField(label=_("Client"), queryset=Company.objects.filter(is_internal=False), required=False)
    project = forms.ModelChoiceField(label=_("Project"), queryset=Project.objects.all(), required=False)
    type = forms.ChoiceField(label=_("Type"), required=False)
    status = forms.ChoiceField(label=_("Status"), required=False)
    priority = forms.ChoiceField(label=_("Priority"), required=False)
    origin = forms.ChoiceField(label=_("Origin"), required=False)
    visibility = forms.ChoiceField(label=_("Visibility"), required=False)
    assignee = forms.ModelChoiceField(label=_("Assignee"), queryset=staff_users(), required=False)
    milestone = forms.ModelChoiceField(label=_("Roadmap step"), queryset=Milestone.objects.none(), required=False)
    date_from = forms.DateField(label=_("Created from"), required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label=_("Created until"), required=False, widget=forms.DateInput(attrs={"type": "date"}))
    late = forms.BooleanField(label=_("Late only"), required=False)
    show_closed = forms.BooleanField(label=_("Include closed"), required=False)

    OPEN = "open"
    # Grouped choices, used by the clickable counters of the dashboards.
    CHANGES = "changes"
    WORKING = "working"

    def __init__(self, *args, user, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        blank = [("", "—")]
        self.fields["type"].choices = blank + [(self.CHANGES, _("Changes & features"))] + list(Ticket.Type.choices)
        self.fields["status"].choices = blank + [(self.WORKING, _("In progress or in test"))] + list(Ticket.Status.choices)
        self.fields["priority"].choices = blank + list(Ticket.Priority.choices)
        self.fields["origin"].choices = blank + list(Ticket.Origin.choices)
        self.fields["visibility"].choices = blank + list(Ticket.Visibility.choices)
        self.fields["assignee"].queryset = staff_users()
        if project is not None:
            del self.fields["company"], self.fields["project"]
            self.fields["milestone"].queryset = project.milestones.all()
            if not user.is_digitalia:
                self.fields["milestone"].queryset = project.milestones.filter(is_client_visible=True)
        else:
            del self.fields["milestone"]
        if not user.is_digitalia:
            for name in ("origin", "visibility", "assignee"):
                del self.fields[name]
            self.fields["type"].choices = blank + [(self.CHANGES, _("Changes & features"))] + [
                c for c in Ticket.Type.choices if c[0] in Ticket.CLIENT_TYPES
            ]

    def apply(self, qs):
        if not self.is_valid():
            return qs.open()
        data = self.cleaned_data
        if data.get("q"):
            term = data["q"].strip()
            cond = Q(title__icontains=term) | Q(description__icontains=term)
            if "-" in term:
                key, _sep, num = term.rpartition("-")
                if num.isdigit():
                    cond |= Q(project__key__iexact=key, number=int(num))
            qs = qs.filter(cond)
        if data.get("type") == self.CHANGES:
            qs = qs.filter(type__in=[Ticket.Type.EVOLUTION, Ticket.Type.FEATURE])
            data = {**data, "type": ""}
        if data.get("status") == self.WORKING:
            qs = qs.filter(status__in=[Ticket.Status.IN_PROGRESS, Ticket.Status.IN_TEST])
            data = {**data, "status": ""}
        for name in ("type", "status", "priority", "origin", "visibility"):
            if data.get(name):
                qs = qs.filter(**{name: data[name]})
        for name in ("assignee", "milestone", "project"):
            if data.get(name):
                qs = qs.filter(**{name: data[name]})
        if data.get("company"):
            qs = qs.filter(project__company=data["company"])
        if data.get("date_from"):
            qs = qs.filter(created_at__date__gte=data["date_from"])
        if data.get("date_to"):
            qs = qs.filter(created_at__date__lte=data["date_to"])
        if data.get("late"):
            qs = qs.late()
        if not data.get("show_closed") and not data.get("status"):
            qs = qs.open()
        return qs
