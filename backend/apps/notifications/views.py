from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from orbit.permissions import IsPmOrAdmin

from .models import Notification, NotificationSetting
from .service import SUBJECTS


class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSetting
        exclude = ("id", "created_at", "updated_at")


class NotificationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    ticket = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "ticket", "payload", "created_at", "read_at")

    def get_ticket(self, n):
        return {"id": n.ticket_id, "ref": n.ticket.ref, "title": n.ticket.title} if n.ticket_id else None

    def get_title(self, n):
        if n.kind == Notification.Kind.DIGEST:
            return f"{len(n.payload.get('tickets', []))} nouvelle(s) demande(s) depuis hier"
        return SUBJECTS[n.kind].format(ref=n.ticket.ref) if n.ticket_id else n.get_kind_display()


class NotificationSettingsView(APIView):
    """GET / PUT /settings/notifications — pm / admin."""

    permission_classes = [IsPmOrAdmin]

    def get(self, request):
        return Response(NotificationSettingSerializer(NotificationSetting.load()).data)

    def put(self, request):
        s = NotificationSettingSerializer(NotificationSetting.load(), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class NotificationListView(APIView):
    """GET /notifications — les 30 dernières de l'utilisateur + nombre de non lues."""

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).select_related("ticket__project")
        return Response({"unread": qs.filter(read_at__isnull=True).count(),
                         "results": NotificationSerializer(qs[:30], many=True).data})


class NotificationReadView(APIView):
    def post(self, request, pk=None):
        qs = Notification.objects.filter(user=request.user, read_at__isnull=True)
        if pk is not None:
            get_object_or_404(Notification, pk=pk, user=request.user)
            qs = qs.filter(pk=pk)
        qs.update(read_at=timezone.now())
        return Response({"unread": Notification.objects.filter(user=request.user, read_at__isnull=True).count()})
