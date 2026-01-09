import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_backfill_is_missing_only(capsys):
    """
    Run backfill twice. The second run must create 0 events.
    We assert using command output to avoid coupling to internal counters.
    """

    # 1st run: may create >0 OR 0 depending on what signals already emitted
    call_command("backfill_encounter_events")
    out1 = capsys.readouterr().out

    # 2nd run: must be 0 (strict)
    call_command("backfill_encounter_events")
    out2 = capsys.readouterr().out

    assert "Events created:" in out2, f"Unexpected output:\n{out2}"
    assert "Events created: 0" in out2, f"Backfill is not missing-only.\nSecond run output:\n{out2}\nFirst run output:\n{out1}"
