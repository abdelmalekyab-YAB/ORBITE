from rest_framework import serializers

from . import models as M


class BillingProfileSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    client_id = serializers.CharField(source="project.client_id", read_only=True)
    client_name = serializers.CharField(source="project.client.name", read_only=True)
    documents = serializers.SerializerMethodField()

    class Meta:
        model = M.BillingProfile
        fields = [
            "id",
            "project",
            "project_name",
            "client_id",
            "client_name",
            "billing_type",
            "monthly_amount",
            "quote_amount",
            "cost",
            "start_month",
            "end_month",
            "status",
            "note",
            "documents",
            "updated_at",
        ]

    def get_documents(self, obj):
        return [{"id": d.id, "kind": d.kind, "name": d.original_name, "url": d.file.url} for d in obj.documents.all()]


class InvoiceSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = M.Invoice
        fields = [
            "id",
            "project",
            "service_month",
            "amount",
            "label",
            "kind",
            "status",
            "invoice_number",
            "po_number",
            "issued_on",
            "document_url",
            "document_name",
            "due_date",
            "payment_status",
            "paid_on",
            "zoho_invoice_id",
            "updated_at",
        ]
        read_only_fields = ["document_url", "zoho_invoice_id"]

    def get_document_url(self, obj):
        return obj.document.url if obj.document else None


class FixedOccurrenceSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = M.FixedOccurrence
        fields = [
            "id",
            "project",
            "month",
            "override_amount",
            "billed_marked",
            "document_url",
            "document_name",
            "due_date",
            "payment_status",
            "paid_on",
        ]

    def get_document_url(self, obj):
        return obj.document.url if obj.document else None


class ExpenseSerializer(serializers.ModelSerializer):
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = M.Expense
        fields = [
            "id",
            "date",
            "supplier",
            "category",
            "label",
            "project",
            "amount_ht",
            "vat",
            "receipt_url",
            "receipt_name",
            "created_at",
        ]

    def get_receipt_url(self, obj):
        return obj.receipt.url if obj.receipt else None


class PaymentUpdateSerializer(serializers.Serializer):
    """Dialogue « paiement » : statut + échéance + payé le (SPEC §6)."""

    payment_status = serializers.ChoiceField(choices=["pending", "late", "paid"])
    due_date = serializers.DateField(required=False, allow_null=True)
    paid_on = serializers.DateField(required=False, allow_null=True)
