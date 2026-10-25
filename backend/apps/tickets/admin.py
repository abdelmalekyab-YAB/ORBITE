from django.contrib import admin

from .models import Attachment, Comment, Ticket, TicketEvent


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("__str__", "title", "status", "priority", "assignee", "is_internal")
    list_filter = ("project", "status__key", "type", "is_internal")
    # Le statut ne se modifie que via workflow.transition (CLAUDE.md).
    readonly_fields = ("status", "number", "closed_at")


admin.site.register([Comment, Attachment, TicketEvent])
