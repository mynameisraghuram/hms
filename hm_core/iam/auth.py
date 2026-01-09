# backend/hm_core/iam/auth.py

from __future__ import annotations

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

from hm_core.iam.scope import apply_scope_from_headers


class CookieOrHeaderJWTAuthentication(JWTAuthentication):
    """
    Authenticate using:
      1) Authorization: Bearer <access>
      2) HttpOnly cookie containing access token

    ALSO enforces tenant/facility scope headers after user is known.
    """

    def authenticate(self, request):
        # 1) Prefer Authorization header
        header = self.get_header(request)
        if header:
            auth_result = super().authenticate(request)
            if auth_result is None:
                return None
            user, token = auth_result
            apply_scope_from_headers(request, user=user)
            return user, token

        # 2) Cookie access token
        cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "hm_access")
        raw_token = request.COOKIES.get(cookie_name)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        apply_scope_from_headers(request, user=user)
        return user, validated_token
