from django.contrib import admin

from .models import Attachment, Comment, Ticket, TicketEvent


class CommentInline(admin.StackedInline):
    model = Comment
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


class EventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "user", "kind", "field", "old_value", "new_value", "is_internal")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "project", "type", "status", "priority", "origin", "visibility", "assignee", "due_date")
    list_filter = ("status", "type", "priority", "origin", "visibility", "project")
    search_fields = ("title", "description")
    readonly_fields = ("number", "origin", "author", "author_company", "created_at", "updated_at", "closed_at")
    inlines = [CommentInline, AttachmentInline, EventInline]
