from django.contrib import admin

from . import models as M


@admin.register(M.BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
    list_display = ("project", "billing_type", "monthly_amount", "quote_amount", "start_month", "end_month", "status")
    list_filter = ("billing_type", "status")
    search_fields = ("project__name",)


@admin.register(M.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "service_month",
        "amount",
        "kind",
        "status",
        "payment_status",
        "due_date",
        "invoice_number",
    )
    list_filter = ("status", "kind", "payment_status", "service_month")
    search_fields = ("label", "invoice_number", "po_number")


@admin.register(M.FixedOccurrence)
class FixedOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("project", "month", "override_amount", "billed_marked", "payment_status", "due_date")


@admin.register(M.Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "supplier", "category", "project", "amount_ht", "vat")
    list_filter = ("category",)


admin.site.register(M.ProjectDocument)
admin.site.register(M.ZohoSyncLog)
