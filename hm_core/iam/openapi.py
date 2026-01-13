from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieOrHeaderJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "hm_core.iam.auth.CookieOrHeaderJWTAuthentication"
    name = "BearerOrCookieJWT"

    def get_security_definition(self, auto_schema):
        # We document it as Bearer JWT (even though you also accept cookies),
        # because Swagger "Authorize" works great with Bearer.
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Send access token via `Authorization: Bearer <token>` "
                "or via HttpOnly cookie (hm_access)."
            ),
        }
