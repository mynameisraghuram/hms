# backend/hm_core/billing/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.response import Response

from hm_core.billing.api.serializers import BillableEventSerializer
from hm_core.billing.selectors import billable_events_filtered
from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers


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
        scope = None

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return scope.tenant_id, scope.facility_id, None


class BillableEventViewSet(viewsets.ViewSet):
    """
    Read-only list endpoint for billing events.
    Filters:
      - ?encounter=<uuid>
      - ?patient=<uuid>
    """

    def list(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        enc = request.query_params.get("encounter")
        pat = request.query_params.get("patient")

        encounter_id = UUID(enc) if enc else None
        patient_id = UUID(pat) if pat else None

        qs = billable_events_filtered(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
        )

        return Response(BillableEventSerializer(qs, many=True).data, status=status.HTTP_200_OK)
