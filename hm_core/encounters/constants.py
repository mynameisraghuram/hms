# hm_core/encounters/constants.py

class EncounterStatus:
    """
    Minimal status constants used by services.
    Keep strings aligned with Encounter.status values.
    """
    CREATED = "CREATED"
    CHECKED_IN = "CHECKED_IN"
    IN_CONSULT = "IN_CONSULT"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
