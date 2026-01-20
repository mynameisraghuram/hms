# backend/hm_core/common/spectacular_hooks.py
from __future__ import annotations


def preprocess_exclude_legacy_api(endpoints):
    """
    Your ROOT_URLCONF includes both:
      /api/v1/  (primary)
      /api/     (legacy alias)

    drf-spectacular will include BOTH by default, causing:
      - duplicate paths
      - operationId collisions
      - suffixes like retrieve2, list2, etc.

    This hook removes legacy /api/* endpoints from the schema, while keeping /api/v1/*.
    """
    filtered = []
    for path, path_regex, method, callback in endpoints:
        # paths often start with '/api/...'
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            continue
        filtered.append((path, path_regex, method, callback))
    return filtered
