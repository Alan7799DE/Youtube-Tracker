from verifier.jobs.tick import run_tick, TickSteps


def test_tick_runs_all_steps_in_order(mocker):
    calls = []
    steps = TickSteps(
        resolve_unresolved_channels=lambda: calls.append("resolve"),
        retry_due_transcripts=lambda: calls.append("transcripts"),
        renew_expiring_leases=lambda: calls.append("leases"),
        fail_overdue_channels=lambda: calls.append("deadlines"),
    )
    run_tick(steps)
    assert calls == ["resolve", "transcripts", "leases", "deadlines"]


def test_tick_continues_if_one_step_fails(mocker):
    calls = []
    def boom():
        raise RuntimeError("falló transcripts")
    steps = TickSteps(
        resolve_unresolved_channels=lambda: calls.append("resolve"),
        retry_due_transcripts=boom,
        renew_expiring_leases=lambda: calls.append("leases"),
        fail_overdue_channels=lambda: calls.append("deadlines"),
    )
    # un paso que falla no debe abortar el resto del tick
    run_tick(steps)
    assert calls == ["resolve", "leases", "deadlines"]
