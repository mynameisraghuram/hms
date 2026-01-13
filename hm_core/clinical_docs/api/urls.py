# backend/hm_core/clinical_docs/api/urls.py
from __future__ import annotations

from django.urls import path

from hm_core.clinical_docs.api.views import (
    AmendView,
    CreateDraftView,
    FinalizeView,
    LatestDocumentsView,
)

app_name = "clinical_docs"

urlpatterns = [
    path(
        "encounters/<uuid:encounter_id>/documents/draft/",
        CreateDraftView.as_view(),
        name="clinical-doc-create-draft",
    ),
    path(
        "documents/<uuid:document_id>/finalize/",
        FinalizeView.as_view(),
        name="clinical-doc-finalize",
    ),
    path(
        "documents/<uuid:document_id>/amend/",
        AmendView.as_view(),
        name="clinical-doc-amend",
    ),
    path(
        "encounters/<uuid:encounter_id>/documents/latest/",
        LatestDocumentsView.as_view(),
        name="clinical-doc-latest-per-template",
    ),
]
