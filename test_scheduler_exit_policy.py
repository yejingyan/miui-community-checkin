from __future__ import annotations

import miui_daily_orchestrator as orch


def test_scheduler_exit_success_only_when_checkin_and_status_success() -> None:
    assert orch.scheduler_exit(0, 0) == 0


def test_scheduler_exit_keeps_need_human_when_h5_pending() -> None:
    assert orch.scheduler_exit(3, 2) == 2
    assert orch.scheduler_exit(2, 2) == 2
