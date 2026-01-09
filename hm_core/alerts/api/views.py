from __future__ import annotations

from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from hm_core.alerts.models import Alert, Notification
from hm_core.alerts.selectors import alerts_qs, notifications_qs
from hm_core.alerts.services import AlertContext, AlertService
from hm_core.alerts.api.serializers import AlertSerializer, NotificationSerializer


class ScopedContextMixin:
    def ctx(self) -> AlertContext:
        tenant_id = self.request.tenant_id
        facility_id = self.request.facility_id
        actor_user_id = getattr(self.request.user, "id", None)
        return AlertContext(tenant_id=tenant_id, facility_id=facility_id, actor_user_id=actor_user_id)


class AlertViewSet(ScopedContextMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AlertSerializer

    def get_queryset(self):
        c = self.ctx()
        qs = alerts_qs(tenant_id=c.tenant_id, facility_id=c.facility_id)
        status_q = self.request.query_params.get("status")
        severity_q = self.request.query_params.get("severity")
        encounter_id = self.request.query_params.get("encounter_id")
        if status_q:
            qs = qs.filter(status=status_q)
        if severity_q:
            qs = qs.filter(severity=severity_q)
        if encounter_id:
            qs = qs.filter(encounter_id=encounter_id)
        return qs.order_by("-created_at")

    @action(methods=["POST"], detail=True, url_path="ack")
    def ack(self, request, pk=None):
        alert = AlertService.ack_alert(ctx=self.ctx(), alert_id=pk)
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)


class NotificationViewSet(ScopedContextMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        c = self.ctx()
        qs = notifications_qs(tenant_id=c.tenant_id, facility_id=c.facility_id, user_id=c.actor_user_id)
        is_read = self.request.query_params.get("is_read")
        if is_read in ("true", "false"):
            qs = qs.filter(is_read=(is_read == "true"))
        return qs.order_by("-created_at")

    @action(methods=["POST"], detail=True, url_path="mark-read")
    def mark_read(self, request, pk=None):
        c = self.ctx()
        notif = Notification.objects.get(
            id=pk,
            tenant_id=c.tenant_id,
            facility_id=c.facility_id,
            recipient_id=c.actor_user_id,
        )
        notif.mark_read()
        notif.save(update_fields=["is_read", "read_at", "updated_at"])
        return Response(NotificationSerializer(notif).data, status=status.HTTP_200_OK)
