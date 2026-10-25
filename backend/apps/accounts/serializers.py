from rest_framework import serializers

from .models import Organization, User


class UserMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="get_full_name")

    class Meta:
        model = User
        fields = ("id", "name", "initials", "job")


class MeSerializer(serializers.ModelSerializer):
    organization = serializers.CharField(source="organization.name", default=None)
    organization_kind = serializers.CharField(source="organization.kind", default=None)
    name = serializers.CharField(source="get_full_name")
    first_name = serializers.CharField()
    projects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "name", "first_name", "initials", "job", "organization", "organization_kind",
                  "is_digitalia", "is_orbit_admin", "projects")

    def get_projects(self, user):
        from apps.projects.scope import visible_projects

        return [{"key": p.key, "name": p.name, "client": p.client.name} for p in visible_projects(user)]


def user_status(user: User) -> str:
    if not user.is_active:
        return "disabled"
    if user.invited_at and not user.activated_at:
        return "invited"
    return "active"


class UserSerializer(serializers.ModelSerializer):
    """Vue admin d'un utilisateur (écran Accès)."""

    name = serializers.CharField(source="get_full_name", read_only=True)
    organization = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "name", "initials", "job", "organization", "is_active",
                  "status", "invited_at", "activated_at", "projects")

    def get_organization(self, u):
        return {"id": u.organization_id, "name": u.organization.name, "kind": u.organization.kind} \
            if u.organization_id else None

    def get_status(self, u):
        return user_status(u)

    def get_projects(self, u):
        return sorted(a.project.key for a in u.project_access.select_related("project"))


def split_name(name: str) -> tuple[str, str]:
    parts = name.strip().split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


class InviteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    job = serializers.ChoiceField(["admin", "pm", "dev"], required=False)
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet e-mail.")
        return value.lower()

    def validate(self, data):
        org = data.get("organization")
        if org is None or org.kind == Organization.Kind.DIGITALIA:
            if "job" not in data:
                raise serializers.ValidationError({"job": "Rôle requis pour un membre Digitalia."})
            data["organization"] = Organization.objects.filter(kind=Organization.Kind.DIGITALIA).first()
        else:
            data["job"] = User.Job.CLIENT
        return data


class UserUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    job = serializers.ChoiceField(["admin", "pm", "dev"], required=False)


class OrganizationSerializer(serializers.ModelSerializer):
    users = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ("id", "name", "kind", "is_active", "users", "projects")
        read_only_fields = ("kind",)

    def get_users(self, org):
        return UserSerializer(org.users.order_by("first_name"), many=True).data

    def get_projects(self, org):
        return [{"key": p.key, "name": p.name, "is_archived": p.is_archived} for p in org.projects.order_by("key")]


class ClientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    contact_name = serializers.CharField(max_length=150)
    contact_email = serializers.EmailField()

    def validate_contact_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet e-mail.")
        return value.lower()


class PasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)
