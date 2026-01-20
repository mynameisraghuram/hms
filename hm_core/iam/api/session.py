# backend/hm_core/iam/api/session.py

from __future__ import annotations

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiParameter

from hm_core.iam.api.schema_serializers import SessionBootstrapResponseSerializer
from hm_core.iam.scope import resolve_scope_from_headers, assert_user_membership
from hm_core.iam.services.membership import list_user_facilities
from hm_core.iam.models import FacilityMembership, RolePermission


class SessionBootstrapView(APIView):
    """
    Frontend bootstrap endpoint.

    - Requires auth (cookie or header JWT).
    - Scope headers OPTIONAL.
      - If provided -> validated + membership enforced.
      - If not provided -> server chooses a default scope from memberships.
    - Returns everything needed for UI initialization.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: SessionBootstrapResponseSerializer},
        tags=["IAM"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=False, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=False, type=str),
        ],
    )
    def get(self, request):
        # 1) memberships
        memberships = list_user_facilities(request.user.id)

        # 2) determine active scope:
        #    a) if headers provided, validate + enforce membership
        scope = resolve_scope_from_headers(request)
        if scope is not None:
            assert_user_membership(request.user, scope)
            active_scope = {"tenant_id": str(scope.tenant_id), "facility_id": str(scope.facility_id)}
        else:
            # b) choose default from memberships (primary first, else first)
            chosen = None
            for m in memberships:
                if m.get("is_primary"):
                    chosen = m
                    break
            if chosen is None and memberships:
                chosen = memberships[0]

            active_scope = None
            if chosen:
                active_scope = {
                    "tenant_id": str(chosen.get("tenant_id")),
                    "facility_id": str(chosen.get("facility_id")),
                }

        # 3) active context (tenant/facility/role + permissions)
        active_tenant = None
        active_facility = None
        active_role = None
        permissions: list[str] = []

        if active_scope:
            tenant_id = active_scope["tenant_id"]
            facility_id = active_scope["facility_id"]

            membership = (
                FacilityMembership.objects.select_related("tenant", "facility", "role", "user_profile", "user_profile__user")
                .filter(
                    is_active=True,
                    tenant_id=tenant_id,
                    facility_id=facility_id,
                    user_profile__user_id=request.user.id,
                    user_profile__is_active=True,
                )
                .first()
            )

            # membership should exist; if not, behave safely
            if membership:
                t = membership.tenant
                f = membership.facility
                r = membership.role

                active_tenant = {"id": str(t.id), "code": getattr(t, "code", None), "name": getattr(t, "name", None)}
                active_facility = {"id": str(f.id), "code": getattr(f, "code", None), "name": getattr(f, "name", None)}
                active_role = {"id": str(r.id), "code": getattr(r, "code", None), "name": getattr(r, "name", None)}

                permissions = list(
                    RolePermission.objects.select_related("permission")
                    .filter(role_id=r.id)
                    .values_list("permission__code", flat=True)
                )

        # 4) response
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
                "active_tenant": active_tenant,
                "active_facility": active_facility,
                "active_role": active_role,
                "permissions": permissions,
                "feature_flags": {},  # later: tenant/facility policy flags
                "server_time": timezone.now(),
                "api_version": "0.1.0",
            }
        )
