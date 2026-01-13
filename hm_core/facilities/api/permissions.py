from __future__ import annotations

from hm_core.common.permissions import BaseRolePermission, ROLE_ADMIN, ROLE_READONLY, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION


class FacilityPermission(BaseRolePermission):
    """
    Facilities are tenant-level objects, but scope middleware still requires a facility header.
    Practical policy:
      - read: most clinical roles can read
      - write: ADMIN only
    """
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_READONLY},
        "create": {ROLE_ADMIN},
        "update": {ROLE_ADMIN},
        "partial_update": {ROLE_ADMIN},
        "destroy": {ROLE_ADMIN},
    }
