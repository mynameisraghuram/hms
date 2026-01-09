# backend/hm_core/common/management/commands/ensure_roles.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


ROLE_GROUPS = ["ADMIN", "DOCTOR", "NURSE", "RECEPTION", "LAB", "BILLING", "READONLY"]


class Command(BaseCommand):
    help = "Ensure default role groups exist (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name in ROLE_GROUPS:
            _, was_created = Group.objects.get_or_create(name=name)
            created += 1 if was_created else 0

        self.stdout.write(self.style.SUCCESS(f"Roles ensured. Newly created: {created}"))
