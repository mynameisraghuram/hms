# backend/hm_core/common/views.py
from rest_framework import viewsets


class ScopedViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that automatically scopes queries to tenant and facility.
    Assumes the model inherits from ScopedModel.
    """

    def get_queryset(self):
        """Filter queryset by tenant and facility from request"""
        if not hasattr(self.request, 'tenant_id') or not hasattr(self.request, 'facility_id'):
            return self.queryset.none()

        return self.queryset.filter(
            tenant_id=self.request.tenant_id,
            facility_id=self.request.facility_id
        )

    def perform_create(self, serializer):
        """Automatically set tenant and facility on create"""
        serializer.save(
            tenant_id=self.request.tenant_id,
            facility_id=self.request.facility_id
        )
