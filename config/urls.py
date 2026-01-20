# backend/config/urls.py
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.http import JsonResponse

def home(request):
    return JsonResponse(
        {
            "status": "ok",
            "docs": "/api/docs/",
            "schema": "/api/schema/",
            "api_v1": "/api/v1/",
        }
    )


urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # ✅ Primary versioned API (frontend should use this)
    path("api/v1/", include("hm_core.api.urls")),

    # ✅ Backwards-compatible alias (tests + legacy clients)
    # Provides: /api/me/, /api/auth/login/, etc.
    # Keep AFTER schema/docs so those explicit routes win.
    path("api/", include("hm_core.api.urls")),

   
]
