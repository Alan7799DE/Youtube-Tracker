from __future__ import annotations
import logging
from typing import Callable
from pydantic import BaseModel, ConfigDict

log = logging.getLogger("verifier.tick")
Step = Callable[[], None]


class TickSteps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    resolve_unresolved_channels: Step
    retry_due_transcripts: Step
    renew_expiring_leases: Step
    fail_overdue_channels: Step


def run_tick(steps: TickSteps) -> None:
    """Corre cada paso del mantenimiento; si uno falla, loguea y sigue con el resto
    (un error transitorio en una pieza no debe frenar las demás)."""
    for name, step in [
        ("resolve_unresolved_channels", steps.resolve_unresolved_channels),
        ("retry_due_transcripts", steps.retry_due_transcripts),
        ("renew_expiring_leases", steps.renew_expiring_leases),
        ("fail_overdue_channels", steps.fail_overdue_channels),
    ]:
        try:
            step()
        except Exception:  # noqa: BLE001 - se loguea y se sigue
            log.exception("tick: falló el paso %s", name)
