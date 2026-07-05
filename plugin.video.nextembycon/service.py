# coding=utf-8
# Gnu General Public License - see LICENSE.TXT

import time
import traceback

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib.downloadutils import DownloadUtils
from resources.lib.simple_logging import SimpleLogging
from resources.lib.play_utils import (
    PlaybackMonitorService,
    MonitoringService,
    queue_progress,
)
from resources.lib.kodi_utils import HomeWindow
from resources.lib.widgets import set_background_image, set_random_movies
from resources.lib.websocket_client import WebSocketClient
from resources.lib.menu_functions import set_library_window_values
from resources.lib.context_monitor import ContextMonitor
from resources.lib.server_detect import check_server
from resources.lib.library_change_monitor import LibraryChangeMonitor
from resources.lib.tracking import set_timing_enabled
from resources.lib.image_server import HttpImageServerThread
from resources.lib.playnext import PlayNextService
from resources.lib.chapter_dialog import ChapterDialogMonitor
from resources.lib.background_scheduler import BackgroundScheduler, ScheduledTask
from resources.lib.runtime_state import RuntimeState

settings = xbmcaddon.Addon()

log_timing_data = settings.getSetting("log_timing") == "true"
if log_timing_data:
    set_timing_enabled(True)

# clear user and token when logging in
home_window = HomeWindow()
home_window.clear_property("userid")
home_window.clear_property("AccessToken")
home_window.clear_property("Params")

log = SimpleLogging("service")
kodi_monitor = xbmc.Monitor()

# wait for 10 seconds for the Kodi splash screen to close
i = 0
while not kodi_monitor.abortRequested():
    if i == 100 or not xbmc.getCondVisibility("Window.IsVisible(startup)"):
        break
    i += 1
    xbmc.sleep(100)

# notify of debug logging
enable_logging = settings.getSetting("log_debug") == "true"
if enable_logging:
    xbmcgui.Dialog().notification(
        settings.getAddonInfo("name"),
        "Debug logging enabled!",
        time=3000,
        icon=xbmcgui.NOTIFICATION_WARNING,
    )

# make sure we have a server before starting the service
du = DownloadUtils()
while not kodi_monitor.abortRequested():
    server = du.get_server()
    if server is not None:
        break
    kodi_monitor.waitForAbort(5)

if kodi_monitor.abortRequested():
    log.debug("Abort requested before service started")
    exit(0)

log.debug("Service starting up")

check_server()

download_utils = DownloadUtils()

# auth the service
try:
    download_utils.authenticate()
    download_utils.get_user_id()
except Exception as error:
    log.error("Error with initial service auth: {0}", error)

image_server = HttpImageServerThread()
image_server.start()

# set up all the services
play_monitor_service: PlaybackMonitorService = PlaybackMonitorService()
monitor_service: MonitoringService = MonitoringService(play_monitor_service)

home_window = HomeWindow()
service_started_at = time.time()
last_progress_update = service_started_at
last_playback_stopped_at = None
was_playing = False
skin_checked = False
skin_check_delay = 20
user_last_changed = service_started_at

# start the library update monitor
library_change_monitor = LibraryChangeMonitor()
library_change_monitor.start()

# start the WebSocket Client running
remote_control = settings.getSetting("websocket_enabled") == "true"
websocket_client = WebSocketClient(library_change_monitor)
if remote_control:
    websocket_client.start()

play_next_service = None
play_next_trigger_time = int(settings.getSetting("play_next_trigger_time"))
if play_next_trigger_time > 0:
    play_next_service = PlayNextService(play_monitor_service)
    play_next_service.start()

# Start the context menu monitor
context_monitor = None
context_menu = settings.getSetting("override_contextmenu") == "true"
if context_menu:
    context_monitor = ContextMonitor()
    context_monitor.start()

# Start the bookmark/chapter monitor
chapter_dialog_monitor = None
emby_bookmarks = settings.getSetting("override_bookmarks") == "true"
if emby_bookmarks:
    chapter_dialog_monitor = ChapterDialogMonitor()
    chapter_dialog_monitor.start()

background_interval = int(settings.getSetting("background_interval"))
random_movie_list_interval = int(settings.getSetting("random_movie_refresh_interval"))
random_movie_list_interval = random_movie_list_interval * 60

prev_user_id = home_window.get_property("userid")

background_scheduler = BackgroundScheduler()
background_refresh_flags = {"user_changed": False}


def run_background_refresh(state: RuntimeState) -> None:
    user_changed = background_refresh_flags["user_changed"] or state.is_user_changed
    set_library_window_values(user_changed)
    set_background_image(user_changed)
    if user_changed:
        background_refresh_flags["user_changed"] = False

background_scheduler.add_task(
    ScheduledTask(
        name="random_movies",
        interval=float(random_movie_list_interval),
        run=lambda state: set_random_movies(),
        startup_delay=15.0,
        failure_backoff=60.0,
    )
)

background_scheduler.add_task(
    ScheduledTask(
        name="background_image",
        interval=float(background_interval),
        run=run_background_refresh,
        startup_delay=15.0,
        failure_backoff=60.0,
    )
)

background_scheduler.add_task(
    ScheduledTask(
        name="screensaver_background_image",
        interval=float(background_interval),
        run=lambda state: set_background_image(False),
        allow_during_screensaver=True,
        should_run=lambda state: state.screensaver_active,
        startup_delay=15.0,
        failure_backoff=60.0,
    )
)

while not kodi_monitor.abortRequested():
    try:
        now = time.time()
        is_playing = xbmc.Player().isPlaying()
        if was_playing and not is_playing:
            last_playback_stopped_at = now
        was_playing = is_playing

        screen_saver_active = xbmc.getCondVisibility("System.ScreenSaverActive")
        current_user_id = home_window.get_property("userid")
        runtime_state = RuntimeState(
            now=now,
            is_playing=is_playing,
            screensaver_active=screen_saver_active,
            abort_requested=kodi_monitor.abortRequested(),
            user_id=current_user_id,
            previous_user_id=prev_user_id,
            service_started_at=service_started_at,
            last_playback_stopped_at=last_playback_stopped_at,
        )

        if runtime_state.is_playback_active:
            # if playing every 10 seconds updated the server with progress
            if (now - last_progress_update) > 10:
                last_progress_update = now
                queue_progress(play_monitor_service)

        else:
            if runtime_state.can_consume_user_change:
                log.debug("user_change_detected")
                prev_user_id = current_user_id
                user_last_changed = now
                background_refresh_flags["user_changed"] = True
                background_scheduler.mark_pending("random_movies")
                background_scheduler.mark_pending("background_image")

                if remote_control:
                    websocket_client.stop_client()
                    websocket_client = WebSocketClient(library_change_monitor)
                    websocket_client.start()

            background_scheduler.tick(runtime_state)

            if (
                skin_checked is False
                and (now - user_last_changed) > skin_check_delay
                and home_window.get_property("userid")
            ):
                skin_checked = True
                # check_skin_installed()

    except Exception as error:
        log.error("Exception in Playback Monitor: {0}", error)
        log.error("{0}", traceback.format_exc())

    kodi_monitor.waitForAbort(1)

image_server.stop()

# call stop on the library update monitor
library_change_monitor.stop()

# stop the play next episdoe service
if play_next_service:
    play_next_service.stop_service()

# call stop on the context menu monitor
if context_monitor:
    context_monitor.stop_monitor()

if chapter_dialog_monitor:
    chapter_dialog_monitor.stop_monitor()

# stop the WebSocket Client
websocket_client.stop_client()

# clear user and token when loggin off
home_window.clear_property("userid")
home_window.clear_property("AccessToken")
home_window.clear_property("userimage")

log.debug("Service shutting down")
