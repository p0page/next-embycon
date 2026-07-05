import threading
import time

import xbmc

from .simple_logging import SimpleLogging
from .widgets import check_for_new_content
from .tracking import timer

log = SimpleLogging(__name__)


class LibraryChangeMonitor(threading.Thread):
    last_library_change_check: float = 0.0
    library_check_triggered: bool = False
    exit_now: bool = False
    time_between_checks: int = 3
    minimum_update_interval: int = 30

    def __init__(self) -> None:
        threading.Thread.__init__(self)

    def stop(self) -> None:
        self.exit_now = True

    @timer
    def check_for_updates(self) -> None:
        log.debug("Trigger check for updates")
        self.library_check_triggered = True

    def should_process_update(
        self, now: float, is_playing: bool, screensaver_active: bool
    ) -> bool:
        if is_playing or screensaver_active:
            return False
        if (now - self.last_library_change_check) < self.minimum_update_interval:
            return False
        return True

    def run(self) -> None:
        log.debug("Library Monitor Started")
        monitor = xbmc.Monitor()
        while not self.exit_now and not monitor.abortRequested():
            if self.library_check_triggered and self.should_process_update(
                time.time(),
                xbmc.Player().isPlaying(),
                xbmc.getCondVisibility("System.ScreenSaverActive"),
            ):
                if self.exit_now or monitor.waitForAbort(self.time_between_checks):
                    break
                log.debug("Doing new content check")
                check_for_new_content()
                self.library_check_triggered = False
                self.last_library_change_check = time.time()

            if self.exit_now or monitor.waitForAbort(self.time_between_checks):
                break

        log.debug("Library Monitor Exited")
