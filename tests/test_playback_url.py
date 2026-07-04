from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin.video.embycon"))


class FakeAddon:
    settings: dict[str, str] = {
        "protocol": "1",
        "verify_cert": "true",
        "ipaddress": "media.example.test",
        "port": "443",
        "deviceName": "Kodi",
        "allow_direct_file_play": "false",
        "audio_playback_bitrate": "384",
        "playback_max_width": "1920",
        "http_timeout": "10",
        "suppressErrors": "true",
        "username": "user",
        "password": "pass",
        "save_user_to_settings": "true",
        "logLevel": "0",
    }

    def getSetting(self, key: str) -> str:
        return self.settings.get(key, "")

    def setSetting(self, key: str, value: str) -> None:
        self.settings[key] = value

    def getAddonInfo(self, key: str) -> str:
        return {"version": "test", "path": str(ROOT)}.get(key, "")

    def getLocalizedString(self, string_id: int) -> str:
        return str(string_id)


class FakeHomeWindow:
    props: dict[str, str] = {"userid": "user-id", "userimage": "DefaultUser.png"}

    def get_property(self, key: str) -> str:
        return self.props.get(key, "")

    def set_property(self, key: str, value: str) -> None:
        self.props[key] = value

    def clear_property(self, key: str) -> None:
        self.props.pop(key, None)


class FakeDownloadUtils:
    def get_server(self, add_user_id: bool = False) -> str:
        assert add_user_id is False
        return "https://media.example.test/proxy"

    def authenticate(self) -> str:
        return "token-123"


class FakeClientInformation:
    @staticmethod
    def get_device_id() -> str:
        return "device-456"


def install_kodi_stubs() -> None:
    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda: FakeAddon()
    sys.modules["xbmcaddon"] = xbmcaddon

    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.LOGERROR = 4
    xbmc.log = lambda *args, **kwargs: None
    xbmc.executebuiltin = lambda *args, **kwargs: None
    sys.modules["xbmc"] = xbmc

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.exists = lambda path: False
    xbmcvfs.translatePath = lambda path: path
    sys.modules["xbmcvfs"] = xbmcvfs

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Dialog = lambda: types.SimpleNamespace(notification=lambda *a, **k: None)
    sys.modules["xbmcgui"] = xbmcgui

    xbmcplugin = types.ModuleType("xbmcplugin")
    sys.modules["xbmcplugin"] = xbmcplugin


install_kodi_stubs()

from resources.lib.downloadutils import DownloadUtils  # noqa: E402
from resources.lib import utils  # noqa: E402


class PlaybackUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "ipaddress": "media.example.test",
            "port": "443",
        }
        FakeHomeWindow.props = {"userid": "user-id", "userimage": "DefaultUser.png"}
        utils.DownloadUtils = FakeDownloadUtils
        utils.ClientInformation = FakeClientInformation

    def test_server_url_preserves_reverse_proxy_path(self) -> None:
        FakeAddon.settings.update(
            {
                "ipaddress": "https://media.example.test/proxy",
                "port": "",
                "protocol": "0",
            }
        )

        download_utils = DownloadUtils()
        download_utils.set_host_domain()

        self.assertEqual(
            download_utils.get_server(),
            "https://media.example.test:443/proxy",
        )

    def test_direct_stream_url_authenticates_player_request(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": "/Videos/item-1/stream.mkv?static=true",
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(
            result.playurl,
            "https://media.example.test/proxy/emby/Videos/item-1/stream.mkv"
            "?static=true&api_key=token-123&DeviceId=device-456"
            "&MediaSourceId=media-source-1&PlaySessionId=play-session-789",
        )
        self.assertEqual(result.playback_type, "1")
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["DeviceId"], ["device-456"])
        self.assertEqual(query["MediaSourceId"], ["media-source-1"])
        self.assertEqual(query["PlaySessionId"], ["play-session-789"])

    def test_transcode_url_authenticates_player_request(self) -> None:
        media_source = {
            "Id": "media-source-2",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": False,
            "SupportsTranscoding": True,
            "TranscodingUrl": (
                "/Videos/item-2/master.m3u8?VideoCodec=h264"
                "&AudioBitrate=128000&AudioStreamIndex=1"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-abc")
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(result.playback_type, "2")
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["DeviceId"], ["device-456"])
        self.assertEqual(query["MediaSourceId"], ["media-source-2"])
        self.assertEqual(query["PlaySessionId"], ["play-session-abc"])
        self.assertEqual(query["AudioBitrate"], ["384000"])
        self.assertEqual(query["MaxWidth"], ["1920"])
        self.assertNotIn("AudioStreamIndex", query)

    def test_direct_play_without_direct_stream_url_uses_http_stream(self) -> None:
        media_source = {
            "Id": "media-source-3",
            "Container": "mkv",
            "SupportsDirectPlay": True,
            "SupportsDirectStream": False,
            "SupportsTranscoding": False,
            "Path": r"\\nas\movies\movie.mkv",
        }

        result = utils.PlayUtils.get_play_url(
            media_source, "play-session-def", "item-3"
        )
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(
            parsed.path,
            "/proxy/emby/Videos/item-3/stream",
        )
        self.assertEqual(result.playback_type, "1")
        self.assertEqual(query["static"], ["true"])
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["MediaSourceId"], ["media-source-3"])
        self.assertEqual(query["PlaySessionId"], ["play-session-def"])


if __name__ == "__main__":
    unittest.main()
