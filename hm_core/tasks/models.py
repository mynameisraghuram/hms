# backend/hm_core/tasks/models.py
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils.timezone import now as tz_now

from hm_core.common.models import ScopedModel
from hm_core.encounters.models import Encounter


class TaskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    DONE = "DONE", "Done"
    CANCELLED = "CANCELLED", "Cancelled"


class Task(ScopedModel):
    """
    Operational task created by workflows/events/rules.
    """
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="tasks")

    code = models.SlugField(max_length=64, db_index=True)  # e.g. "record-vitals"
    title = models.CharField(max_length=255)

    status = models.CharField(
        max_length=32,
        choices=TaskStatus.choices,
        default=TaskStatus.OPEN,
        db_index=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_tasks",
        null=True,
        blank=True,
    )

    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tasks_task"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "status", "due_at"]),
            models.Index(fields=["tenant_id", "facility_id", "encounter", "status"]),
            models.Index(fields=["tenant_id", "facility_id", "code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "encounter", "code"],
                name="uq_task_code_per_encounter_scope",
            ),
        ]

    @property
    def is_overdue(self) -> bool:
        """
        Overdue if:
        - due_at exists
        - status is actionable (OPEN or IN_PROGRESS)
        - due_at is in the past
        """
        if not self.due_at:
            return False
        if self.status not in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}:
            return False
        return self.due_at < tz_now()

    def save(self, *args, **kwargs):
        """
        Make Task creation idempotent on (tenant_id, facility_id, encounter_id, code).

        Important: when Task.objects.create() hits a unique constraint, it happens inside
        an atomic transaction in tests. Without a savepoint, the transaction becomes
        "broken" and you cannot query. So we use a savepoint.
        """
        force_insert = kwargs.get("force_insert", False)
        using = kwargs.get("using") or "default"

        # Normal updates: keep default behavior
        if not force_insert:
            return super().save(*args, **kwargs)

        # Inserts: protect with a savepoint so IntegrityError doesn't poison the transaction
        try:
            with transaction.atomic(using=using, savepoint=True):
                return super().save(*args, **kwargs)
        except IntegrityError:
            # Upsert behavior only for insert attempts
            existing = Task.objects.get(
                tenant_id=self.tenant_id,
                facility_id=self.facility_id,
                encounter_id=self.encounter_id,
                code=self.code,
            )

            # Update mutable fields
            existing.title = self.title
            existing.status = self.status
            existing.assigned_to_id = self.assigned_to_id
            existing.due_at = self.due_at
            existing.completed_at = self.completed_at
            existing.save(
                using=using,
                update_fields=[
                    "title",
                    "status",
                    "assigned_to",
                    "due_at",
                    "completed_at",
                    "updated_at",
                ],
            )

            self.id = existing.id
            return existing
