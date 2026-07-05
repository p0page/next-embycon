# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_STARTUP_GRACE_SECONDS = 10.0
DEFAULT_PLAYBACK_STOP_GRACE_SECONDS = 15.0


@dataclass(frozen=True)
class RuntimeState:
    now: float
    is_playing: bool
    screensaver_active: bool
    abort_requested: bool
    user_id: str
    previous_user_id: str
    service_started_at: float
    last_playback_stopped_at: float | None
    startup_grace_seconds: float = DEFAULT_STARTUP_GRACE_SECONDS
    playback_stop_grace_seconds: float = DEFAULT_PLAYBACK_STOP_GRACE_SECONDS

    @property
    def is_playback_active(self) -> bool:
        return self.is_playing

    @property
    def is_user_changed(self) -> bool:
        return self.user_id != self.previous_user_id

    @property
    def startup_age(self) -> float:
        return max(0.0, self.now - self.service_started_at)

    @property
    def in_startup_grace(self) -> bool:
        return self.startup_age < self.startup_grace_seconds

    @property
    def in_playback_stop_grace(self) -> bool:
        if self.last_playback_stopped_at is None:
            return False
        return (self.now - self.last_playback_stopped_at) < self.playback_stop_grace_seconds

    @property
    def can_run_background(self) -> bool:
        if self.abort_requested:
            return False
        if self.is_playback_active or self.screensaver_active:
            return False
        if self.in_startup_grace or self.in_playback_stop_grace:
            return False
        return True

    @property
    def can_consume_user_change(self) -> bool:
        if self.abort_requested:
            return False
        if not self.is_user_changed:
            return False
        if self.is_playback_active or self.screensaver_active:
            return False
        return True
