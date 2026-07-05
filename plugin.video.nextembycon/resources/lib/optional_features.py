# Gnu General Public License - see LICENSE.TXT
from __future__ import annotations

import time
from collections.abc import Callable


FEATURE_CAPABILITIES = "capabilities"
FEATURE_WEBSOCKET = "websocket"


class OptionalFeatureRegistry:
    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or time.time
        self._unsupported_until: dict[str, float] = {}

    def is_supported(self, name: str, scope: str = "") -> bool:
        return self.seconds_until_retry(name, scope=scope) <= 0.0

    def mark_unsupported(
        self, name: str, ttl_seconds: float, scope: str = ""
    ) -> None:
        self._unsupported_until[self._key(name, scope)] = self._now() + ttl_seconds

    def seconds_until_retry(self, name: str, scope: str = "") -> float:
        retry_at = self._unsupported_until.get(self._key(name, scope), 0.0)
        return max(0.0, retry_at - self._now())

    def clear(self, name: str, scope: str = "") -> None:
        self._unsupported_until.pop(self._key(name, scope), None)

    @staticmethod
    def _key(name: str, scope: str) -> str:
        if not scope:
            return name
        return "%s|%s" % (name, scope)


optional_feature_registry = OptionalFeatureRegistry()
