# hm_core/encounters/signals/task_events.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

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


def _emit_task_event(*, task: Task, code: str, title: str, ts):
    if not ts:
        return

    event_key = f"{code}:{task.id}"

    EncounterEvent.objects.get_or_create(
        tenant_id=task.tenant_id,
        facility_id=task.facility_id,
        encounter_id=task.encounter_id,
        event_key=event_key,
        defaults={
            "type": "EVENT",
            "code": code,
            "title": title,
            "timestamp": ts,
            "meta": {
                "task_id": str(task.id),
                "task_code": task.code,
                "task_title": task.title,
                "status": task.status,
            },
        },
    )


@receiver(post_save, sender=Task)
def task_post_save(sender, instance: Task, created: bool, **kwargs):
    if created:
        _emit_task_event(
            task=instance,
            code="TASK_CREATED",
            title="Task created",
            ts=getattr(instance, "created_at", None),
        )
        return

    prev = getattr(instance, "_pre_save_snapshot", None)
    if not prev:
        return

    prev_completed = getattr(prev, "completed_at", None)
    new_completed = getattr(instance, "completed_at", None)

    if prev_completed is None and new_completed is not None:
        _emit_task_event(
            task=instance,
            code="TASK_DONE",
            title="Task completed",
            ts=new_completed,
        )
