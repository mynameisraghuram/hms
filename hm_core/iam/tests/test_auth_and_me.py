# backend/hm_core/iam/tests/test_auth_and_me.py
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

from rest_framework_simplejwt.tokens import RefreshToken
from hm_core.conftest import _resolve_membership_model


def test_me_requires_auth():
    """
    IMPORTANT: Do NOT use api_client fixture here because in this repo it is already authenticated.
    Use a fresh APIClient to guarantee unauthenticated request.
    """
    c = APIClient()
    res = c.get("/api/me/")
    assert res.status_code in (401, 403)


def test_login_sets_cookies(api_client, user, settings):
    """
    Uses existing fixtures:
      - api_client (repo fixture, OK for login)
      - user (repo fixture)
    """
    user.set_password("Pass@12345")
    user.save(update_fields=["password"])

    username_field = user.USERNAME_FIELD  # "username" or "email" depending on your User model
    payload = {username_field: getattr(user, username_field), "password": "Pass@12345"}

    res = api_client.post("/api/auth/login/", payload, format="json")
    assert res.status_code == 200

    access_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE", "hm_access")
    refresh_cookie = settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "hm_refresh")

    assert access_cookie in res.cookies
    assert refresh_cookie in res.cookies


def test_me_returns_memberships(api_client, user):
    """
    Here it’s fine to use api_client because we explicitly authenticate.
    """
    api_client.force_authenticate(user=user)
    res = api_client.get("/api/me/")
    assert res.status_code == 200

    body = res.json()
    assert "user" in body
    assert body["user"]["id"] == user.id
    assert "memberships" in body


def test_scope_headers_block_non_member(user, other_tenant, other_facility):
    """
    Must NOT use force_authenticate because it bypasses authentication classes.
    Use a real JWT so our CookieOrHeaderJWTAuthentication runs and enforces scope.
    """
    client = APIClient()

    # Ensure non-membership: delete any membership rows for this user+facility
    Membership, facility_field, mode, user_field = _resolve_membership_model()
    filters = {f"{facility_field}_id": other_facility.id}
    if mode == "direct":
        filters[f"{user_field}_id"] = user.id
    else:
        profile_user_field = mode.split(":", 1)[1]
        filters[f"{user_field}__{profile_user_field}_id"] = user.id
    Membership.objects.filter(**filters).delete()

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    # ✅ Use the standardized scope headers
    res = client.get(
        "/api/me/",
        **{
            "HTTP_X_TENANT_ID": str(other_tenant.id),
            "HTTP_X_FACILITY_ID": str(other_facility.id),
        },
    )
    assert res.status_code == 403
