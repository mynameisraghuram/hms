# backend/hm_core/api/urls.py
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hm_core.alerts.api.views import AlertViewSet, NotificationViewSet
from hm_core.audit.api.views import AuditEventViewSet
from hm_core.billing.api.views import BillableEventViewSet, InvoicePaymentsView, InvoiceViewSet
from hm_core.encounters.api.views import EncounterViewSet
from hm_core.facilities.api.views import FacilityViewSet
from hm_core.iam.api.auth import LoginView, LogoutView, RefreshView
from hm_core.iam.api.me import MeView
from hm_core.iam.api.session import SessionBootstrapView
from hm_core.lab.api.views import LabResultViewSet, LabSampleViewSet
from hm_core.orders.api.views import OrderViewSet
from hm_core.patients.api.views import PatientViewSet
from hm_core.tasks.api.views import TaskViewSet
from hm_core.tenants.api.views import TenantViewSet

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

# ✅ Encounters
router.register(r"encounters", EncounterViewSet, basename="encounter")

# ✅ Alerts + Notifications
router.register(r"alerts", AlertViewSet, basename="alerts")
router.register(r"notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    # 🔐 Auth + /me + session bootstrap
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("session/bootstrap/", SessionBootstrapView.as_view(), name="session-bootstrap"),

    # ✅ Clinical docs (namespaced so tests can reverse("clinical_docs:..."))
    path(
        "",
        include(("hm_core.clinical_docs.api.urls", "clinical_docs"), namespace="clinical_docs"),
    ),

    # ✅ Invoice payments (non-ViewSet endpoint)
    path(
        "billing/invoices/<uuid:invoice_id>/payments/",
        InvoicePaymentsView.as_view(),
        name="billing-invoice-payments",
    ),

    # Router URLs last (so explicit paths win if ever overlapping)
    *router.urls,
]
