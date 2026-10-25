from rest_framework import serializers

from apps.tickets.models import QuoteInstallment

from .models import DevInstallment, FinanceSettings, ProjectFinance
from .service import parse_month


class MonthField(serializers.Field):
    """Mois au format « YYYY-MM » (accepte aussi une date complète) ; stocké au 1er du mois."""

    def to_representation(self, value):
        return value.strftime("%Y-%m") if value else None

    def to_internal_value(self, data):
        if data in (None, ""):
            return None
        try:
            return parse_month(str(data))
        except (ValueError, IndexError) as exc:
            raise serializers.ValidationError("Mois attendu au format AAAA-MM.") from exc


class ProjectFinanceSerializer(serializers.ModelSerializer):
    licence_start = MonthField(required=False, allow_null=True)
    licence_end = MonthField(required=False, allow_null=True)
    cost_month = MonthField(required=False, allow_null=True)

    class Meta:
        model = ProjectFinance
        fields = ("dev_price", "licence_amount", "licence_start", "licence_end", "cost_mode", "cost_monthly",
                  "cost_days", "cost_tjm", "cost_month")


class DevInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevInstallment
        fields = ("id", "due_on", "amount", "is_paid", "paid_on")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être positif.")
        return value


class QuoteInstallmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteInstallment
        fields = ("id", "due_on", "amount", "is_paid", "paid_on")


class FinanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSettings
        fields = ("default_tjm",)


class StaffRowSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    monthly_salary = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    allocations = serializers.DictField(child=serializers.IntegerField(min_value=0, max_value=100))
