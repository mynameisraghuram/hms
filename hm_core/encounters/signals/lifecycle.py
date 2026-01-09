# hm_core/encounters/signals/lifecycle.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from hm_core.encounters.models import Encounter, EncounterEvent


@receiver(pre_save, sender=Encounter)
def encounter_pre_save(sender, instance: Encounter, **kwargs):
    if not instance.pk:
        instance._pre_save_snapshot = None
        return
    try:
        instance._pre_save_snapshot = Encounter.objects.get(pk=instance.pk)
    except Encounter.DoesNotExist:
        instance._pre_save_snapshot = None


def _emit_encounter_event(*, encounter: Encounter, code: str, title: str, ts):
    if not ts:
        return

    # event_key makes it idempotent
    event_key = f"{code}:{encounter.id}"

    EncounterEvent.objects.get_or_create(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        event_key=event_key,
        defaults={
            "type": "EVENT",
            "code": code,
            "title": title,
            "timestamp": ts,   # IMPORTANT: you renamed occurred_at -> timestamp
            "meta": {"status": encounter.status},
        },
    )


@receiver(post_save, sender=Encounter)
def encounter_post_save(sender, instance: Encounter, created: bool, **kwargs):
    if created:
        _emit_encounter_event(
            encounter=instance,
            code="ENCOUNTER_CREATED",
            title="Encounter created",
            ts=instance.created_at,
        )
        return

    prev = getattr(instance, "_pre_save_snapshot", None)
    if not prev:
        return

    def flipped(prev_val, new_val):
        return (prev_val is None) and (new_val is not None)

    if flipped(getattr(prev, "checked_in_at", None), getattr(instance, "checked_in_at", None)):
        _emit_encounter_event(
            encounter=instance,
            code="CHECKED_IN",
            title="Patient checked in",
            ts=instance.checked_in_at,
        )

    if flipped(getattr(prev, "consult_started_at", None), getattr(instance, "consult_started_at", None)):
        _emit_encounter_event(
            encounter=instance,
            code="CONSULT_STARTED",
            title="Consultation started",
            ts=instance.consult_started_at,
        )

    if flipped(getattr(prev, "closed_at", None), getattr(instance, "closed_at", None)):
        _emit_encounter_event(
            encounter=instance,
            code="CLOSED",
            title="Encounter closed",
            ts=instance.closed_at,
        )
