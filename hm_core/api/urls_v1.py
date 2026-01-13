from django.urls import include, path

urlpatterns = [
    # only the versioned API
    path("v1/", include("hm_core.api.urls")),
]
