from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organization, User

admin.site.register(Organization)


@admin.register(User)
class OrbitUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "organization", "job", "is_active")
    fieldsets = (*(UserAdmin.fieldsets or ()),
                 ("Orbit", {"fields": ("organization", "job", "invited_at", "activated_at")}))
