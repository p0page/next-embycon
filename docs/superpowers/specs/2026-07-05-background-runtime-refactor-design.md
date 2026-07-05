# Background Runtime Refactor Design

## Goal

Make Next EmbyCon feel stable and smooth on Kodi/Xbox by moving background work behind a clear runtime policy. The plugin should keep the user-facing experience intact while ensuring playback, pause, resume, and source selection are not interrupted by optional background tasks.

## User Experience Principles

- Playback stability wins over background freshness.
- Core features stay: continue watching, favorites, recent lists, posters, backdrops, media source selection, progress reporting, Play Next, and chapter/bookmark support.
- Optional or decorative work can wait: random movie widgets, background image rotation, cache cleanup, library refresh, optional capabilities, and websocket probing.
- Production builds stay quiet. Development timing logs may exist, but they must be disabled by default and must not require Xbox log collection from the user.
- User-visible errors are reserved for user-initiated actions such as login and playback. Background failures should use debug logging and backoff.

## Architecture

The current `service.py` loop owns too many responsibilities directly. The refactor introduces three small units and migrates behavior behind them:

1. `RuntimeState`
   - Reads Kodi playback, screensaver, abort, and user state in one place.
   - Tracks startup time and recent playback stop time.
   - Provides policy-friendly booleans such as `is_playback_active`, `is_idle`, and `can_run_background`.

2. `BackgroundScheduler`
   - Runs named tasks according to interval, priority, and runtime policy.
   - Defers non-critical tasks while playback is active or immediately after playback stops.
   - Coalesces repeated triggers such as library changes.
   - Applies failure backoff so optional tasks do not retry in a tight loop.

3. `OptionalFeatureRegistry`
   - Remembers unsupported optional server features for a bounded TTL.
   - Covers capabilities and websocket discovery first.
   - Keeps unsupported endpoint failures out of user-facing notifications.

`service.py` remains the process entrypoint. It should start monitors, create tasks, tick the scheduler, and shut everything down cleanly. Playback-specific code remains in `play_utils.py`; network mechanics remain in `downloadutils.py`; library change detection remains in `library_change_monitor.py` but delegates timing and coalescing to the scheduler where practical.

## Data Flow

1. Service startup authenticates and starts required monitors.
2. Optional features are checked through `OptionalFeatureRegistry` before probing the server.
3. The main service loop refreshes `RuntimeState` once per tick.
4. Playback progress is queued asynchronously while playback is active.
5. Background tasks only run when their task policy accepts the current `RuntimeState`.
6. Library change events mark a task pending; actual refresh waits until playback-safe idle time.
7. Websocket 404 or capabilities 404 marks the feature unsupported until TTL expiry.

## Error Handling

- User-initiated failures may notify the user.
- Background task failures are logged at debug level unless they indicate a real plugin bug.
- Optional 404 failures are treated as unsupported capabilities, not connection failures.
- Repeated failures apply backoff and do not trigger login flow or token clearing.

## Testing

The implementation must add unit tests for:

- Runtime state policy during playing, paused/screensaver, idle, startup, and recent stop grace periods.
- Scheduler task execution, deferral, coalescing, and backoff.
- Optional feature TTL behavior for capabilities and websocket.
- Service-level behavior through pure helper functions where direct Kodi integration is hard.
- Existing playback URL, media source sorting, package structure, and metadata tests must continue to pass.

Kodi validation remains required before producing a zip:

- Launch Kodi with a clean or controlled profile.
- Install/copy the addon.
- Configure the known Emby server.
- Let service run long enough to observe startup, optional endpoint handling, and idle background tasks.
- Confirm no Next EmbyCon user-facing error loop, no websocket reconnect storm, no settings parse error, and no install structure problem.

## Scope

In scope:

- Background runtime architecture.
- Optional endpoint backoff.
- Playback-safe scheduling.
- Development-only timing hooks if useful for local validation.
- Version bump, package, and copy to `F:\Movie`.

Out of scope for this refactor:

- Full menu redesign.
- Transcoding support changes.
- Replacing Kodi player behavior.
- Removing core UX features for performance.
