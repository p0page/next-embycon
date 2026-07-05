from __future__ import annotations

import sys
import types
import unittest
import base64
import hashlib
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

    @staticmethod
    def get_version() -> str:
        return "test-version"

    @staticmethod
    def get_client() -> str:
        return "Test Client"

    @staticmethod
    def get_user_agent() -> str:
        return "Kodi/test-version"


class FakePlaybackDownloadUtils:
    calls: list[dict[str, object]] = []

    def download_url(
        self,
        url: str,
        suppress: bool = False,
        post_body: str | dict | None = None,
        method: str = "GET",
        authenticate: bool = True,
        headers: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(
            {
                "url": url,
                "suppress": suppress,
                "post_body": post_body,
                "method": method,
                "authenticate": authenticate,
                "headers": headers,
            }
        )
        return "null"


class FakeListItem:
    def __init__(self) -> None:
        self.subtitles: list[str] = []

    def setSubtitles(self, subtitles: list[str]) -> None:
        self.subtitles = subtitles


class FakeHTTPResponse:
    def __init__(
        self, status: int, reason: str, body: bytes = b"null", headers=None
    ) -> None:
        self.status = status
        self.reason = reason
        self._body = body
        self._headers = headers or []

    def read(self) -> bytes:
        return self._body

    def getheaders(self):
        return self._headers

    def getheader(self, name: str):
        for key, value in self._headers:
            if key.lower() == name.lower():
                return value
        return None


class FakeHTTPConnection:
    instances: list["FakeHTTPConnection"] = []
    response = FakeHTTPResponse(200, "OK", b"{}")

    def __init__(
        self, host: str, port=None, timeout=None, context=None
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.requests: list[dict[str, object]] = []
        self.instances.append(self)

    @property
    def address(self) -> str:
        if self.port is None:
            return self.host
        return "%s:%s" % (self.host, self.port)

    def request(self, method: str, url: str, body=None, headers=None) -> None:
        self.requests.append(
            {"method": method, "url": url, "body": body, "headers": headers}
        )

    def getresponse(self) -> FakeHTTPResponse:
        return self.response

    def close(self) -> None:
        pass


def install_kodi_stubs() -> None:
    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda: FakeAddon()
    sys.modules["xbmcaddon"] = xbmcaddon

    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.LOGERROR = 4
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.log = lambda *args, **kwargs: None
    xbmc.executebuiltin = lambda *args, **kwargs: None
    xbmc.executeJSONRPC = lambda *args, **kwargs: '{"result": {}}'
    xbmc.Player = type("Player", (), {})
    xbmc.Monitor = type("Monitor", (), {})
    xbmc.PlayList = lambda _playlist_type: types.SimpleNamespace(
        clear=lambda: None,
        add=lambda *a, **k: None,
        getposition=lambda: -1,
        size=lambda: 0,
    )
    sys.modules["xbmc"] = xbmc

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.exists = lambda path: False
    xbmcvfs.translatePath = lambda path: path
    sys.modules["xbmcvfs"] = xbmcvfs

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.WindowXMLDialog = type("WindowXMLDialog", (), {})
    xbmcgui.ListItem = type("ListItem", (), {})
    xbmcgui.Dialog = lambda: types.SimpleNamespace(notification=lambda *a, **k: None)
    sys.modules["xbmcgui"] = xbmcgui

    xbmcplugin = types.ModuleType("xbmcplugin")
    sys.modules["xbmcplugin"] = xbmcplugin


install_kodi_stubs()

from resources.lib.downloadutils import DownloadUtils  # noqa: E402
from resources.lib import downloadutils as downloadutils_module  # noqa: E402
from resources.lib import play_utils  # noqa: E402
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
        DownloadUtils._instance = None
        downloadutils_module.HomeWindow = FakeHomeWindow
        utils.DownloadUtils = FakeDownloadUtils
        utils.ClientInformation = FakeClientInformation

    def test_authenticate_uses_current_emby_form_field_names(self) -> None:
        captured = {}

        def fake_download_url(
            url: str,
            suppress: bool = False,
            post_body: str | dict | None = None,
            method: str = "GET",
            authenticate: bool = True,
            headers: dict[str, str] | None = None,
        ) -> str:
            if "AuthenticateByName" in url:
                captured["url"] = url
                captured["post_body"] = post_body
                captured["method"] = method
                captured["authenticate"] = authenticate
            return (
                '{"AccessToken":"token-123",'
                '"User":{"Id":"user-id","Name":"test-user"}}'
            )

        download_utils = DownloadUtils()
        download_utils.download_url = fake_download_url

        self.assertEqual(download_utils.authenticate(), "token-123")
        self.assertEqual(
            captured["post_body"],
            "Username=user&Pw=pass",
        )
        self.assertEqual(captured["method"], "POST")
        self.assertFalse(captured["authenticate"])

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

    def test_server_url_refreshes_when_settings_change(self) -> None:
        download_utils = DownloadUtils()
        self.assertEqual(download_utils.get_server(), "https://media.example.test:443")

        FakeAddon.settings.update(
            {
                "ipaddress": "https://changed.example.test/proxy",
                "port": "",
                "protocol": "0",
            }
        )

        self.assertEqual(
            download_utils.get_server(),
            "https://changed.example.test:443/proxy",
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

    def test_direct_stream_url_does_not_duplicate_emby_prefix(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": "/emby/Videos/item-1/stream.mkv?static=true",
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.path, "/proxy/emby/Videos/item-1/stream.mkv")
        self.assertNotIn("/emby/emby/", result.playurl or "")

    def test_direct_stream_absolute_url_is_not_prefixed(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": (
                "https://cdn.example.test/Videos/item-1/stream.mkv?static=true"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.netloc, "cdn.example.test")
        self.assertEqual(parsed.path, "/Videos/item-1/stream.mkv")
        self.assertNotIn("media.example.test", parsed.netloc)

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

    def test_transcode_url_does_not_duplicate_emby_prefix(self) -> None:
        media_source = {
            "Id": "media-source-2",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": False,
            "SupportsTranscoding": True,
            "TranscodingUrl": (
                "/emby/Videos/item-2/master.m3u8?VideoCodec=h264"
                "&AudioBitrate=128000&AudioStreamIndex=1"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-abc")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.path, "/proxy/emby/Videos/item-2/master.m3u8")
        self.assertNotIn("/emby/emby/", result.playurl or "")

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


class DownloadUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "ipaddress": "media.example.test",
            "port": "443",
            "username": "user",
            "password": "pass",
            "suppressErrors": "false",
        }
        FakeHomeWindow.props = {
            "AccessToken": "token-123",
            "userid": "user-id",
            "userimage": "DefaultUser.png",
        }
        DownloadUtils._instance = None
        downloadutils_module.HomeWindow = FakeHomeWindow
        downloadutils_module.ClientInformation = FakeClientInformation
        self.original_https_connection = (
            downloadutils_module.http.client.HTTPSConnection
        )
        self.original_http_connection = downloadutils_module.http.client.HTTPConnection
        downloadutils_module.http.client.HTTPSConnection = FakeHTTPConnection
        downloadutils_module.http.client.HTTPConnection = FakeHTTPConnection
        FakeHTTPConnection.instances = []
        FakeHTTPConnection.response = FakeHTTPResponse(200, "OK", b"{}")

    def tearDown(self) -> None:
        downloadutils_module.http.client.HTTPSConnection = (
            self.original_https_connection
        )
        downloadutils_module.http.client.HTTPConnection = self.original_http_connection

    def test_download_url_uses_default_https_port_when_url_omits_port(self) -> None:
        download_utils = DownloadUtils()

        result = download_utils.download_url(
            "https://media.example.test/emby/System/Info/Public?format=json",
            authenticate=False,
        )

        self.assertEqual(result, "{}")
        self.assertEqual(
            FakeHTTPConnection.instances[0].address, "media.example.test:443"
        )
        self.assertEqual(
            FakeHTTPConnection.instances[0].requests[0]["url"],
            "/emby/System/Info/Public?format=json",
        )

    def test_download_url_does_not_clear_saved_password_for_regular_401(self) -> None:
        hashed_username = hashlib.md5(b"user").hexdigest()
        saved_password_key = "saved_user_password_" + hashed_username
        FakeAddon.settings[saved_password_key] = "stored-password"
        FakeHTTPConnection.response = FakeHTTPResponse(401, "Unauthorized", b"")
        download_utils = DownloadUtils()

        download_utils.download_url(
            "https://media.example.test/emby/Sessions/Playing/Progress",
            post_body={"ItemId": "item-1"},
            method="POST",
        )

        self.assertEqual(FakeAddon.settings[saved_password_key], "stored-password")
        self.assertFalse(FakeHomeWindow.props.get("AccessToken"))

    def test_download_url_applies_basic_auth_for_url_credentials(self) -> None:
        expected = base64.b64encode(b"proxy-user:proxy-pass").decode("ascii")
        download_utils = DownloadUtils()

        result = download_utils.download_url(
            "https://proxy-user:proxy-pass@media.example.test/emby/Users/Public",
            authenticate=False,
        )

        self.assertEqual(result, "{}")
        headers = FakeHTTPConnection.instances[0].requests[0]["headers"]
        self.assertEqual(headers["Authorization"], "Basic " + expected)

    def test_download_url_uses_kodi_user_agent(self) -> None:
        download_utils = DownloadUtils()

        download_utils.download_url(
            "https://media.example.test/emby/System/Info/Public?format=json",
            authenticate=False,
        )

        headers = FakeHTTPConnection.instances[0].requests[0]["headers"]
        self.assertEqual(headers["User-Agent"], "Kodi/test-version")
        self.assertNotIn("EmbyCon", headers["User-Agent"])

    def test_redacts_sensitive_data_for_logs(self) -> None:
        value = {
            "X-MediaBrowser-Token": "token-123",
            "url": "https://example.test/stream?api_key=token-123&DeviceId=device-1",
            "body": "Username=test-user&Pw=secret-password",
            "response": '{"AccessToken":"token-123"}',
            "headers": [("X-MediaBrowser-Token", "token-123")],
        }

        redacted = str(downloadutils_module.redact_sensitive_data(value))

        self.assertNotIn("token-123", redacted)
        self.assertNotIn("secret-password", redacted)
        self.assertIn("<redacted>", redacted)


class PlaybackSubtitleTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "audio_playback_bitrate": "384",
            "playback_max_width": "1920",
            "direct_stream_sub_select": "0",
        }
        play_utils.DownloadUtils = FakeDownloadUtils

    def test_external_subs_uses_delivery_url_with_emby_prefix(self) -> None:
        list_item = FakeListItem()
        media_source = {
            "Id": "media-source-1",
            "MediaStreams": [
                {
                    "Type": "Subtitle",
                    "IsExternal": True,
                    "IsTextSubtitleStream": True,
                    "SupportsExternalStream": True,
                    "Index": 3,
                    "Codec": "ass",
                    "Language": "chi",
                    "IsDefault": False,
                    "IsForced": False,
                    "DeliveryUrl": (
                        "/emby/Videos/item-1/Subtitles/sub-id/Stream.ass"
                        "?api_key=existing-token"
                    ),
                }
            ],
        }

        play_utils.external_subs(media_source, list_item, "item-1")

        self.assertEqual(
            list_item.subtitles,
            [
                "https://media.example.test/proxy/emby/Videos/item-1/"
                "Subtitles/sub-id/Stream.ass?api_key=existing-token"
            ],
        )

    def test_transcode_selected_external_subtitle_uses_delivery_url(self) -> None:
        list_item = FakeListItem()
        media_source = {
            "Id": "media-source-2",
            "DefaultAudioStreamIndex": 1,
            "DefaultSubtitleStreamIndex": "",
            "MediaStreams": [
                {
                    "Type": "Audio",
                    "Index": 1,
                    "Codec": "aac",
                    "Language": "eng",
                    "ChannelLayout": "stereo",
                },
                {
                    "Type": "Subtitle",
                    "Index": 3,
                    "Codec": "ass",
                    "Language": "chi",
                    "IsDefault": False,
                    "IsForced": False,
                    "IsTextSubtitleStream": True,
                    "IsExternal": True,
                    "SupportsExternalStream": True,
                    "DeliveryUrl": (
                        "/Videos/item-2/Subtitles/sub-id/Stream.ass"
                        "?api_key=existing-token"
                    ),
                },
            ],
        }

        result = play_utils.audio_subs_pref(
            "https://media.example.test/proxy/emby/Videos/item-2/master.m3u8",
            list_item,
            media_source,
            "item-2",
            "",
            "3",
        )

        self.assertEqual(
            list_item.subtitles,
            [
                "https://media.example.test/proxy/emby/Videos/item-2/"
                "Subtitles/sub-id/Stream.ass?api_key=existing-token"
            ],
        )
        self.assertNotIn("SubtitleStreamIndex=3", result)


class PlaybackStopTests(unittest.TestCase):
    def setUp(self) -> None:
        FakePlaybackDownloadUtils.calls = []
        play_utils.DownloadUtils = FakePlaybackDownloadUtils
        play_utils.HomeWindow = FakeHomeWindow
        play_utils.ClientInformation = FakeClientInformation
        self.marked_items: list[tuple[str, bool]] = []
        self.original_mark_item_watched = play_utils.mark_item_watched
        play_utils.mark_item_watched = (
            lambda item_id, refresh=True: self.marked_items.append((item_id, refresh))
        )

    def tearDown(self) -> None:
        play_utils.mark_item_watched = self.original_mark_item_watched

    def test_direct_stream_stop_does_not_delete_active_encodings(self) -> None:
        played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        play_utils.stop_all_playback(played_information)

        urls = [call["url"] for call in FakePlaybackDownloadUtils.calls]
        self.assertIn("{server}/emby/Sessions/Playing/Stopped", urls)
        self.assertFalse(any("ActiveEncodings" in str(url) for url in urls))

    def test_transcode_stop_suppresses_active_encoding_cleanup_errors(self) -> None:
        played_information = {
            "https://media.example.test/proxy/emby/Videos/item-2/master.m3u8": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-2",
                "source_id": "source-2",
                "play_session_id": "play-session-2",
                "live_stream_id": "",
                "playback_type": "Transcode",
                "play_action_type": "play_all",
            }
        }

        play_utils.stop_all_playback(played_information)

        cleanup_calls = [
            call
            for call in FakePlaybackDownloadUtils.calls
            if "ActiveEncodings" in str(call["url"])
        ]
        self.assertEqual(len(cleanup_calls), 1)
        self.assertEqual(cleanup_calls[0]["method"], "DELETE")
        self.assertTrue(cleanup_calls[0]["suppress"])

    def test_playback_ended_does_not_mark_watched_before_threshold(self) -> None:
        monitor = play_utils.PlaybackMonitorService()
        monitor.currently_playing_id = "item-1"
        monitor.played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        monitor.onPlayBackEnded()

        self.assertEqual(self.marked_items, [])

    def test_playback_ended_marks_watched_after_threshold(self) -> None:
        monitor = play_utils.PlaybackMonitorService()
        monitor.currently_playing_id = "item-1"
        monitor.played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 92,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        monitor.onPlayBackEnded()

        self.assertEqual(self.marked_items, [("item-1", False)])


if __name__ == "__main__":
    unittest.main()
