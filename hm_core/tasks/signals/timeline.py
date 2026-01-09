# backend/hm_core/tasks/signals/timeline.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.timezone import now

from hm_core.tasks.models import Task
from hm_core.encounters.models import EncounterEvent


@receiver(pre_save, sender=Task)
def task_pre_save(sender, instance: Task, **kwargs):
    if not instance.pk:
        instance._pre_save_snapshot = None
        return
    try:
        instance._pre_save_snapshot = Task.objects.get(pk=instance.pk)
    except Task.DoesNotExist:
        instance._pre_save_snapshot = None


@receiver(post_save, sender=Task)
def task_post_save(sender, instance: Task, created: bool, **kwargs):

    def emit(code, title, key, ts, meta):
        EncounterEvent.objects.get_or_create(
            tenant_id=instance.tenant_id,
            facility_id=instance.facility_id,
            encounter_id=instance.encounter_id,
            event_key=key,
            defaults={
                "type": "EVENT",
                "code": code,
                "title": title,
                "timestamp": ts or now(),
                "meta": meta,
            },
        )

    if created:
        emit(
            "TASK_CREATED",
            "Task created",
            f"TASK_CREATED:{instance.id}",
            instance.created_at,
            {
                "task_id": str(instance.id),
                "task_code": instance.code,
                "status": instance.status,
            },
        )
        return

    prev = getattr(instance, "_pre_save_snapshot", None)
    if prev and prev.completed_at is None and instance.completed_at:
        emit(
            "TASK_DONE",
            "Task completed",
            f"TASK_DONE:{instance.id}",
            instance.completed_at,
            {
                "task_id": str(instance.id),
                "task_code": instance.code,
                "status": instance.status,
            },
        )
