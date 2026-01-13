# backend/hm_core/api/urls.py
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from hm_core.alerts.api.views import AlertViewSet, NotificationViewSet
from hm_core.billing.api.views import BillableEventViewSet, InvoicePaymentsView, InvoiceViewSet
from hm_core.clinical_docs.api.views import (
    AmendView,
    CreateDraftView,
    FinalizeView,
    LatestDocumentsView,
)
from hm_core.encounters.api.views import EncounterViewSet
from hm_core.iam.api.auth import LoginView, LogoutView, RefreshView
from hm_core.iam.api.me import MeView
from hm_core.lab.api.views import LabResultViewSet, LabSampleViewSet
from hm_core.orders.api.views import OrderViewSet
from hm_core.patients.views import PatientViewSet
from hm_core.tasks.api.views import TaskViewSet
from hm_core.facilities.api.views import FacilityViewSet
from hm_core.tenants.api.views import TenantViewSet
from hm_core.audit.api.views import AuditEventViewSet

router = DefaultRouter()

# ViewSet-backed modules (centralized)
router.register(r"patients", PatientViewSet, basename="patients")
router.register(r"tasks", TaskViewSet, basename="tasks")
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"lab/samples", LabSampleViewSet, basename="lab-samples")
router.register(r"lab/results", LabResultViewSet, basename="lab-results")
router.register(r"billing/events", BillableEventViewSet, basename="billing-events")
router.register(r"billing/invoices", InvoiceViewSet, basename="billing-invoices")
router.register(r"facilities", FacilityViewSet, basename="facilities")
router.register(r"tenants", TenantViewSet, basename="tenants")
router.register(r"audit/events", AuditEventViewSet, basename="audit-events")




# ✅ Encounters (moved from hm_core.encounters.api.urls)
router.register(r"encounters", EncounterViewSet, basename="encounter")

# ✅ Alerts + Notifications (moved from hm_core.alerts.urls)
router.register(r"alerts", AlertViewSet, basename="alerts")
router.register(r"notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    # 🔐 Auth + /me (centralized, no hm_core.iam.urls include)
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),

    # ✅ Clinical docs (moved from hm_core.clinical_docs.api.urls)
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
    
    path(
    "billing/invoices/<uuid:invoice_id>/payments/",
    InvoicePaymentsView.as_view(),
    name="billing-invoice-payments",
    ),


    # Router URLs last (so explicit paths win if ever overlapping)
    *router.urls,
]
