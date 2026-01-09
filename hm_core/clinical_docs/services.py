# backend/hm_core/clinical_docs/services.py
"""
Compatibility shim.

Phase-1 ClinicalDocument lifecycle is implemented in:
- hm_core.clinical_docs.services.lifecycle
- hm_core.clinical_docs.services.idempotency
- hm_core.clinical_docs.services.read_models

This module stays only to avoid breaking older imports.
"""

from hm_core.clinical_docs.services.lifecycle import (  # noqa: F401
    amend,
    create_draft,
    finalize,
)

from hm_core.clinical_docs.services.idempotency import (  # noqa: F401
    get_key_from_request,
    normalize_idempotency_key,
)

from hm_core.clinical_docs.services.read_models import (  # noqa: F401
    DEFAULT_LATEST_STATUSES,
    latest_document_for_template,
    latest_documents_per_template_for_encounter,
)
