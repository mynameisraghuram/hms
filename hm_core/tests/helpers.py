# hm_core/tests/helpers.py

def scoped(tenant, facility):
    return {
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_X_FACILITY_ID": str(facility.id),
    }
