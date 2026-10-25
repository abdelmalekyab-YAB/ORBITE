from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserMiniSerializer
from apps.projects.models import Milestone

from .models import Attachment, Comment, Quote, QuoteInstallment, Ticket, TicketEvent
from .workflow import allowed_next

# Côté client, l'impact choisi se traduit en priorité (règle 7).
IMPACT_TO_PRIORITY = {"confort": "normal", "genant": "high", "bloquant": "critical"}


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ("id", "name", "content_type", "url", "created_at")

    def get_url(self, obj):
        url = obj.file.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request and url.startswith("/") else url


class CommentSerializer(serializers.ModelSerializer):
    author = UserMiniSerializer()
    author_is_digitalia = serializers.BooleanField(source="author.is_digitalia")
    attachments = AttachmentSerializer(many=True)

    class Meta:
        model = Comment
        fields = ("id", "author", "author_is_digitalia", "body", "kind", "attachments", "created_at")


class TicketEventSerializer(serializers.ModelSerializer):
    actor = UserMiniSerializer(allow_null=True)

    class Meta:
        model = TicketEvent
        fields = ("id", "actor", "kind", "from_value", "to_value", "message", "at")


class QuoteInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteInstallment
        fields = ("id", "due_on", "amount", "is_paid", "paid_on")


class QuoteSerializer(serializers.ModelSerializer):
    installments = QuoteInstallmentSerializer(many=True, read_only=True)
    decided_by = UserMiniSerializer(allow_null=True, read_only=True)
    pdf = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = ("id", "amount_ht", "parts", "description", "pdf", "status", "sent_at", "decided_at", "decided_by",
                  "installments")

    def get_pdf(self, q):
        if not q.pdf:
            return None
        request = self.context.get("request")
        url = q.pdf.url
        return request.build_absolute_uri(url) if request and url.startswith("/") else url


def quote_visible(quote, user) -> bool:
    """Un client ne voit pas un brouillon jamais envoyé."""
    return bool(quote) and (user.is_digitalia or quote.status != Quote.Status.DRAFT or quote.sent_at is not None)


class TicketSerializer(serializers.ModelSerializer):
    """Représentation liste / carte : balle, étape client, retard."""

    ref = serializers.CharField()
    project = serializers.CharField(source="project.key")
    project_name = serializers.CharField(source="project.name")
    status = serializers.CharField(source="status.key")
    status_label = serializers.CharField(source="status.label")
    client_label = serializers.SerializerMethodField()
    ball = serializers.CharField(source="status.ball")
    is_closed = serializers.BooleanField(source="status.is_closed")
    is_late = serializers.BooleanField()
    author = UserMiniSerializer()
    assignee = UserMiniSerializer(allow_null=True)
    milestone = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()  # type: ignore[assignment]  # nom imposé par l'API
    quote = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields: tuple[str, ...] = (
                  "id", "ref", "number", "project", "project_name", "type", "title", "status", "status_label",
                  "client_label", "ball", "is_closed", "is_late", "priority", "origin", "is_internal", "author",
                  "assignee", "milestone", "due_on", "parent", "billing", "estimate_days", "created_at",
                  "updated_at", "closed_at", "quote")

    def get_quote(self, t):
        q = getattr(t, "quote", None) if hasattr(t, "quote") else None
        if q is None or not quote_visible(q, self.context["request"].user):
            return None
        return {"amount_ht": str(q.amount_ht), "status": q.status}

    def get_client_label(self, t):
        return "Clôturée" if t.status.is_closed and not t.status.is_terminal_ok else t.status.client_label

    def get_milestone(self, t):
        return {"id": t.milestone_id, "name": t.milestone.name} if t.milestone else None

    def get_parent(self, t):
        return {"id": t.parent_id, "ref": t.parent.ref, "title": t.parent.title} if t.parent else None

    def to_representation(self, t):
        data = super().to_representation(t)
        user = self.context["request"].user
        if not user.is_digitalia:  # règle 2 : rien d'interne côté client
            for field in ("is_internal", "estimate_days", "parent"):
                data.pop(field, None)
        return data


class TicketDetailSerializer(TicketSerializer):
    description = serializers.CharField()
    attachments = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True)
    allowed_transitions = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    quote_detail = serializers.SerializerMethodField()

    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + ("description", "attachments", "comments", "allowed_transitions",
                                                 "children", "quote_detail")

    def get_quote_detail(self, t):
        q = getattr(t, "quote", None) if hasattr(t, "quote") else None
        return QuoteSerializer(q, context=self.context).data if quote_visible(q, self.context["request"].user) else None

    def get_attachments(self, t):
        qs = t.attachments.filter(comment__isnull=True)
        return AttachmentSerializer(qs, many=True, context=self.context).data

    def get_allowed_transitions(self, t):
        return allowed_next(t, self.context["request"].user)

    def get_children(self, t):
        if not self.context["request"].user.is_digitalia:
            return []
        return [{"id": c.id, "ref": c.ref, "title": c.title, "status": c.status.key, "status_label": c.status.label}
                for c in t.children.select_related("status", "project")]


class TicketCreateSerializer(serializers.Serializer):
    project = serializers.CharField()
    type = serializers.ChoiceField(Ticket.Type.choices)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    impact = serializers.ChoiceField(list(IMPACT_TO_PRIORITY), required=False)
    priority = serializers.ChoiceField(Ticket.Priority.choices, required=False)
    # Réservé à Digitalia (ignoré pour un client) :
    is_internal = serializers.BooleanField(required=False, default=False)
    initial_status = serializers.ChoiceField(["faire", "nouveau"], required=False, default="faire")
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(organization__kind="digitalia"),
                                                  required=False, allow_null=True)
    milestone = serializers.PrimaryKeyRelatedField(queryset=Milestone.objects.all(), required=False, allow_null=True)
    due_on = serializers.DateField(required=False, allow_null=True)
    parent = serializers.PrimaryKeyRelatedField(  # type: ignore[assignment]  # nom imposé par l'API
        queryset=Ticket.objects.all(), required=False, allow_null=True)


class TicketUpdateSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(organization__kind="digitalia"),
                                                  required=False, allow_null=True)

    class Meta:
        model = Ticket
        fields = ("title", "description", "type", "priority", "assignee", "milestone", "due_on", "is_internal",
                  "billing", "estimate_days")

    def validate_milestone(self, value):
        if value and self.instance is not None and value.project_id != self.instance.project_id:
            raise serializers.ValidationError("Cette version n'appartient pas au projet.")
        return value


class QuoteInputSerializer(serializers.Serializer):
    amount_ht = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    parts = serializers.ChoiceField([1, 2, 3], required=False)
    description = serializers.CharField(required=False, allow_blank=True)


class TriageSerializer(serializers.Serializer):
    """Décision de triage (docs/05-api.md). `quote` en JSON, ou `quote_*` à plat en multipart (avec PDF)."""

    decision = serializers.ChoiceField(["faire", "analyser", "attente", "refuse", "devis"])
    type = serializers.ChoiceField(Ticket.Type.choices, required=False)
    priority = serializers.ChoiceField(Ticket.Priority.choices, required=False)
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(organization__kind="digitalia"),
                                                  required=False, allow_null=True)
    milestone = serializers.PrimaryKeyRelatedField(queryset=Milestone.objects.all(), required=False, allow_null=True)
    due_on = serializers.DateField(required=False, allow_null=True)
    estimate_days = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    billing = serializers.ChoiceField(Ticket.Billing.choices, required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, default="")
    quote = QuoteInputSerializer(required=False)
    quote_amount_ht = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    quote_parts = serializers.ChoiceField([1, 2, 3], required=False)
    quote_description = serializers.CharField(required=False, allow_blank=True)
    quote_pdf = serializers.FileField(required=False)

    FIELDS = ("type", "priority", "assignee", "milestone", "due_on", "estimate_days", "billing")

    def quote_data(self) -> dict:
        d = self.validated_data
        flat = {k: d[f"quote_{k}"] for k in ("amount_ht", "parts", "description") if f"quote_{k}" in d}
        return {**flat, **d.get("quote", {})}
