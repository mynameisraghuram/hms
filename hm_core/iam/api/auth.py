# backend/hm_core/iam/api/auth.py

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from hm_core.iam.api.schema_serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    RefreshResponseSerializer,
    LogoutResponseSerializer,
)

def _seconds(value: Any) -> int:
    """
    Convert a JWT lifetime setting into seconds.
    Supports timedelta OR int/float (already seconds).
    """
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    try:
        return int(value)
    except Exception:
        # safest fallback: 0 means "session cookie"
        return 0


def _set_auth_cookies(response: Response, *, access: str, refresh: str) -> None:
    jwt_cfg = getattr(settings, "SIMPLE_JWT", {}) or {}

    access_name = jwt_cfg.get("AUTH_COOKIE", "hm_access")
    refresh_name = jwt_cfg.get("AUTH_COOKIE_REFRESH", "hm_refresh")

    access_lifetime = _seconds(jwt_cfg.get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=10)))
    refresh_lifetime = _seconds(jwt_cfg.get("REFRESH_TOKEN_LIFETIME", timedelta(days=14)))

    secure = bool(jwt_cfg.get("AUTH_COOKIE_SECURE", False))
    samesite = jwt_cfg.get("AUTH_COOKIE_SAMESITE", "Lax")

    response.set_cookie(
        access_name,
        access,
        max_age=access_lifetime,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )
    response.set_cookie(
        refresh_name,
        refresh,
        max_age=refresh_lifetime,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    jwt_cfg = getattr(settings, "SIMPLE_JWT", {}) or {}
    access_name = jwt_cfg.get("AUTH_COOKIE", "hm_access")
    refresh_name = jwt_cfg.get("AUTH_COOKIE_REFRESH", "hm_refresh")
    response.delete_cookie(access_name, path="/")
    response.delete_cookie(refresh_name, path="/")


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginRequestSerializer,
        responses={200: LoginResponseSerializer},
        tags=["IAM"],
    )

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access = serializer.validated_data["access"]
        refresh = serializer.validated_data["refresh"]

        res = Response({"detail": "login ok"}, status=status.HTTP_200_OK)
        _set_auth_cookies(res, access=access, refresh=refresh)
        return res


class RefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: RefreshResponseSerializer},
        tags=["IAM"],
    )

    def post(self, request):
        jwt_cfg = getattr(settings, "SIMPLE_JWT", {}) or {}
        refresh_cookie_name = jwt_cfg.get("AUTH_COOKIE_REFRESH", "hm_refresh")
        refresh = request.COOKIES.get(refresh_cookie_name)

        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        serializer.is_valid(raise_exception=True)

        access = serializer.validated_data["access"]
        new_refresh = serializer.validated_data.get("refresh", refresh)

        res = Response({"detail": "refreshed"}, status=status.HTTP_200_OK)
        _set_auth_cookies(res, access=access, refresh=new_refresh)
        return res


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: LogoutResponseSerializer},
        tags=["IAM"],
    )

    def post(self, request):
        res = Response({"detail": "logged out"}, status=status.HTTP_200_OK)
        _clear_auth_cookies(res)
        return res
