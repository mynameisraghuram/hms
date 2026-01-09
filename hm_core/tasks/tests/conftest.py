import uuid
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils.timezone import now


def _uuid():
    return uuid.uuid4()


def get_encounter_model():
    # Most likely "encounters.Encounter"
    return apps.get_model("encounters", "Encounter")


def get_patient_model():
    # If patients app exists. If not, Encounter factory will still try to build minimal.
    try:
        return apps.get_model("patients", "Patient")
    except LookupError:
        return None


def get_event_model():
    """
    We don't assume exact model name. Try common ones used in the project.
    """
    candidates = [
        ("encounters", "EncounterEvent"),
        ("encounters", "Event"),
        ("audit", "AuditEvent"),
    ]
    for app_label, model_name in candidates:
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            continue
    return None


def create_minimal_instance(model_cls, **overrides):
    """
    Generic factory that fills required (non-null, no default) fields.
    This keeps tests resilient even if Encounter has many required fields.
    """
    kwargs = dict(overrides)

    for field in model_cls._meta.fields:
        if field.primary_key:
            continue

        name = field.name

        if name in kwargs:
            continue

        # If nullable or has default, we can skip
        if getattr(field, "null", False):
            continue
        if field.has_default():
            continue

        # Auto fields (created_at etc.) generally have auto_now_add/defaults
        if field.auto_created:
            continue

        internal_type = field.get_internal_type()

        # Handle UUID-like ids
        if internal_type in {"UUIDField"}:
            kwargs[name] = _uuid()
            continue

        # Common scope fields in your codebase
        if name in {"tenant_id", "facility_id"}:
            kwargs[name] = _uuid()
            continue

        if internal_type in {"CharField", "TextField", "SlugField"}:
            kwargs[name] = f"test-{name}"
            continue

        if internal_type in {"IntegerField", "BigIntegerField", "PositiveIntegerField"}:
            kwargs[name] = 1
            continue

        if internal_type in {"BooleanField"}:
            kwargs[name] = False
            continue

        if internal_type in {"DateTimeField"}:
            kwargs[name] = now()
            continue

        # Required ForeignKey: recursively create target
        if internal_type == "ForeignKey":
            rel_model = field.remote_field.model
            rel_obj = create_minimal_instance(rel_model)
            kwargs[name] = rel_obj
            continue

        # Fallback: try None (will fail loudly if truly required)
        kwargs[name] = None

    return model_cls.objects.create(**kwargs)


@pytest.fixture
def tenant_id():
    return _uuid()


@pytest.fixture
def facility_id():
    return _uuid()


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="u1", password="pass")


@pytest.fixture
def user2(db):
    User = get_user_model()
    return User.objects.create_user(username="u2", password="pass")


@pytest.fixture
def encounter(db, tenant_id, facility_id):
    Encounter = get_encounter_model()
    # Try to pass tenant/facility explicitly; rest auto-filled.
    return create_minimal_instance(Encounter, tenant_id=tenant_id, facility_id=facility_id)
