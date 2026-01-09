# hm_core/encounters/signals/doc_events.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now

from hm_core.clinical_docs.models import EncounterDocument
from hm_core.encounters.models import EncounterEvent


@receiver(post_save, sender=EncounterDocument)
def doc_post_save(sender, instance: EncounterDocument, created: bool, **kwargs):
    if not created:
        return

    ts = getattr(instance, "authored_at", None) or getattr(instance, "created_at", None) or now()
    event_key = f"DOC_AUTHORED:{instance.id}"

    EncounterEvent.objects.get_or_create(
        tenant_id=instance.tenant_id,
        facility_id=instance.facility_id,
        encounter_id=instance.encounter_id,
        event_key=event_key,
        defaults={
            "type": "EVENT",
            "code": "DOC_AUTHORED",
            "title": "Document authored",
            "timestamp": ts,
            "meta": {
                "document_id": str(instance.id),
                "kind": instance.kind,
                "authored_by_id": getattr(instance, "authored_by_id", None),
            },
        },
    )
