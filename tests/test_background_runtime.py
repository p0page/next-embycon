from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin.video.nextembycon"))


class RuntimeStateTests(unittest.TestCase):
    def test_runtime_state_blocks_background_while_playing(self) -> None:
        from resources.lib.runtime_state import RuntimeState

        state = RuntimeState(
            now=100.0,
            is_playing=True,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=None,
        )

        self.assertTrue(state.is_playback_active)
        self.assertFalse(state.can_run_background)

    def test_runtime_state_allows_background_when_idle_after_grace_periods(self) -> None:
        from resources.lib.runtime_state import RuntimeState

        state = RuntimeState(
            now=100.0,
            is_playing=False,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=50.0,
        )

        self.assertFalse(state.is_playback_active)
        self.assertTrue(state.can_run_background)

    def test_runtime_state_blocks_background_during_startup_grace(self) -> None:
        from resources.lib.runtime_state import RuntimeState

        state = RuntimeState(
            now=5.0,
            is_playing=False,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=None,
        )

        self.assertTrue(state.in_startup_grace)
        self.assertFalse(state.can_run_background)

    def test_runtime_state_blocks_background_shortly_after_playback_stops(self) -> None:
        from resources.lib.runtime_state import RuntimeState

        state = RuntimeState(
            now=110.0,
            is_playing=False,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=100.0,
        )

        self.assertTrue(state.in_playback_stop_grace)
        self.assertFalse(state.can_run_background)

    def test_runtime_state_does_not_consume_user_change_during_screensaver(self) -> None:
        from resources.lib.runtime_state import RuntimeState

        state = RuntimeState(
            now=100.0,
            is_playing=False,
            screensaver_active=True,
            abort_requested=False,
            user_id="new-user",
            previous_user_id="old-user",
            service_started_at=0.0,
            last_playback_stopped_at=None,
        )

        self.assertTrue(state.is_user_changed)
        self.assertFalse(state.can_consume_user_change)


class BackgroundSchedulerTests(unittest.TestCase):
    def idle_state(self, now: float = 100.0):
        from resources.lib.runtime_state import RuntimeState

        return RuntimeState(
            now=now,
            is_playing=False,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=None,
        )

    def playing_state(self, now: float = 100.0):
        from resources.lib.runtime_state import RuntimeState

        return RuntimeState(
            now=now,
            is_playing=True,
            screensaver_active=False,
            abort_requested=False,
            user_id="user-id",
            previous_user_id="user-id",
            service_started_at=0.0,
            last_playback_stopped_at=None,
        )

    def test_scheduler_defers_background_task_while_playing(self) -> None:
        from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask

        calls: list[float] = []
        scheduler = BackgroundScheduler()
        scheduler.add_task(
            ScheduledTask(
                name="refresh",
                interval=30.0,
                run=lambda state: calls.append(state.now),
            )
        )
        scheduler.mark_pending("refresh")

        scheduler.tick(self.playing_state())

        self.assertEqual(calls, [])
        self.assertTrue(scheduler.is_pending("refresh"))

    def test_scheduler_runs_pending_task_when_idle(self) -> None:
        from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask

        calls: list[float] = []
        scheduler = BackgroundScheduler()
        scheduler.add_task(
            ScheduledTask(
                name="refresh",
                interval=30.0,
                run=lambda state: calls.append(state.now),
            )
        )
        scheduler.mark_pending("refresh")

        scheduler.tick(self.idle_state())

        self.assertEqual(calls, [100.0])
        self.assertFalse(scheduler.is_pending("refresh"))

    def test_scheduler_coalesces_pending_triggers(self) -> None:
        from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask

        calls: list[float] = []
        scheduler = BackgroundScheduler()
        scheduler.add_task(
            ScheduledTask(
                name="library",
                interval=0.0,
                run=lambda state: calls.append(state.now),
            )
        )
        scheduler.mark_pending("library")
        scheduler.mark_pending("library")
        scheduler.mark_pending("library")

        scheduler.tick(self.idle_state())

        self.assertEqual(calls, [100.0])
        self.assertFalse(scheduler.is_pending("library"))

    def test_scheduler_backs_off_failed_pending_task(self) -> None:
        from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask

        calls: list[float] = []

        def fail_once(state) -> None:
            calls.append(state.now)
            raise RuntimeError("temporary")

        scheduler = BackgroundScheduler()
        scheduler.add_task(
            ScheduledTask(
                name="optional",
                interval=0.0,
                run=fail_once,
                failure_backoff=60.0,
            )
        )
        scheduler.mark_pending("optional")

        scheduler.tick(self.idle_state(100.0))
        scheduler.tick(self.idle_state(120.0))

        self.assertEqual(calls, [100.0])
        self.assertTrue(scheduler.is_pending("optional"))

    def test_scheduler_respects_task_predicate(self) -> None:
        from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask

        calls: list[float] = []
        scheduler = BackgroundScheduler()
        scheduler.add_task(
            ScheduledTask(
                name="screensaver-only",
                interval=30.0,
                run=lambda state: calls.append(state.now),
                allow_during_screensaver=True,
                should_run=lambda state: state.screensaver_active,
            )
        )

        scheduler.tick(self.idle_state(100.0))

        self.assertEqual(calls, [])


class OptionalFeatureRegistryTests(unittest.TestCase):
    def test_optional_feature_registry_skips_until_ttl_expires(self) -> None:
        from resources.lib.optional_features import OptionalFeatureRegistry

        registry = OptionalFeatureRegistry(now=lambda: 100.0)
        registry.mark_unsupported("websocket", ttl_seconds=60.0)

        self.assertFalse(registry.is_supported("websocket"))
        registry._now = lambda: 161.0
        self.assertTrue(registry.is_supported("websocket"))

    def test_optional_feature_registry_reports_remaining_retry_delay(self) -> None:
        from resources.lib.optional_features import OptionalFeatureRegistry

        registry = OptionalFeatureRegistry(now=lambda: 100.0)
        registry.mark_unsupported("capabilities", ttl_seconds=60.0)

        self.assertEqual(registry.seconds_until_retry("capabilities"), 60.0)
        registry._now = lambda: 130.0
        self.assertEqual(registry.seconds_until_retry("capabilities"), 30.0)
        registry._now = lambda: 161.0
        self.assertEqual(registry.seconds_until_retry("capabilities"), 0.0)

    def test_optional_feature_registry_scopes_unsupported_state(self) -> None:
        from resources.lib.optional_features import OptionalFeatureRegistry

        registry = OptionalFeatureRegistry(now=lambda: 100.0)
        registry.mark_unsupported(
            "websocket", ttl_seconds=60.0, scope="server-a|user-a"
        )

        self.assertFalse(registry.is_supported("websocket", scope="server-a|user-a"))
        self.assertTrue(registry.is_supported("websocket", scope="server-b|user-a"))


if __name__ == "__main__":
    unittest.main()
