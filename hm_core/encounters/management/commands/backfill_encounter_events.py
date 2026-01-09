
# hm_core/encounters/management/commands/backfill_encounter_events.py
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from hm_core.encounters.models import Encounter, EncounterEvent
from hm_core.tasks.models import Task
from hm_core.clinical_docs.models import EncounterDocument


class Command(BaseCommand):
    help = "Backfill EncounterEvent stream from current state (Encounter/Task/EncounterDocument). Only inserts missing events."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print counts only; do not write.")
        parser.add_argument("--tenant-id", type=str, default=None, help="Optional tenant UUID filter.")
        parser.add_argument("--facility-id", type=str, default=None, help="Optional facility UUID filter.")
        parser.add_argument("--limit", type=int, default=None, help="Optional limit encounters scanned.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        qs = Encounter.objects.all().order_by("created_at")
        if opts["tenant_id"]:
            qs = qs.filter(tenant_id=opts["tenant_id"])
        if opts["facility_id"]:
            qs = qs.filter(facility_id=opts["facility_id"])
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        examined = 0
        created_count = 0

        def upsert_event(*, tenant_id, facility_id, encounter_id, event_key, code, title, ts, meta):
            nonlocal created_count
            if ts is None:
                ts = now()
            if meta is None:
                meta = {}

            if dry:
                # We still count "would create" by checking existence cheaply
                exists = EncounterEvent.objects.filter(
                    tenant_id=tenant_id,
                    facility_id=facility_id,
                    encounter_id=encounter_id,
                    event_key=event_key,
                ).exists()
                if not exists:
                    created_count += 1
                return

            _, created = EncounterEvent.objects.get_or_create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
                event_key=event_key,
                defaults={
                    "type": "EVENT",
                    "code": code,
                    "title": title,
                    "timestamp": ts,
                    "meta": meta,
                },
            )
            if created:
                created_count += 1

        # Wrap writes in one transaction (dry-run does no writes anyway)
        ctx = transaction.atomic() if not dry else nullcontext()
        with ctx:
            for e in qs:
                examined += 1

                # 1) Encounter lifecycle
                upsert_event(
                    tenant_id=e.tenant_id,
                    facility_id=e.facility_id,
                    encounter_id=e.id,
                    event_key=f"ENCOUNTER_CREATED:{e.id}",
                    code="ENCOUNTER_CREATED",
                    title="Encounter created",
                    ts=e.created_at,
                    meta={"status": e.status},
                )

                if getattr(e, "checked_in_at", None):
                    upsert_event(
                        tenant_id=e.tenant_id,
                        facility_id=e.facility_id,
                        encounter_id=e.id,
                        event_key=f"CHECKED_IN:{e.id}",
                        code="CHECKED_IN",
                        title="Patient checked in",
                        ts=e.checked_in_at,
                        meta={"status": e.status},
                    )

                if getattr(e, "consult_started_at", None):
                    upsert_event(
                        tenant_id=e.tenant_id,
                        facility_id=e.facility_id,
                        encounter_id=e.id,
                        event_key=f"CONSULT_STARTED:{e.id}",
                        code="CONSULT_STARTED",
                        title="Consultation started",
                        ts=e.consult_started_at,
                        meta={"status": e.status},
                    )

                if getattr(e, "closed_at", None):
                    upsert_event(
                        tenant_id=e.tenant_id,
                        facility_id=e.facility_id,
                        encounter_id=e.id,
                        event_key=f"CLOSED:{e.id}",
                        code="CLOSED",
                        title="Encounter closed",
                        ts=e.closed_at,
                        meta={"status": e.status},
                    )

                # 2) Tasks (created + done)
                tasks = Task.objects.filter(
                    tenant_id=e.tenant_id,
                    facility_id=e.facility_id,
                    encounter_id=e.id,
                )
                for t in tasks:
                    upsert_event(
                        tenant_id=t.tenant_id,
                        facility_id=t.facility_id,
                        encounter_id=t.encounter_id,
                        event_key=f"TASK_CREATED:{t.id}",
                        code="TASK_CREATED",
                        title="Task created",
                        ts=getattr(t, "created_at", None) or getattr(t, "updated_at", None) or now(),
                        meta={
                            "task_id": str(t.id),
                            "task_code": t.code,
                            "task_title": t.title,
                            "status": t.status,
                        },
                    )
                    if getattr(t, "completed_at", None):
                        upsert_event(
                            tenant_id=t.tenant_id,
                            facility_id=t.facility_id,
                            encounter_id=t.encounter_id,
                            event_key=f"TASK_DONE:{t.id}",
                            code="TASK_DONE",
                            title="Task completed",
                            ts=t.completed_at,
                            meta={
                                "task_id": str(t.id),
                                "task_code": t.code,
                                "task_title": t.title,
                                "status": t.status,
                            },
                        )

                # 3) Documents authored
                docs = EncounterDocument.objects.filter(
                    tenant_id=e.tenant_id,
                    facility_id=e.facility_id,
                    encounter_id=e.id,
                )
                for d in docs:
                    ts = getattr(d, "authored_at", None) or getattr(d, "created_at", None) or now()
                    upsert_event(
                        tenant_id=d.tenant_id,
                        facility_id=d.facility_id,
                        encounter_id=d.encounter_id,
                        event_key=f"DOC_AUTHORED:{d.id}",
                        code="DOC_AUTHORED",
                        title="Document authored",
                        ts=ts,
                        meta={
                            "document_id": str(d.id),
                            "kind": d.kind,
                            "authored_by_id": getattr(d, "authored_by_id", None),
                        },
                    )

        if dry:
            self.stdout.write(f"Encounters examined: {examined}")
            self.stdout.write(f"DRY RUN: events that would be created: {created_count}")
        else:
            self.stdout.write(f"Encounters examined: {examined}")
            self.stdout.write(f"Events created: {created_count}")


# local helper (so we don't import contextlib in older snippets)
class nullcontext:
    def __enter__(self):  # noqa
        return None

    def __exit__(self, *exc):  # noqa
        return False
