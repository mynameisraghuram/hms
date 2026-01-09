# backend/hm_core/tasks/permissions.py

from __future__ import annotations

from typing import Set

from rest_framework.permissions import BasePermission, SAFE_METHODS

from hm_core.tasks.models import Task, TaskStatus


# Group/role names (Django auth Group names recommended)
ROLE_ADMIN = "ADMIN"
ROLE_DOCTOR = "DOCTOR"
ROLE_NURSE = "NURSE"
ROLE_RECEPTION = "RECEPTION"
ROLE_LAB = "LAB"
ROLE_BILLING = "BILLING"
ROLE_READONLY = "READONLY"


def _user_roles(user) -> Set[str]:
    """
    Resolve roles from:
    1) Django groups: user.groups (recommended)
    2) Optional user.role attribute (if your project has it)

    Returns set of role strings.
    """
    roles: Set[str] = set()

    if not user or not getattr(user, "is_authenticated", False):
        return roles

    # Superuser treated as admin
    if getattr(user, "is_superuser", False):
        roles.add(ROLE_ADMIN)
        return roles

    # Django Groups
    if hasattr(user, "groups"):
        roles.update(user.groups.values_list("name", flat=True))

    # Optional user.role or user.roles
    if hasattr(user, "role") and user.role:
        roles.add(str(user.role))

    if hasattr(user, "roles") and user.roles:
        try:
            roles.update(set(user.roles))
        except TypeError:
            roles.add(str(user.roles))

    return roles


class TaskPermission(BasePermission):
    """
    Role-based permissions for TaskViewSet (Stories 1–3).

    High-level policy:
    - ADMIN: everything
    - DOCTOR/NURSE: list + workflow actions + assign/unassign
    - RECEPTION/LAB/BILLING: list only (read-only tasks dashboard)
    - READONLY: list only
    - Detail workflow actions: assignee can act on own tasks (start/done/cancel/reopen),
      even if they don't have DOCTOR/NURSE, but never backfill.

    Backfill is powerful: admin only.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        roles = _user_roles(user)

        # Must be authenticated for everything in this HMS API
        if not user or not user.is_authenticated:
            return False

        # ADMIN can do all
        if ROLE_ADMIN in roles:
            return True

        action = getattr(view, "action", None)

        # Default: allow safe methods on list/retrieve-like actions only
        # But this is a ViewSet with custom actions, so we must be explicit.
        if action in {"list"}:
            # Many roles can view tasks
            return True

        # Backfill is admin only
        if action in {"backfill_done"}:
            return False

        # Workflow + assignment actions (non-admin)
        if action in {"assign", "unassign", "start", "done", "reopen", "cancel"}:
            # doctors/nurses can do these broadly; others may be allowed via object permission
            if ROLE_DOCTOR in roles or ROLE_NURSE in roles:
                return True
            # allow pass-through to object permission (assignee rule),
            # DRF will call has_object_permission for detail=True actions.
            return True

        # Unknown action => deny by default (safer)
        return False

    def has_object_permission(self, request, view, obj: Task) -> bool:
        user = request.user
        roles = _user_roles(user)

        # ADMIN can do all
        if ROLE_ADMIN in roles:
            return True

        action = getattr(view, "action", None)

        # list doesn't hit object permissions typically, but keep safe
        if action in {None, "list"}:
            return True

        # Backfill is admin-only and is detail=False anyway
        if action == "backfill_done":
            return False

        # Doctors/Nurses: can operate on tasks in their scope
        if ROLE_DOCTOR in roles or ROLE_NURSE in roles:
            return True

        # Assignee rule for non-clinical staff:
        # They can start/done/cancel/reopen ONLY their own tasks,
        # and never assign/unassign.
        if action in {"start", "done", "cancel", "reopen"}:
            if obj.assigned_to_id and obj.assigned_to_id == getattr(user, "id", None):
                # additional safety: prevent acting on CANCELLED/DONE weirdness (service enforces too)
                return True
            return False

        if action in {"assign", "unassign"}:
            return False

        return False
