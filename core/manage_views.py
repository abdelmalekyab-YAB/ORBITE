"""Management screens: clients, projects and accounts (Orbit administrators only)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from tickets.models import Ticket

from .accounts import is_pending, send_invitation
from .manage_forms import CompanyForm, ProjectForm, UserForm
from .models import Company, Project
from .permissions import manager_required

User = get_user_model()


@manager_required
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk, is_internal=False)
    projects = company.projects.annotate(
        n_open=Count("tickets", filter=~Q(tickets__status__in=Ticket.CLOSED_STATUSES), distinct=True),
        n_members=Count("members", distinct=True),
    )
    users = company.users.order_by("-is_active", "last_name").prefetch_related("projects")
    for u in users:
        u.pending = is_pending(u)
    return render(request, "manage/company_detail.html", {"company": company, "projects": projects, "users": users})


@manager_required
def company_edit(request, pk=None):
    company = get_object_or_404(Company, pk=pk, is_internal=False) if pk else Company()
    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(request, _("Client %(name)s saved.") % {"name": company.name})
        return redirect("company_detail", pk=company.pk)
    return render(request, "manage/form.html", {
        "form": form, "title": _("Edit client") if pk else _("New client"),
        "cancel": "company_detail" if pk else "client_list", "cancel_arg": pk,
    })


@manager_required
def project_edit(request, key=None):
    project = get_object_or_404(Project, key__iexact=key) if key else Project()
    initial = {}
    if not key and request.GET.get("company", "").isdigit():
        initial["company"] = int(request.GET["company"])
    form = ProjectForm(request.POST or None, instance=project, initial=initial)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, _("Project %(name)s saved.") % {"name": project.name})
        return redirect(project)
    return render(request, "manage/project_form.html", {"form": form, "project": project if key else None})


@manager_required
def user_list(request, tab=None):
    tab = tab or request.GET.get("tab", "clients")
    users = User.objects.select_related("company").prefetch_related("projects").order_by("company__name", "last_name")
    if tab == "digitalia":
        users = users.filter(Q(role=User.Role.STAFF) | Q(is_superuser=True), is_active=True)
    elif tab == "inactive":
        users = users.filter(is_active=False)
    else:
        tab = "clients"
        users = users.filter(role=User.Role.CLIENT, is_active=True)
    q = request.GET.get("q", "").strip()
    if q:
        users = users.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
                             | Q(company__name__icontains=q))
    users = list(users)
    for u in users:
        u.pending = is_pending(u)
    return render(request, "manage/user_list.html", {"users": users, "tab": tab, "q": q})


@manager_required
def user_edit(request, pk=None):
    account = get_object_or_404(User, pk=pk) if pk else User(role=User.Role.CLIENT)
    initial = {}
    if not pk and request.GET.get("company", "").isdigit():
        initial["company"] = int(request.GET["company"])
        initial["projects"] = Project.objects.filter(company_id=initial["company"], is_active=True)
    if not pk and request.GET.get("role") == "staff":
        initial["role"] = User.Role.STAFF
        initial["company"] = Company.objects.filter(is_internal=True).first()
    form = UserForm(request.POST or None, instance=account, initial=initial)
    if request.method == "POST" and form.is_valid():
        if account.pk == request.user.pk and not form.cleaned_data.get("is_active", True):
            form.add_error("is_active", _("You cannot deactivate your own account."))
        else:
            created = account.pk is None
            account = form.save()
            if created:
                send_invitation(request, account, request.user)
                messages.success(request, _("Invitation sent to %(email)s.") % {"email": account.email})
            else:
                messages.success(request, _("Account saved."))
            return redirect("user_list_tab", tab="digitalia" if account.is_digitalia else "clients") if created else redirect("user_edit", pk=account.pk)
    context = {"form": form, "account": account if pk else None}
    if pk:
        context["pending"] = is_pending(account)
    return render(request, "manage/user_form.html", context)


@require_POST
@manager_required
def user_invite_again(request, pk):
    account = get_object_or_404(User, pk=pk, is_active=True)
    send_invitation(request, account, request.user)
    messages.success(request, _("A new invitation link was sent to %(email)s.") % {"email": account.email})
    return redirect(request.POST.get("next") or "user_list")


@require_POST
@manager_required
def user_toggle_active(request, pk):
    account = get_object_or_404(User, pk=pk)
    if account == request.user:
        messages.error(request, _("You cannot deactivate your own account."))
    else:
        account.is_active = not account.is_active
        account.save(update_fields=["is_active"])
        messages.success(request, _("Account reactivated.") if account.is_active else _("Account deactivated: it can no longer log in."))
    return redirect(request.POST.get("next") or "user_list")
