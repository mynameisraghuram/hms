# backend/hm_core/audit/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers
from hm_core.audit.api.serializers import AuditEventSerializer
from hm_core.audit.selectors import list_audit_events


def _get_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    tenant_id = getattr(request, "tenant_id", None)
    facility_id = getattr(request, "facility_id", None)

    if tenant_id and facility_id:
        try:
            return UUID(str(tenant_id)), UUID(str(facility_id)), None
        except Exception:
            return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    try:
        scope = resolve_scope_from_headers(request)
    except Exception:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return scope.tenant_id, scope.facility_id, None


class AuditEventViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        entity_type = request.query_params.get("entity_type") or None
        entity_id_raw = request.query_params.get("entity_id") or None
        event_code = request.query_params.get("event_code") or None
        actor_user_raw = request.query_params.get("actor_user_id")

        entity_id = None
        if entity_id_raw:
            try:
                entity_id = UUID(str(entity_id_raw))
            except Exception:
                return Response({"detail": "Invalid entity_id (UUID expected)"}, status=status.HTTP_400_BAD_REQUEST)

        actor_user_id = None
        if actor_user_raw is not None and actor_user_raw != "":
            try:
                actor_user_id = int(actor_user_raw)
            except Exception:
                return Response({"detail": "Invalid actor_user_id (int expected)"}, status=status.HTTP_400_BAD_REQUEST)

        qs = list_audit_events(
            tenant_id=tenant_id,
            facility_id=facility_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_code=event_code,
            actor_user_id=actor_user_id,
        )

        # keep it safe: timeline endpoints can get huge
        limit = request.query_params.get("limit")
        try:
            limit_n = int(limit) if limit else 200
        except Exception:
            limit_n = 200
        limit_n = max(1, min(limit_n, 500))

        return Response(AuditEventSerializer(qs[:limit_n], many=True).data, status=status.HTTP_200_OK)
