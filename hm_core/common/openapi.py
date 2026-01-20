# backend/hm_core/common/openapi.py
from __future__ import annotations

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter


class HMSAutoSchema(AutoSchema):
    """
    Global OpenAPI improvements for HM Software:

    - Adds scope headers (X-Tenant-Id, X-Facility-Id) automatically to scoped endpoints
    - Adds Idempotency-Key header automatically (optional)
    - Skips scope headers for auth endpoints and schema/docs endpoints
    """

    SCOPE_HEADERS = [
        OpenApiParameter(
            name="X-Tenant-Id",
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.HEADER,
            required=True,
            description="Tenant scope UUID (required for scoped endpoints).",
        ),
        OpenApiParameter(
            name="X-Facility-Id",
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.HEADER,
            required=True,
            description="Facility scope UUID (required for scoped endpoints).",
        ),
    ]

    IDEMPOTENCY_HEADER = OpenApiParameter(
        name="Idempotency-Key",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        required=False,
        description=(
            "Optional idempotency key for safely retrying POST/PUT requests. "
            "Strongly recommended for client retries."
        ),
    )

    def _is_unscoped_endpoint(self) -> bool:
        """
        Endpoints that should NOT show tenant/facility headers in schema.
        """
        view = getattr(self, "view", None)
        if view is None:
            return False

        # Skip schema & swagger views (spectacular itself)
        view_class_name = view.__class__.__name__
        if view_class_name in {"SpectacularAPIView", "SpectacularSwaggerView"}:
            return True

        # Skip auth module endpoints
        module = view.__class__.__module__ or ""
        if module.startswith("hm_core.iam.api."):
            return True

        # In your API layout, /me and /auth/* are unscoped.
        # The module check already covers them, but keep this as belt+suspenders.
        path = ""
        try:
            path = getattr(view.request, "path", "") or ""
        except Exception:
            path = ""

        if "/auth/" in path or path.endswith("/me/") or "/api/schema/" in path or "/api/docs/" in path:
            return True

        return False

    def get_override_parameters(self):
        params = list(super().get_override_parameters() or [])

        # Always include Idempotency-Key (harmless for GET too, and super useful for docs)
        # but don't duplicate if already present in a specific endpoint decorator.
        if not any(p.name.lower() == "idempotency-key" for p in params):
            params.append(self.IDEMPOTENCY_HEADER)

        # Add scope headers to ALL scoped endpoints unless explicitly unscoped
        if not self._is_unscoped_endpoint():
            existing = {p.name.lower() for p in params}
            for p in self.SCOPE_HEADERS:
                if p.name.lower() not in existing:
                    params.append(p)

        return params
