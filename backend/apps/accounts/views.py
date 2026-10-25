from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.projects.models import Project, ProjectAccess
from orbit.permissions import IsOrbitAdmin

from . import invitations
from .models import Organization, User
from .serializers import (
    ClientCreateSerializer,
    InviteSerializer,
    MeSerializer,
    OrganizationSerializer,
    PasswordSerializer,
    UserSerializer,
    UserUpdateSerializer,
    split_name,
    user_status,
)


def error(detail: str, code: str, http=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": detail, "code": code}, status=http)


def session(user: User) -> dict:
    """Tokens + `me` ; pose `activated_at` à la première connexion (règle 4)."""
    now = timezone.now()
    if user.activated_at is None:
        user.activated_at = now
    user.last_login = now
    user.save(update_fields=["activated_at", "last_login"])
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "me": MeSerializer(user).data}


class LoginView(APIView):
    """POST /auth/login : e-mail + mot de passe → tokens + `me` (règle 4 : messages explicites)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        user = User.objects.filter(email__iexact=email).select_related("organization").first()
        if user is None or not user.check_password(request.data.get("password") or ""):
            if user is not None and user_status(user) == "invited" and not user.has_usable_password():
                return error("Votre invitation n'a pas encore été acceptée : utilisez le lien reçu par e-mail pour "
                             "créer votre mot de passe.", "invitation_pending", status.HTTP_401_UNAUTHORIZED)
            return error("E-mail ou mot de passe incorrect.", "invalid_credentials", status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return error("Ce compte a été désactivé. Contactez Digitalia.", "account_disabled",
                         status.HTTP_401_UNAUTHORIZED)
        return Response(session(user))


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)


def _set_password(request, *, invitation: bool):
    s = PasswordSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    user = invitations.user_from_token(s.validated_data["uid"], s.validated_data["token"])
    if user is None or not user.is_active:
        return error("Ce lien n'est plus valide. Demandez un nouveau lien à Digitalia.", "invalid_link")
    try:
        validate_password(s.validated_data["password"], user)
    except DjangoValidationError as exc:
        return error(" ".join(exc.messages), "weak_password")
    user.set_password(s.validated_data["password"])
    user.save()
    return Response(session(user))


class InviteAcceptView(APIView):
    """POST /auth/invite/accept {uid, token, password} → définit le mot de passe, pose `activated_at`, connecte."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return _set_password(request, invitation=True)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return _set_password(request, invitation=False)


class PasswordForgotView(APIView):
    """POST /auth/password/forgot {email} — répond toujours 200 (ne révèle pas si le compte existe)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            if user_status(user) == "invited" and not user.has_usable_password():
                invitations.send_invitation(user)
            else:
                invitations.send_password_reset(user)
        return Response({"detail": "Si un compte existe pour cette adresse, un e-mail vient d'être envoyé."})


# ---------- Accès (admin) ----------

class UserListView(APIView):
    permission_classes = [IsOrbitAdmin]

    def get(self, request):
        users = User.objects.select_related("organization").order_by("organization__kind", "first_name")
        if kind := request.query_params.get("kind"):
            users = users.filter(organization__kind=kind)
        return Response(UserSerializer(users, many=True).data)

    @transaction.atomic
    def post(self, request):
        s = InviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        first, last = split_name(d["name"])
        user = User(email=d["email"], username=d["email"], first_name=first, last_name=last,
                    organization=d["organization"], job=d["job"])
        user.set_unusable_password()
        user.save()
        invitations.send_invitation(user, request.user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsOrbitAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        s = UserUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "name" in d:
            user.first_name, user.last_name = split_name(d["name"])
        if "email" in d and d["email"].lower() != user.email.lower():
            if User.objects.filter(email__iexact=d["email"]).exclude(pk=user.pk).exists():
                return error("Un compte existe déjà avec cet e-mail.", "email_taken")
            user.email = user.username = d["email"].lower()
        if "job" in d:
            if not user.is_digitalia:
                return error("Le rôle ne se modifie que pour l'équipe Digitalia.", "invalid_job")
            if user.pk == request.user.pk and d["job"] != user.job:
                return error("Vous ne pouvez pas changer votre propre rôle.", "self_job")
            user.job = d["job"]
        user.save()
        return Response(UserSerializer(user).data)

    @transaction.atomic
    def delete(self, request, pk):
        """RGPD : anonymise le compte (l'historique des demandes est conservé, sans données personnelles)."""
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return error("Vous ne pouvez pas supprimer votre propre compte.", "self_delete")
        anonymize(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def anonymize(user: User) -> None:
    from apps.notifications.models import Notification

    user.email = user.username = f"supprime-{user.pk}@orbit.invalid"
    user.first_name, user.last_name = "Utilisateur", "supprimé"
    user.is_active = False
    user.set_unusable_password()
    user.save()
    ProjectAccess.objects.filter(user=user).delete()
    Notification.objects.filter(user=user).delete()


class UserActionView(APIView):
    """POST /users/{id}/{activate|deactivate|resend-invite|reset-password}."""

    permission_classes = [IsOrbitAdmin]

    def post(self, request, pk, action):
        user = get_object_or_404(User, pk=pk)
        if action in ("activate", "deactivate"):
            if user.pk == request.user.pk:
                return error("Vous ne pouvez pas désactiver votre propre compte.", "self_deactivate")
            user.is_active = action == "activate"
            user.save(update_fields=["is_active"])
        elif action == "resend-invite":
            if user_status(user) != "invited":
                return error("Ce compte est déjà actif.", "not_invited")
            invitations.send_invitation(user, request.user)
        elif action == "reset-password":
            if not user.is_active:
                return error("Ce compte est désactivé.", "account_disabled")
            invitations.send_password_reset(user)
        else:
            return error("Action inconnue.", "unknown_action", status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data)


class ProjectAccessView(APIView):
    """PUT /users/{id}/project-access {projects: [KEY…]} — uniquement des projets de l'organisation du client."""

    permission_classes = [IsOrbitAdmin]

    @transaction.atomic
    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.is_digitalia:
            return error("L'équipe Digitalia voit tous les projets.", "digitalia_user")
        keys = {str(k).upper() for k in request.data.get("projects", [])}
        projects = list(Project.objects.filter(key__in=keys, client=user.organization_id))
        if len(projects) != len(keys):
            return error("Un client ne peut accéder qu'aux projets de son organisation.", "foreign_project")
        ProjectAccess.objects.filter(user=user).exclude(project__in=projects).delete()
        for p in projects:
            ProjectAccess.objects.get_or_create(user=user, project=p)
        return Response(UserSerializer(user).data)


class OrganizationListView(APIView):
    permission_classes = [IsOrbitAdmin]

    def get(self, request):
        orgs = Organization.objects.filter(kind=Organization.Kind.CLIENT).order_by("name")
        return Response(OrganizationSerializer(orgs, many=True).data)

    @transaction.atomic
    def post(self, request):
        """Crée le client et son premier contact, invité par e-mail."""
        s = ClientCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        org = Organization.objects.create(name=d["name"], kind=Organization.Kind.CLIENT)
        first, last = split_name(d["contact_name"])
        user = User(email=d["contact_email"], username=d["contact_email"], first_name=first, last_name=last,
                    organization=org, job=User.Job.CLIENT)
        user.set_unusable_password()
        user.save()
        invitations.send_invitation(user, request.user)
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    permission_classes = [IsOrbitAdmin]

    def patch(self, request, pk):
        org = get_object_or_404(Organization, pk=pk, kind=Organization.Kind.CLIENT)
        s = OrganizationSerializer(org, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
