from rest_framework import serializers

from apps.accounts.models import Organization, User
from apps.accounts.serializers import UserMiniSerializer

from .models import Milestone, Project, WorkflowStatus


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ("id", "name", "starts_on", "ends_on", "order")


class ProjectSerializer(serializers.ModelSerializer):
    client = serializers.CharField(source="client.name")
    lead = UserMiniSerializer(allow_null=True)

    class Meta:
        model = Project
        fields = ("key", "name", "description", "client", "lead", "is_archived")


class ProjectCreateSerializer(serializers.Serializer):
    key = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9]{1,5}$", error_messages={
        "invalid": "La clé doit faire 2 à 6 caractères (lettres et chiffres, commençant par une lettre)."})
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True)
    client = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.filter(kind="client"))
    lead = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(organization__kind="digitalia"),
                                              required=False, allow_null=True)
    dev_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    licence_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    licence_start = serializers.CharField(required=False, allow_blank=True)

    def validate_key(self, value):
        value = value.upper()
        if Project.objects.filter(key=value).exists():
            raise serializers.ValidationError("Cette clé est déjà utilisée.")
        return value

    def validate_licence_start(self, value):
        if not value:
            return None
        from apps.finance.service import parse_month

        try:
            return parse_month(value)
        except (ValueError, IndexError) as exc:
            raise serializers.ValidationError("Mois attendu au format AAAA-MM.") from exc


class ProjectUpdateSerializer(serializers.ModelSerializer):
    lead = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(organization__kind="digitalia"),
                                              required=False, allow_null=True)

    class Meta:
        model = Project
        fields = ("name", "description", "lead")


class WorkflowStatusSerializer(serializers.ModelSerializer):
    next: "serializers.SlugRelatedField[WorkflowStatus]" = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="key")

    class Meta:
        model = WorkflowStatus
        fields = ("key", "label", "client_label", "ball", "is_closed", "is_terminal_ok", "order", "color", "next",
                  "is_system")
