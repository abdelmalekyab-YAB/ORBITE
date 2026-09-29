from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Company, Milestone, Project, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "is_internal", "created_at")
    list_filter = ("is_internal",)
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + ((_("Orbit"), {"fields": ("role", "company")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_("Orbit"), {"fields": ("first_name", "last_name", "email", "role", "company")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "company", "is_active")
    list_filter = ("role", "company", "is_active")


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "company", "lead", "is_active")
    list_filter = ("company", "is_active")
    search_fields = ("name", "key")
    filter_horizontal = ("members",)
    inlines = [MilestoneInline]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "kind", "status", "due_date", "is_client_visible")
    list_filter = ("kind", "status", "project")
