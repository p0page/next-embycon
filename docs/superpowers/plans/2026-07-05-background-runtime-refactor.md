# Background Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Next EmbyCon background service work behind runtime state, scheduling, and optional-feature policy so playback stays stable without sacrificing core UX features.

**Architecture:** Add small policy modules under `resources/lib`, then migrate `service.py`, websocket handling, capabilities posting, and library refresh into those policies. Keep playback URL and media source behavior stable, and preserve existing production defaults.

**Tech Stack:** Kodi Python addon, Python standard library, existing `unittest` suite, PowerShell packaging workflow.

---

## File Structure

- Create `plugin.video.nextembycon/resources/lib/runtime_state.py`
  - Holds immutable runtime snapshots and grace-period policy helpers.
- Create `plugin.video.nextembycon/resources/lib/background_scheduler.py`
  - Holds task records, interval checks, coalescing, deferral, and backoff.
- Create `plugin.video.nextembycon/resources/lib/optional_features.py`
  - Holds optional endpoint TTL state backed by Kodi addon settings where practical.
- Modify `plugin.video.nextembycon/service.py`
  - Replace direct scattered interval logic with scheduled tasks while preserving monitor startup/shutdown.
- Modify `plugin.video.nextembycon/resources/lib/downloadutils.py`
  - Route capabilities through optional feature policy and keep optional failures quiet.
- Modify `plugin.video.nextembycon/resources/lib/websocket_client.py`
  - Route unsupported websocket detection through optional feature policy.
- Modify `plugin.video.nextembycon/resources/lib/library_change_monitor.py`
  - Keep event detection, defer execution through scheduler-friendly checks.
- Modify `plugin.video.nextembycon/addon.xml`
  - Bump version after implementation.
- Modify tests in `tests/test_playback_url.py`, plus add focused tests if the file grows too large.

## Task 1: Runtime State

**Files:**
- Create: `plugin.video.nextembycon/resources/lib/runtime_state.py`
- Test: `tests/test_playback_url.py`

- [ ] **Step 1: Write failing tests**

Add tests that construct runtime snapshots without Kodi:

```python
def test_runtime_state_blocks_background_while_playing(self):
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
```

Also test idle state, startup grace, and recent playback stop grace.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: import failure for `resources.lib.runtime_state`.

- [ ] **Step 3: Implement runtime state**

Create a dataclass with `is_playback_active`, `is_user_changed`, `startup_age`, and `can_run_background` properties. Default grace values: startup 10 seconds, playback stop 15 seconds.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: runtime state tests pass.

## Task 2: Background Scheduler

**Files:**
- Create: `plugin.video.nextembycon/resources/lib/background_scheduler.py`
- Test: `tests/test_playback_url.py`

- [ ] **Step 1: Write failing tests**

Add tests for task interval, deferral during playback, pending coalescing, and failure backoff:

```python
def test_scheduler_defers_background_task_while_playing(self):
    from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask
    from resources.lib.runtime_state import RuntimeState

    calls = []
    scheduler = BackgroundScheduler()
    scheduler.add_task(ScheduledTask(name="refresh", interval=30, run=lambda state: calls.append(state.now)))
    scheduler.mark_pending("refresh")

    state = RuntimeState(100.0, True, False, False, "u", "u", 0.0, None)
    scheduler.tick(state)

    self.assertEqual(calls, [])
    self.assertTrue(scheduler.is_pending("refresh"))
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: import failure for `resources.lib.background_scheduler`.

- [ ] **Step 3: Implement scheduler**

Implement `ScheduledTask` and `BackgroundScheduler` with:

- `add_task(task)`
- `mark_pending(name)`
- `tick(state)`
- `is_pending(name)`
- task fields: `name`, `interval`, `run`, `allow_during_playback=False`, `allow_during_screensaver=False`, `startup_delay=0`, `failure_backoff=60`

- [ ] **Step 4: Verify**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: scheduler tests pass.

## Task 3: Optional Feature Registry

**Files:**
- Create: `plugin.video.nextembycon/resources/lib/optional_features.py`
- Modify: `plugin.video.nextembycon/resources/lib/downloadutils.py`
- Modify: `plugin.video.nextembycon/resources/lib/websocket_client.py`
- Test: `tests/test_playback_url.py`

- [ ] **Step 1: Write failing tests**

Add tests for memory-backed unsupported TTL:

```python
def test_optional_feature_registry_skips_until_ttl_expires(self):
    from resources.lib.optional_features import OptionalFeatureRegistry

    registry = OptionalFeatureRegistry(now=lambda: 100.0)
    registry.mark_unsupported("websocket", ttl_seconds=60)

    self.assertFalse(registry.is_supported("websocket"))
    registry._now = lambda: 161.0
    self.assertTrue(registry.is_supported("websocket"))
```

Also test capabilities uses `download_url(... suppress=True, log_http_errors=False)` and skips when unsupported.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: import failure for `resources.lib.optional_features`.

- [ ] **Step 3: Implement optional feature registry**

Implement in-memory TTL first. Add setting-backed persistence only if it can be done without fragile Kodi profile assumptions in tests.

- [ ] **Step 4: Integrate capabilities and websocket**

Update `post_capabilities` to skip when `capabilities` is unsupported. Update websocket 404 handler to mark `websocket` unsupported and stop reconnecting.

- [ ] **Step 5: Verify**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: optional feature tests pass, existing websocket/capabilities tests still pass.

## Task 4: Service Scheduler Integration

**Files:**
- Modify: `plugin.video.nextembycon/service.py`
- Modify: `plugin.video.nextembycon/resources/lib/library_change_monitor.py`
- Test: `tests/test_playback_url.py`

- [ ] **Step 1: Write failing helper tests**

Extract pure helpers if needed and test that:

- random movies do not run while playing
- background images do not run while playing or during startup grace
- library refresh remains pending while playing and runs when idle
- progress updates still run while playing

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: helper import or assertion failure.

- [ ] **Step 3: Implement integration**

Keep monitor startup/shutdown in `service.py`. Register scheduler tasks for random movies, background images, user window values, and library changes. Leave playback progress outside scheduler or mark it `allow_during_playback=True`.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m unittest tests.test_playback_url
```

Expected: integration helper tests pass.

## Task 5: Version, Packaging, Kodi Validation

**Files:**
- Modify: `plugin.video.nextembycon/addon.xml`
- Modify: `tests/test_addon_metadata.py`

- [ ] **Step 1: Bump version**

Bump from `0.1.2` to `0.2.0` because this is a background runtime architecture change.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m unittest discover tests
python -m compileall -q plugin.video.nextembycon tests
python scripts/check_strings.py
python scripts/package_addon.py
```

Expected: unit tests pass, compile succeeds, string checker has no missing definitions, package builds.

- [ ] **Step 3: Copy package**

Copy the generated zip to:

```text
F:\Movie
```

- [ ] **Step 4: Kodi smoke validation**

Use installed Kodi to validate addon startup against the configured Emby server. Confirm log evidence for:

- addon installed and service started
- auth succeeds
- optional capabilities/websocket failures do not produce user-facing error loops
- no websocket reconnect storm
- no settings parse error
- Kodi remains responsive during idle service runtime

## Self-Review

- The plan covers all design requirements: runtime state, scheduler, optional feature TTL, service integration, production quietness, package validation.
- No menu redesign or transcoding change is included.
- Each task has a failing-test step before implementation.
- The version bump is explicit because this is no longer a small patch.
