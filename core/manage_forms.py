from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Company, Project

User = get_user_model()


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name"]


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["company", "name", "key", "description", "lead", "members", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "members": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.filter(is_internal=False)
        self.fields["lead"].queryset = User.objects.filter(Q(role="staff") | Q(is_superuser=True), is_active=True)
        clients = User.objects.filter(role=User.Role.CLIENT, is_active=True).select_related("company")
        company = self.initial.get("company") or getattr(self.instance, "company_id", None)
        if self.data.get("company"):
            company = self.data.get("company")
        if company:
            clients = clients.filter(company=company)
        self.fields["members"].queryset = clients.order_by("last_name", "first_name")
        self.fields["members"].label_from_instance = lambda u: f"{u.get_full_name() or u.username} · {u.email}"
        self.fields["members"].help_text = _("Client accounts of this company that can see the project.")

    def clean_key(self):
        key = self.cleaned_data["key"].upper()
        if Project.objects.filter(key__iexact=key).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This key is already used by another project."))
        return key


class UserForm(forms.ModelForm):
    projects = forms.ModelMultipleChoiceField(
        label=_("Projects"), queryset=Project.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text=_("For a client: the projects they will see when they log in."),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "company", "is_staff", "is_active"]
        labels = {"is_staff": _("Orbit administrator"), "is_active": _("Active account")}
        help_texts = {
            "is_staff": _("Digitalia only: can manage clients, projects and accounts."),
            "is_active": _("A deactivated account can no longer log in."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        self.fields["projects"].queryset = Project.objects.filter(is_active=True).select_related("company")
        self.fields["projects"].label_from_instance = lambda p: f"{p.name} · {p.company}"
        if self.instance.pk:
            self.fields["projects"].initial = self.instance.projects.all()
        else:
            del self.fields["is_active"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("An account already uses this e-mail address."))
        return email

    def clean(self):
        cleaned = super().clean()
        role, company = cleaned.get("role"), cleaned.get("company")
        if role == User.Role.CLIENT:
            if not company or company.is_internal:
                self.add_error("company", _("Choose the client company of this account."))
            cleaned["is_staff"] = False
            projects = cleaned.get("projects") or []
            wrong = [p.name for p in projects if company and p.company_id != company.pk]
            if wrong:
                self.add_error("projects", _("These projects belong to another client: %(names)s") % {"names": ", ".join(wrong)})
        else:
            cleaned["projects"] = []
            if company is None:
                cleaned["company"] = Company.objects.filter(is_internal=True).first()
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.company = self.cleaned_data.get("company")
        user.is_staff = self.cleaned_data.get("is_staff", False)
        if not user.pk:
            user.username = self.cleaned_data["email"]
            user.set_unusable_password()
        if commit:
            user.save()
            user.projects.set(self.cleaned_data.get("projects") or [])
        return user
