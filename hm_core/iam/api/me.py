# backend/hm_core/iam/api/me.py

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hm_core.iam.scope import resolve_scope_from_headers, assert_user_membership
from hm_core.iam.services.membership import is_user_member_of_facility, list_user_facilities


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        raise ValidationError({field_name: "Invalid UUID"})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns user info + memberships.
        Scope headers are OPTIONAL for GET /me.
        If scope headers are provided, they MUST be valid and user MUST be a member, else 400/403.
        """
        # If headers are present, validate and attach scope
        scope = resolve_scope_from_headers(request)
        if scope is not None:
            # Ensures 403 if not a member
            assert_user_membership(request.user, scope)

            # Attach for downstream consistency (even if middleware didn’t)
            request.scope = scope
            request.tenant_id = scope.tenant_id
            request.facility_id = scope.facility_id

        memberships = list_user_facilities(request.user.id)

        active_scope = None
        if getattr(request, "scope", None):
            active_scope = {
                "tenant_id": str(request.scope.tenant_id),
                "facility_id": str(request.scope.facility_id),
            }

        return Response(
            {
                "user": {
                    "id": request.user.id,
                    "username": getattr(request.user, "username", None),
                    "email": getattr(request.user, "email", None),
                    "is_superuser": bool(getattr(request.user, "is_superuser", False)),
                },
                "memberships": memberships,
                "active_scope": active_scope,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """
        Switch active tenant/facility scope.
        Expects: {"tenant_id": "uuid", "facility_id": "uuid"}

        Note: Server cannot "set headers" for the client; client should use returned scope
        and send X-Tenant-Id / X-Facility-Id headers in subsequent requests.
        """
        tenant_id_raw = request.data.get("tenant_id")
        facility_id_raw = request.data.get("facility_id")

        if not tenant_id_raw or not facility_id_raw:
            raise ValidationError("Both tenant_id and facility_id are required")

        tenant_id = _parse_uuid(str(tenant_id_raw), "tenant_id")
        facility_id = _parse_uuid(str(facility_id_raw), "facility_id")

        if not is_user_member_of_facility(
            user_id=request.user.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
        ):
            # 403 fits “you’re authenticated but not allowed”
            raise PermissionDenied("You do not have access to the selected facility.")

        return Response(
            {
                "message": "Scope switched successfully",
                "active_scope": {
                    "tenant_id": str(tenant_id),
                    "facility_id": str(facility_id),
                },
            },
            status=status.HTTP_200_OK,
        )
