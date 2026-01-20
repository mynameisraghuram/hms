from __future__ import annotations

from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

from hm_core.audit.api.serializers import AuditEventSerializer
from hm_core.audit.models import AuditEvent
from hm_core.audit.selectors import list_audit_events
from hm_core.common.api.pagination import DefaultPagination, paginate
from hm_core.common.scope import require_scope


class AuditEventViewSet(viewsets.GenericViewSet):
    """
    List audit/timeline events (scoped).
    """
    permission_classes = [IsAuthenticated]

    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.none()

    @extend_schema(
        tags=["Audit"],
        responses={200: AuditEventSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="entity_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by entity type (e.g. Encounter, OrderItem, Invoice).",
            ),
            OpenApiParameter(
                name="entity_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by entity UUID.",
            ),
            OpenApiParameter(
                name="event_code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by event code (e.g. encounter.closed, lab.result.released).",
            ),
            OpenApiParameter(
                name="actor_user_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by actor user id (int).",
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional alias for page_size (max 500). Prefer page/page_size.",
            ),
        ],
    )
    def list(self, request):
        scope = require_scope(request)

        entity_type = request.query_params.get("entity_type") or None
        entity_id_raw = request.query_params.get("entity_id") or None
        event_code = request.query_params.get("event_code") or None
        actor_user_raw = request.query_params.get("actor_user_id")

        entity_id = None
        if entity_id_raw:
            try:
                entity_id = UUID(str(entity_id_raw))
            except Exception:
                raise DRFValidationError({"entity_id": "Invalid UUID"})

        actor_user_id = None
        if actor_user_raw is not None and actor_user_raw != "":
            try:
                actor_user_id = int(actor_user_raw)
            except Exception:
                raise DRFValidationError({"actor_user_id": "Invalid int"})

        qs = list_audit_events(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_code=event_code,
            actor_user_id=actor_user_id,
        )

        # Support legacy `limit` as alias for page_size but keep paginated contract.
        limit = request.query_params.get("limit")
        paginator = None
        if limit:
            try:
                n = int(limit)
                n = max(1, min(n, 500))
                paginator = DefaultPagination()
                paginator.page_size = n
            except Exception:
                # If invalid, just ignore and use default pagination.
                paginator = None

        return paginate(request, qs, AuditEventSerializer, paginator=paginator)
