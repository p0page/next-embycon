# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .runtime_state import RuntimeState


@dataclass
class ScheduledTask:
    name: str
    interval: float
    run: Callable[[RuntimeState], None]
    allow_during_playback: bool = False
    allow_during_screensaver: bool = False
    should_run: Callable[[RuntimeState], bool] | None = None
    startup_delay: float = 0.0
    failure_backoff: float = 60.0


@dataclass
class _TaskState:
    task: ScheduledTask
    last_run_at: float | None = None
    pending: bool = False
    next_allowed_at: float = 0.0


class BackgroundScheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, _TaskState] = {}

    def add_task(self, task: ScheduledTask) -> None:
        self._tasks[task.name] = _TaskState(task=task)

    def mark_pending(self, name: str) -> None:
        self._tasks[name].pending = True

    def is_pending(self, name: str) -> bool:
        return self._tasks[name].pending

    def tick(self, state: RuntimeState) -> None:
        for task_state in list(self._tasks.values()):
            if not self._can_run(task_state, state):
                continue
            if not self._is_due(task_state, state):
                continue

            try:
                task_state.task.run(state)
            except Exception:
                task_state.next_allowed_at = state.now + task_state.task.failure_backoff
                task_state.pending = True
                continue

            task_state.last_run_at = state.now
            task_state.pending = False
            task_state.next_allowed_at = 0.0

    def _can_run(self, task_state: _TaskState, state: RuntimeState) -> bool:
        task = task_state.task
        if state.abort_requested:
            return False
        if state.now < task_state.next_allowed_at:
            return False
        if state.startup_age < task.startup_delay:
            return False
        if state.is_playback_active and not task.allow_during_playback:
            return False
        if state.in_playback_stop_grace and not task.allow_during_playback:
            return False
        if state.screensaver_active and not task.allow_during_screensaver:
            return False
        if task.should_run is not None and not task.should_run(state):
            return False
        return True

    def _is_due(self, task_state: _TaskState, state: RuntimeState) -> bool:
        if task_state.pending:
            return True

        task = task_state.task
        if task.interval <= 0:
            return False
        if task_state.last_run_at is None:
            return state.startup_age >= task.startup_delay
        return (state.now - task_state.last_run_at) >= task.interval
